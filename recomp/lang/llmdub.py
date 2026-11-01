"""The LLM dubber: timed, meaning-conserving dub lines in any language pair (P19, docs/research/P19-dubbing-and-meaning).

The agent (an LLM) only reads and writes languages it is strong in. This module does the language-free work around
it:

- **Routes.** Per pair, which languages the LLM reads and writes in, and where machine translation (MT) crosses:

  | Route | When | The LLM reads | The LLM writes | MT |
  |---|---|---|---|---|
  | `direct` | source and target both strong | the source | the target | none |
  | `source` ("src-en") | source strong, target weak | the source | the source (+ a middle language in quality mode) | writing language → target, back-translation to verify |
  | `target` ("tgt-en") | source weak, target strong | MT views of the source in the middle language(s) | the target (+ a middle language in quality mode) | source → middle views |
  | `middle` ("mid-en") | both weak | MT views in one middle language | the middle language | views, middle → target, back-translation |
  | `multi` | both weak, meaning matters most | MT views in two or more middle languages, from different MT systems | the first middle (+ the second in quality mode) | as `middle`, per middle language |

- **Frames.** Each line is split into speech frames at the speaker's pauses (word timings), so the dub speaks when
  they speak and pauses when they pause.
- **Selection.** Every option is translated (if needed) and spoken by the target voice. The measured duration
  against its frame is the only ruler. The exact best combination per line maximises the meaning units kept, stays
  in the band, keeps every core unit, and avoids verified MT errors. Conserve mode costs added content and lets
  short silences through.
- **Steering and checks.** Frames still out of band become rewrite requests with a syllable target. Chosen options
  that crossed MT become back-translation checks.

Research behind each choice:

- frames and the voice as ruler: `wt-placement`, `wt-duration`, `wt-llm-multiround`;
- units and exact selection: `wt-mctr`;
- MT-only targets: `wt-twosided`;
- weak sources: `wt-pivot`;
- routes: `wt-routes`;
- two middle languages: `wt-bipivot`.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
from pathlib import Path

from ..core import config
from ..envelope import RecompError

ROUTES = ("auto", "direct", "source", "target", "middle", "multi")
ALIASES = {"src-en": "source", "src": "source", "tgt-en": "target", "tgt": "target", "mid-en": "middle",
           "mid": "middle", "multi-middle": "multi"}
BUDGETS = ("economy", "quality")
ENGINES = ("google", "nllb", "bergamot", "stub")
TIER_W = {"core": 3.0, "support": 2.0, "colour": 1.0}

# Languages the LLM reads with nuance and writes naturally. Edit per model: `recomp dub settings --strong …`.
STRONG = ["en", "es", "fr", "de", "it", "pt", "nl", "sv", "da", "no", "pl", "cs", "ro", "ru", "uk", "tr", "ar", "he",
          "fa", "hi", "zh", "ja", "ko", "id", "vi"]

DEFAULTS: dict = {
    "route": "auto",            # auto | direct | source | target | middle | multi (aliases: src-en, tgt-en, mid-en)
    "middle": ["en"],           # middle languages, in order (multi uses two or more: e.g. en,es)
    "budget": "economy",        # economy: one writing language · quality: two, pooled per segment
    "views_mt": ["google"],     # MT systems for the understanding views, paired with the middle languages in order
    "mt": "google",             # MT system from a writing language into the target (and for back-translation)
    "verify": "auto",           # auto (when the target is weak or MT crossed) | always | never
    "conserve": False,          # cost added content; a short silence beats an invention
    "rounds": 2,                # steering rounds the agent is offered
    "band": [0.8, 1.05],        # good fit: voice time / speaker time
    "mt_prior": 0.5,            # pooled options: cost of an MT-crossed option, so a directly written one wins near-ties
    "min_pause": 0.3,           # a pause this long between words splits a line into frames
    "strong": None,             # override the strong-language list (None: the built-in one)
    "voice": None,              # target voice (default: the language's configured voice)
}
FIELDS = tuple(DEFAULTS)

ALPHA, BETA, ERR_COST = 4.0, 1.0, 3.0


# ---- settings --------------------------------------------------------------------------------------------------

def normalise(over: dict) -> dict:
    """Validate and normalise a partial settings dict (from any layer)."""
    out = {}
    for k, v in (over or {}).items():
        if k == "targets":  # languages to dub into: informational, kept with the source
            out[k] = [x for x in (v.split(",") if isinstance(v, str) else v) if str(x).strip()]
            continue
        if k not in DEFAULTS:
            raise RecompError("E_INVALID", f"unknown dub setting {k!r}", hint=f"Settings: {', '.join(FIELDS)}")
        if v is None:
            continue
        if k == "route":
            v = ALIASES.get(str(v).lower(), str(v).lower())
            if v not in ROUTES:
                raise RecompError("E_INVALID", f"route must be one of {', '.join(ROUTES)} (or src-en, tgt-en, mid-en)")
        elif k == "budget" and v not in BUDGETS:
            raise RecompError("E_INVALID", f"budget must be one of {', '.join(BUDGETS)}")
        elif k in ("middle", "views_mt", "strong"):
            v = [x.strip() for x in (v.split(",") if isinstance(v, str) else v) if str(x).strip()]
            if k == "views_mt" and any(e not in ENGINES for e in v):
                raise RecompError("E_INVALID", f"MT systems: {', '.join(ENGINES)}")
        elif k == "mt" and v not in ENGINES:
            raise RecompError("E_INVALID", f"mt must be one of {', '.join(ENGINES)}")
        elif k == "verify" and v not in ("auto", "always", "never"):
            raise RecompError("E_INVALID", "verify must be auto, always or never")
        elif k == "band":
            v = [float(x) for x in (v.split(",") if isinstance(v, str) else v)]
            if len(v) != 2 or not 0 < v[0] < v[1]:
                raise RecompError("E_INVALID", "band is two ratios, low,high (e.g. 0.8,1.05)")
        elif k in ("rounds",):
            v = int(v)
        elif k in ("mt_prior", "min_pause"):
            v = float(v)
        elif k == "conserve":
            v = bool(v) if not isinstance(v, str) else v.lower() in ("1", "true", "yes", "on")
        out[k] = v
    return out


def layers(project, source: dict | None = None, journey: dict | None = None) -> list[tuple[str, dict]]:
    """The settings layers, lowest first: built-in → studio config → project → source → journey."""
    out = [("default", dict(DEFAULTS)), ("studio", config.get("dub") or {}),
           ("project", (project.meta.get("dub") if project else None) or {})]
    if source:
        out.append((f"source {source.get('ref')}", (source.get("meta") or {}).get("dub") or {}))
    if journey:
        out.append((f"journey {journey.get('ref')}", (journey.get("settings") or {}).get("dub") or {}))
    return out


def resolve(project, source: dict | None = None, journey: dict | None = None) -> tuple[dict, dict]:
    """Effective settings and where each one came from."""
    eff, origin = {}, {}
    for name, layer in layers(project, source, journey):
        for k, v in normalise(layer).items() if name != "default" else layer.items():
            eff[k], origin[k] = v, name
    return eff, origin


def strong_set(settings: dict) -> set[str]:
    return {x.lower()[:2] for x in (settings.get("strong") or STRONG)}


# ---- routes ----------------------------------------------------------------------------------------------------

def plan(src: str, tgt: str, settings: dict) -> dict:
    """Which languages the LLM reads and writes in for this pair, and every MT crossing."""
    strong = strong_set(settings)
    s_ok, t_ok = (src or "").lower()[:2] in strong, (tgt or "").lower()[:2] in strong
    route = settings.get("route") or "auto"
    middle = [m for m in (settings.get("middle") or ["en"])]
    quality = settings.get("budget") == "quality"
    if route == "auto":
        route = "direct" if s_ok and t_ok else "target" if t_ok else "source" if s_ok else \
            ("multi" if len(middle) > 1 else "middle")
    if route == "multi" and len(middle) < 2:
        middle = middle + [m for m in ("en", "es") if m not in middle][: 2 - len(middle)]
    engines = list(settings.get("views_mt") or ["google"])
    if route == "direct":
        reads, writes = [src], [tgt]
    elif route == "source":
        reads = [src]
        writes = [src] + ([m for m in middle if m not in (src, tgt)][:1] if quality else [])
    elif route == "target":
        reads = middle[:1] if len(middle) == 1 else middle
        writes = [tgt] + ([middle[0]] if quality and middle[0] != tgt else [])
    elif route == "middle":
        reads, writes = middle[:1], middle[:1]
    else:  # multi
        reads, writes = middle, middle[: 2 if quality else 1]
    views = []
    if route in ("target", "middle", "multi"):
        for k, lang in enumerate(reads):
            views.append({"lang": lang, "mt": engines[k] if k < len(engines) else engines[-1]})
    verify = settings.get("verify", "auto")
    crosses = any(w != tgt for w in writes)
    needs_check = verify == "always" or (verify == "auto" and crosses and not t_ok)
    back = []
    if needs_check:
        back = [{"lang": v["lang"], "mt": v["mt"]} for v in views] or [{"lang": reads[0], "mt": settings.get("mt", "google")}]
        back = [b for b in back if b["lang"] != tgt] or [{"lang": "en", "mt": settings.get("mt", "google")}]
    steps = []
    if views:
        into = ", ".join("{} ({})".format(v["lang"], v["mt"]) for v in views)
        steps.append(f"MT views of the {src} source into {into}: "
                     "whole line and each speech frame → the LLM writes the meaning map from them")
    else:
        steps.append(f"the LLM reads the {src} source and writes the meaning map (units pinned to speech frames)")
    for w in writes:
        steps.append(f"the LLM writes options per frame in {w}" + ("" if w == tgt else f" → MT {w}→{tgt} ({settings.get('mt')})"))
    steps.append(f"the {tgt} voice speaks every option on the speaker's frames → exact selection"
                 + (" over the pooled languages" if len(writes) > 1 else ""))
    if back:
        steps.append(f"check: back-translate the chosen {tgt} into {', '.join(b['lang'] for b in back)}; the LLM marks "
                     "units kept and errors")
    steps.append(f"steer out-of-band frames for up to {settings.get('rounds', 2)} round(s)")
    if views:
        steps.append("low-confidence lines → a person checks them")
    return {"src": src, "tgt": tgt, "route": route, "budget": settings.get("budget"), "strong": {"src": s_ok, "tgt": t_ok},
            "reads": reads, "writes": writes, "views": views, "back_translate": back, "steps": steps}


# ---- frames ----------------------------------------------------------------------------------------------------

def frames(words: list[tuple[float, float, str]], span: tuple[float, float], text: str, min_pause: float) -> list[dict]:
    """Speech frames of one line: words grouped between pauses of ``min_pause`` or more, clipped to ``span``.
    Without word timings the line is one frame."""
    a, b = span
    ws = [(max(a, s), min(b, e), t) for s, e, t in words if e > a and s < b]
    if not ws:
        return [{"start": round(a, 3), "end": round(b, 3), "dur": round(b - a, 3), "text": text}]
    out, cur = [], [ws[0]]
    for w in ws[1:]:
        if w[0] - cur[-1][1] >= min_pause:
            out.append(cur)
            cur = [w]
        else:
            cur.append(w)
    out.append(cur)
    return [{"start": round(f[0][0], 3), "end": round(f[-1][1], 3), "dur": round(max(0.05, f[-1][1] - f[0][0]), 3),
             "text": " ".join(t for _, _, t in f)} for f in out]


# ---- syllables (any script) ------------------------------------------------------------------------------------

_VOWEL_RX = re.compile("[aeiouyàáâãäåæèéêëìíîïòóôõöøùúûüýÿœɛɔəɨ]+")


def _ethiopic(ch: str) -> bool:
    cp = ord(ch)
    return 0x1200 <= cp <= 0x139F or 0x2D80 <= cp <= 0x2DDF or 0xAB00 <= cp <= 0xAB2F


def _word_syllables(word: str) -> float:
    eth = [c for c in word if _ethiopic(c) and unicodedata.category(c).startswith("L")]
    if eth:  # sixth-order fidel is often no syllable of its own
        n = 0.0
        for k, c in enumerate(eth):
            sixth = 0x1200 <= ord(c) <= 0x137F and (ord(c) - 0x1200) % 8 == 5
            n += (0.2 if k == len(eth) - 1 and k > 0 else 0.4) if sixth else 1.0
        return max(1.0, n)
    cjk = [c for c in word if 0x4E00 <= ord(c) <= 0x9FFF or 0x3040 <= ord(c) <= 0x30FF or 0xAC00 <= ord(c) <= 0xD7AF]
    if cjk:
        return float(len(cjk))
    w = word.lower()
    if w.isdigit():
        return 1.5 * len(w)
    groups = len(_VOWEL_RX.findall(w))
    if groups > 1 and w.endswith("e") and not w.endswith(("le", "ee", "ie")):
        groups -= 1
    if groups == 0:
        letters = sum(ch.isalpha() for ch in w)
        return max(1.0, letters / 3) if letters else 0.0
    return float(groups)


def syllables(text: str) -> float:
    return sum(_word_syllables(w) for w in re.findall(r"\w+", unicodedata.normalize("NFC", text or "")))


# ---- MT --------------------------------------------------------------------------------------------------------

def option_id(key: str, frame: int, lang: str, text: str) -> str:
    return hashlib.sha1(f"{key}|{frame}|{lang}|{text.strip()}".encode()).hexdigest()[:10]


class MT:
    """MT with a per-project cache. Engines: google (web endpoint), nllb (NLLB-200 under the worker python),
    bergamot (Mozilla Firefox Translations models, English-centric: chains through en), stub (tests)."""

    def __init__(self, project):
        self.path = project.dir("cache", "dub") / "mt_cache.json"
        try:
            self.cache = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self.cache = {}
        self.calls = 0

    def save(self) -> None:
        self.path.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")

    def translate(self, texts: list[str], src: str, tgt: str, engine: str) -> list[str]:
        if os.environ.get("RECOMP_MT") == "stub":
            engine = "stub"
        if src == tgt:
            return list(texts)
        k = lambda t: f"{engine}|{src}|{tgt}|{t}"  # noqa: E731
        todo = sorted({t for t in texts if t.strip() and k(t) not in self.cache})
        if todo:
            got = self._run(todo, src, tgt, engine)
            for t, r in zip(todo, got):
                self.cache[k(t)] = r
            self.calls += len(todo)
        return [self.cache.get(k(t), "") if t.strip() else "" for t in texts]

    def _run(self, texts: list[str], src: str, tgt: str, engine: str) -> list[str]:
        if engine == "stub":
            return [f"[{tgt}] {t}" for t in texts]
        if engine == "google":
            from .google import Translator
            tr = Translator(src, tgt)
            return [tr.raw(t) for t in texts]
        if engine in ("nllb", "bergamot"):
            return _worker_mt(texts, src, tgt, engine)
        raise RecompError("E_INVALID", f"unknown MT system {engine!r}", hint=f"Choose from {', '.join(ENGINES)}")


def _worker_mt(texts: list[str], src: str, tgt: str, engine: str) -> list[str]:
    """Batch MT in the worker env (scripts/mt_nllb.py, mt_bergamot.py): JSONL in, JSONL out."""
    import tempfile
    from ..workers.worker_env import run_script
    with tempfile.TemporaryDirectory() as d:
        inp, out = Path(d) / "in.jsonl", Path(d) / "out.jsonl"
        inp.write_text("".join(json.dumps({"key": str(i), "text": t}, ensure_ascii=False) + "\n"
                               for i, t in enumerate(texts)), encoding="utf-8")
        args = ["--src", src, "--tgt", tgt, "--in", str(inp), "--out", str(out)]
        if engine == "nllb":
            args += ["--model", config.get("dub.nllb_model") or "facebook/nllb-200-distilled-600M"]
        else:
            models = config.get("dub.bergamot_models")
            if not models:
                raise RecompError("E_CONFIG", "bergamot needs Mozilla model folders",
                                  hint="`recomp config set dub.bergamot_models <folder with de-en, en-es, …>` "
                                       "(base-memory models from Mozilla's public model registry)")
            args += ["--models", models]
        run_script(f"mt_{engine}", args, allow_download=bool(config.get("dub.allow_download")))
        got = {}
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                got[int(r["key"])] = r["text"]
    return [got.get(i, "") for i in range(len(texts))]


# ---- the voice as ruler ----------------------------------------------------------------------------------------

class Ruler:
    """Measured speaking time of a text in the target voice (synthesised once, cached by voice and text)."""

    def __init__(self, project, lang: str, voice: str | None = None):
        from . import tts
        self.lang, self.voice = lang, voice
        self.backend, self.v = tts.voice_for(lang, voice)
        self.clips = project.dir("cache", "dub", "clips")
        self.path = project.dir("cache", "dub") / "durations.json"
        try:
            self.cache = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self.cache = {}

    def _k(self, text: str) -> str:
        return f"{self.backend}|{self.v}|{text.strip()}"

    def measure(self, texts: list[str], progress=None) -> None:
        from . import tts
        from .dub import _key
        todo = sorted({t.strip() for t in texts if t.strip() and self._k(t) not in self.cache})
        if self.backend == "mms" and todo:
            tts.synth_batch([(t, self.clips / f"{_key(self.backend, self.v, t)}.wav") for t in todo], self.lang, voice=self.voice)
        for n, t in enumerate(todo):
            clip = self.clips / f"{_key(self.backend, self.v, t)}.wav"
            if clip.exists():
                from ..media import ff
                d = ff.probe(clip).duration
            else:
                d = tts.synth(t, self.lang, clip, voice=self.voice)
            self.cache[self._k(t)] = round(float(d), 3)
            if progress:
                progress(n / max(1, len(todo)), f"voiced {n + 1}/{len(todo)}")
        self.path.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")

    def __call__(self, text: str) -> float:
        return self.cache.get(self._k(text), 0.0) if text.strip() else 0.0

    def rate(self) -> float:
        """This voice's syllables per second, from what it has spoken (5.5 until it has spoken enough)."""
        mine = [(syllables(k.split("|", 2)[2]), d) for k, d in self.cache.items() if k.startswith(f"{self.backend}|{self.v}|")]
        syl, dur = sum(s for s, _ in mine), sum(d for _, d in mine)
        return syl / dur if dur > 5 else 5.5


