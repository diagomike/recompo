"""NLLB-200 machine translation under the worker python (a second, direct MT system for the LLM dubber).

    python mt_nllb.py --model facebook/nllb-200-distilled-600M --src am --tgt es --in jobs.jsonl --out out.jsonl

Jobs are JSONL {key, text}; output JSONL {key, text}. NLLB translates directly between its 200 languages (no
pivot through English), which makes it a truly independent second view of a source (P19 `wt-bipivot`).
"""

from __future__ import annotations

import argparse
import json
import sys

CODES = {"am": "amh_Ethi", "om": "gaz_Latn", "ti": "tir_Ethi", "so": "som_Latn", "sw": "swh_Latn", "en": "eng_Latn",
         "es": "spa_Latn", "fr": "fra_Latn", "de": "deu_Latn", "it": "ita_Latn", "pt": "por_Latn", "ar": "arb_Arab",
         "ha": "hau_Latn", "yo": "yor_Latn", "ig": "ibo_Latn", "zu": "zul_Latn", "rw": "kin_Latn", "zh": "zho_Hans",
         "ja": "jpn_Jpan", "ru": "rus_Cyrl", "tr": "tur_Latn", "hi": "hin_Deva", "nl": "nld_Latn"}


def main():
    ap = argparse.ArgumentParser()
    for k in ("model", "src", "tgt", "in", "out"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    src, tgt = CODES.get(a.src, a.src), CODES.get(a.tgt, a.tgt)
    tok = AutoTokenizer.from_pretrained(a.model, src_lang=src)
    model = AutoModelForSeq2SeqLM.from_pretrained(a.model).eval()
    jobs = [json.loads(l) for l in open(getattr(a, "in"), encoding="utf-8") if l.strip()]
    out = open(a.out, "w", encoding="utf-8")
    for k in range(0, len(jobs), 16):
        batch = jobs[k:k + 16]
        enc = tok([j["text"] for j in batch], return_tensors="pt", padding=True, truncation=True, max_length=256)
        with torch.no_grad():
            gen = model.generate(**enc, forced_bos_token_id=tok.convert_tokens_to_ids(tgt), max_new_tokens=256, num_beams=4)
        for j, t in zip(batch, tok.batch_decode(gen, skip_special_tokens=True)):
            out.write(json.dumps({"key": j["key"], "text": t}, ensure_ascii=False) + "\n")
        sys.stdout.write(json.dumps({"progress": round(min(1.0, (k + 16) / len(jobs)), 3)}) + "\n")
        sys.stdout.flush()
    out.close()
    print(json.dumps({"done": len(jobs)}))


if __name__ == "__main__":
    main()
