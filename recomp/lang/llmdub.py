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
ENGINES = ("nllb", "m2m100", "bergamot", "google", "stub")
OFFLINE = ("nllb", "m2m100", "bergamot")  # run on your machine (worker env); google is the one online engine

# What each offline system can translate (ISO 639-1). NLLB-200 and M2M-100 translate directly between any two of
# their languages; Mozilla's bergamot models are English-centric (X→en, en→X; others chain through English).
NLLB = {"am", "om", "ti", "so", "sw", "en", "es", "fr", "de", "it", "pt", "ar", "ha", "yo", "ig", "zu", "rw", "zh", "ja",
        "ru", "tr", "hi", "nl", "lg", "ln", "wo", "xh", "ny", "sn", "rn", "mg", "af", "fa", "he", "uk", "pl", "ro", "el",
        "cs", "sv", "da", "fi", "no", "hu", "bg", "sr", "hr", "vi", "id", "ms", "th", "ko", "bn", "ur", "ta", "te", "pa"}
M2M100 = set("af am ar ast az ba be bg bn br bs ca ceb cs cy da de el en es et fa ff fi fr fy ga gd gl gu ha he hi hr ht "
             "hu hy id ig ilo is it ja jv ka kk km kn ko lb lg ln lo lt lv mg mk ml mn mr ms my ne nl no ns oc or pa pl "
             "ps pt ro ru sd si sk sl so sq sr ss su sv sw ta th tl tn tr uk ur uz vi wo xh yi yo zh zu".split())
BERGAMOT = set("af ar az be bg bn bs ca cs da de el en es et eu fa fi fr gl gu he hi hr hu id is it ja kn ko lt lv ml mr "
               "ms nb nl no pl pt ro ru sk sl sq sr sv ta te th tl tr ug uk ur vi zh".split())


def supports(engine: str, src: str, tgt: str) -> bool:
    s, t = (src or "").lower()[:2], (tgt or "").lower()[:2]
    if engine in ("google", "stub"):
        return True
    table = {"nllb": NLLB, "m2m100": M2M100, "bergamot": BERGAMOT}.get(engine)
    return bool(table) and s in table and t in table


def engine_for(want: str, src: str, tgt: str, online: bool, avoid: tuple = ()) -> tuple[str, str]:
    """The MT system for one crossing: the one asked for if it can do the pair and the dub may use it, else the
    first offline system that can (one not in ``avoid`` first, so two views stay independent), else google when
    online. Returns (engine, note)."""
    if os.environ.get("RECOMP_MT") == "stub":
        return "stub", ""
    order = [want] + [e for e in OFFLINE if e != want] + ["google"]
    allowed = [e for e in order if (e != "google" or online) and supports(e, src, tgt)]
    if not allowed:
        raise RecompError("E_OFFLINE" if not online else "E_INVALID", f"no MT system here can translate {src}→{tgt}",
                          hint="Allow online MT (`recomp dub settings --at studio --online true`) or translate those "
                               "lines yourself")
    pick = next((e for e in allowed if e not in avoid), allowed[0])
    note = ""
    if pick != want:
        why = "is online and the dub is offline" if want == "google" and not online else f"cannot do {src}→{tgt}"
        note = f"{want} {why}: using {pick}"
    if pick in avoid:
        note = (note + "; " if note else "") + f"no independent second system for {src}→{tgt}: {pick} again"
    return pick, note
TIER_W = {"core": 3.0, "support": 2.0, "colour": 1.0}

# Languages the LLM reads with nuance and writes naturally. Edit per model: `recomp dub settings --strong …`.
STRONG = ["en", "es", "fr", "de", "it", "pt", "nl", "sv", "da", "no", "pl", "cs", "ro", "ru", "uk", "tr", "ar", "he",
          "fa", "hi", "zh", "ja", "ko", "id", "vi"]

