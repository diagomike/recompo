"""M2M-100 machine translation under the worker python: a second offline MT system, independent of NLLB, for the
LLM dubber's two-view understanding (it covers Amharic, Somali, Swahili, Hausa, Yoruba, … but not Oromo).

    python mt_m2m100.py --model facebook/m2m100_418M --src am --tgt es --in jobs.jsonl --out out.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    for k in ("model", "src", "tgt", "in", "out"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    import torch
    from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

    tok = M2M100Tokenizer.from_pretrained(a.model)
    tok.src_lang = a.src
    model = M2M100ForConditionalGeneration.from_pretrained(a.model).eval()
    jobs = [json.loads(l) for l in open(getattr(a, "in"), encoding="utf-8") if l.strip()]
    out = open(a.out, "w", encoding="utf-8")
    for k in range(0, len(jobs), 16):
        batch = jobs[k:k + 16]
        enc = tok([j["text"] for j in batch], return_tensors="pt", padding=True, truncation=True, max_length=256)
        with torch.no_grad():
            gen = model.generate(**enc, forced_bos_token_id=tok.get_lang_id(a.tgt), max_new_tokens=256, num_beams=4)
        for j, t in zip(batch, tok.batch_decode(gen, skip_special_tokens=True)):
            out.write(json.dumps({"key": j["key"], "text": t}, ensure_ascii=False) + "\n")
        sys.stdout.write(json.dumps({"progress": round(min(1.0, (k + 16) / len(jobs)), 3)}) + "\n")
        sys.stdout.flush()
    out.close()
    print(json.dumps({"done": len(jobs)}))


if __name__ == "__main__":
    main()