# ---- exact selection -------------------------------------------------------------------------------------------

def fit_penalty(ratio: float, band: tuple[float, float], soft_floor: float | None) -> float:
    lo, hi = band
    if ratio <= 0:
        return 4.0
    if lo <= ratio <= hi:
        return 0.0
    if soft_floor and soft_floor <= ratio < lo:
        return 0.1 + 2 * math.log(lo / ratio) ** 2
    d = math.log(ratio / (hi if ratio > hi else lo))
    return (3.0 if ratio > hi else 1.0) * 25 * d * d + 0.25


def select(units: list[dict], frames_: list[dict], variants: dict[int, list[dict]], dur, band=(0.8, 1.05),
           conserve: bool = False) -> dict:
    """Exact best choice of one option per frame. Options: {text, units, errors, added, penalty}.

    Score = Σ weights of the units covered − 4·fit penalties − duplicates − 3·verified errors − penalties
    (− 2·added content in conserve mode); every core unit must be covered when any combination can. Dynamic
    programming over the set of units covered so far, so long lines stay exact and fast."""
    gamma, soft = (2.0, 0.65) if conserve else (0.0, None)
    wt = {u["id"]: TIER_W.get(u.get("tier", "core"), 1.0) for u in units}
    core = frozenset(u["id"] for u in units if u.get("tier", "core") == "core")
    states: dict[frozenset, tuple[float, list]] = {frozenset(): (0.0, [])}
    for k, fr in enumerate(frames_):
        pool = variants.get(k) or [{"text": "", "units": []}]
        nxt: dict[frozenset, tuple[float, list]] = {}
        for cov, (sc, picks) in states.items():
            for v in pool:
                us = frozenset(v.get("units", [])) & frozenset(wt)
                r = dur(v["text"]) / fr["dur"] if v["text"].strip() else 0.0
                f = 0.0 if (not v["text"].strip() and fr["dur"] < 0.3) else fit_penalty(r, band, soft)
                cost = ALPHA * f + BETA * len(cov & us) + gamma * len(v.get("added", [])) + \
                    ERR_COST * len(v.get("errors", [])) + float(v.get("penalty", 0.0))
                ncov = cov | us
                cand = (sc - cost, picks + [(v, round(r, 3))])
                if ncov not in nxt or cand[0] > nxt[ncov][0]:
                    nxt[ncov] = cand
        states = nxt
    scored = [(sc + sum(wt[u] for u in cov), cov, picks) for cov, (sc, picks) in states.items()]
    with_core = [x for x in scored if core <= x[1]]
    best = max(with_core or scored, key=lambda x: x[0])
    score, cov, picks = best
    return {"score": round(score, 3), "picks": [p for p, _ in picks], "phrases": [p["text"] for p, _ in picks],
            "ratios": [r for _, r in picks], "units": sorted(cov), "missing_core": sorted(core - cov),
            "kept_all_core": bool(with_core)}