DEFAULTS: dict = {
    "route": "auto",            # auto | direct | source | target | middle | multi (aliases: src-en, tgt-en, mid-en)
    "middle": ["en"],           # middle languages, in order (multi uses two or more: e.g. en,es)
    "budget": "economy",        # economy: one writing language · quality: two, pooled per segment
    "online": False,            # offline by default: NLLB / M2M-100 / bergamot MT and MMS voices; True allows google + edge
    "views_mt": ["nllb", "m2m100"],  # MT systems for the understanding views, paired with the middle languages in order
    "mt": "nllb",               # MT system from a writing language into the target (and for back-translation)
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
        elif k in ("conserve", "online"):
            v = bool(v) if not isinstance(v, str) else v.lower() in ("1", "true", "yes", "on")
        out[k] = v
    return out


def layers(project, source: dict | None = None, journey: dict | None = None) -> list[tuple[str, dict]]:
    """The settings layers, lowest first: built-in → studio config → project → source → journey."""
    studio = {k: v for k, v in (config.get("dub") or {}).items() if k in DEFAULTS}  # model paths live there too
    out = [("default", dict(DEFAULTS)), ("studio", studio),
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
    engines = list(settings.get("views_mt") or ["nllb"])
    online = bool(settings.get("online"))
    notes: list[str] = []
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
        used: tuple = ()
        for k, lang in enumerate(reads):
            want = engines[k] if k < len(engines) else engines[-1]
            eng, note = engine_for(want, src, lang, online, avoid=used)
            used += (eng,)
            views.append({"lang": lang, "mt": eng})
            if note:
                notes.append(f"view {src}→{lang}: {note}")
    mt_into = {}
    for w in writes:
        if w != tgt:
            eng, note = engine_for(settings.get("mt", "nllb"), w, tgt, online)
            mt_into[w] = eng
            if note:
                notes.append(f"{w}→{tgt}: {note}")
    verify = settings.get("verify", "auto")
    crosses = any(w != tgt for w in writes)
    needs_check = verify == "always" or (verify == "auto" and crosses and not t_ok)
    back = []
    if needs_check:
        langs = [v["lang"] for v in views] or [reads[0]]
        langs = [x for x in langs if x != tgt] or ["en"]
        prefer = [v["mt"] for v in views] or [settings.get("mt", "nllb")]
        for k, lang in enumerate(langs):
            eng, note = engine_for(prefer[min(k, len(prefer) - 1)], tgt, lang, online)
            back.append({"lang": lang, "mt": eng})
            if note:
                notes.append(f"check {tgt}→{lang}: {note}")
    steps = []
    if views:
        into = ", ".join("{} ({})".format(v["lang"], v["mt"]) for v in views)
        steps.append(f"MT views of the {src} source into {into}: "
                     "whole line and each speech frame → the LLM writes the meaning map from them")
    else:
        steps.append(f"the LLM reads the {src} source and writes the meaning map (units pinned to speech frames)")
    for w in writes:
        steps.append(f"the LLM writes options per frame in {w}" + ("" if w == tgt else f" → MT {w}→{tgt} ({mt_into[w]})"))
    steps.append(f"the {tgt} voice speaks every option on the speaker's frames → exact selection"
                 + (" over the pooled languages" if len(writes) > 1 else ""))
    if back:
        steps.append(f"check: back-translate the chosen {tgt} into {', '.join(b['lang'] for b in back)}; the LLM marks "
                     "units kept and errors")
    steps.append(f"steer out-of-band frames for up to {settings.get('rounds', 2)} round(s)")
    if views:
        steps.append("low-confidence lines → a person checks them")
    return {"src": src, "tgt": tgt, "route": route, "budget": settings.get("budget"), "strong": {"src": s_ok, "tgt": t_ok},
            "online": online, "reads": reads, "writes": writes, "views": views, "mt_into": mt_into, "back_translate": back,
            "steps": steps, "notes": notes}


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


NLLB_MODEL = "facebook/nllb-200-distilled-600M"
M2M100_MODEL = "facebook/m2m100_418M"


class MT:
    """MT with a per-project cache. Offline engines run under the worker python: nllb (NLLB-200), m2m100 (M2M-100,
    a second independent system), bergamot (Mozilla Firefox Translations, English-centric). google is online."""

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
        if engine in OFFLINE:
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
            args += ["--model", config.get("dub.nllb_model") or NLLB_MODEL]
        elif engine == "m2m100":
            args += ["--model", config.get("dub.m2m100_model") or M2M100_MODEL]
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

    def __init__(self, project, lang: str, voice: str | None = None, online: bool | None = None):
        from . import tts
        self.lang, self.voice, self.online = lang, voice, online
        self.backend, self.v = tts.voice_for(lang, voice, online)
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
            tts.synth_batch([(t, self.clips / f"{_key(self.backend, self.v, t)}.wav") for t in todo], self.lang, voice=self.voice,
                            online=self.online)
        for n, t in enumerate(todo):
            clip = self.clips / f"{_key(self.backend, self.v, t)}.wav"
            if clip.exists():
                from ..media import ff
                d = ff.probe(clip).duration
            else:
                d = tts.synth(t, self.lang, clip, voice=self.voice, online=self.online)
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


# ---- offline models: what a dub needs, what is here, fetching it once ------------------------------------------

BERGAMOT_REGISTRY = "https://storage.googleapis.com/moz-fx-translations-data--303e-prod-translations-data/db/models.json"


def needs(plans: list[dict]) -> dict:
    """The offline models a set of routes uses: Hugging Face repos (MT and MMS voices) and bergamot pairs."""
    from . import tts
    repos, pairs, voices = set(), set(), {}
    for pl in plans:
        crossings = [(pl["src"], v["lang"], v["mt"]) for v in pl["views"]]
        crossings += [(w, pl["tgt"], e) for w, e in pl["mt_into"].items()]
        crossings += [(pl["tgt"], b["lang"], b["mt"]) for b in pl["back_translate"]]
        for s, t, e in crossings:
            if e == "nllb":
                repos.add(config.get("dub.nllb_model") or NLLB_MODEL)
            elif e == "m2m100":
                repos.add(config.get("dub.m2m100_model") or M2M100_MODEL)
            elif e == "bergamot":
                pairs.update([f"{s}-{t}"] if s == "en" or t == "en" else [f"{s}-en", f"en-{t}"])
        try:
            backend, v = tts.voice_for(pl["tgt"], online=pl.get("online"))
        except RecompError:
            backend, v = None, None
        voices[pl["tgt"]] = {"backend": backend, "voice": v}
        if backend == "mms":
            repos.add(v)
    return {"repos": sorted(repos), "bergamot": sorted(pairs), "voices": voices}


def hf_present(repo: str) -> bool:
    home = config.get("worker.hf_home") or os.environ.get("HF_HOME") or ""
    return bool(home) and (Path(home) / "hub" / f"models--{repo.replace('/', '--')}").exists()


def bergamot_folder() -> Path:
    return Path(config.get("dub.bergamot_models") or (config.home() / "models" / "bergamot"))


def bergamot_present(pair: str) -> bool:
    f = bergamot_folder() / pair
    return f.exists() and any(f.glob("model.*.bin"))


def fetch_bergamot(pairs: list[str], log=print) -> list[dict]:
    """Download Mozilla's base-memory models for these pairs (e.g. de-en) from their public registry."""
    import gzip
    import shutil
    import httpx
    reg = httpx.get(BERGAMOT_REGISTRY, timeout=60).json()
    base, out = reg["baseUrl"], []
    for pair in pairs:
        s, t = pair.split("-")
        cands = reg["models"].get(f"{s}-{t}") or []
        m = next((x for x in cands if x.get("architecture") == "base-memory"), cands[0] if cands else None)
        if not m:
            out.append({"pair": pair, "ok": False, "error": "Mozilla has no model for this pair"})
            continue
        dest = bergamot_folder() / pair
        dest.mkdir(parents=True, exist_ok=True)
        for f in m["files"].values():
            path = f if isinstance(f, str) else f["path"]
            gz = dest / Path(path).name
            with httpx.stream("GET", f"{base}/{path}", timeout=300) as r:
                r.raise_for_status()
                with gz.open("wb") as fh:
                    for chunk in r.iter_bytes():
                        fh.write(chunk)
            with gzip.open(gz) as fi, open(str(gz)[:-3], "wb") as fo:
                shutil.copyfileobj(fi, fo)
            gz.unlink()
        log(f"bergamot {pair}: ok")
        out.append({"pair": pair, "ok": True})
    if not config.get("dub.bergamot_models"):
        config.set_value("dub.bergamot_models", str(bergamot_folder()))
    return out
