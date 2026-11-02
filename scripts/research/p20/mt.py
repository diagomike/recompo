"""P20 offline MT wrappers (CTranslate2): NLLB-200 1.3B (the forward system, as in recompo's offline route),
M2M-100 418M and MADLAD-400 3B (independent families, used for back-translation).
Models come from the Hugging Face cache (HF_CACHE, default /home/user/models/hf).
"""
from __future__ import annotations
import functools, os
from pathlib import Path
import ctranslate2
from transformers import AutoTokenizer

CACHE = Path(os.environ.get("HF_CACHE", "/home/user/models/hf"))
REPOS = {"nllb": "OpenNMT/nllb-200-distilled-1.3B-ct2-int8", "m2m": "jncraton/m2m100_418M-ct2-int8",
         "madlad": "Heng666/madlad400-3b-mt-ct2-int8"}
NLLB = {"en": "eng_Latn", "es": "spa_Latn", "fr": "fra_Latn", "am": "amh_Ethi", "om": "gaz_Latn", "sw": "swh_Latn", "ti": "tir_Ethi"}


def path(name):
    snaps = CACHE / ("models--" + REPOS[name].replace("/", "--")) / "snapshots"
    return next(snaps.iterdir())


@functools.lru_cache(None)
def load(name):
    p = path(name)
    tok = AutoTokenizer.from_pretrained(p) if name == "nllb" else None
    if name == "m2m":
        from transformers import M2M100Tokenizer
        tok = M2M100Tokenizer(vocab_file=str(p / "vocab.json"), spm_file=str(p / "sentencepiece.bpe.model"))
    if name == "madlad":
        import sentencepiece as spm
        tok = spm.SentencePieceProcessor(model_file=str(next(p.glob("*.model"))))
    return ctranslate2.Translator(str(p), device="cpu", compute_type="int8", inter_threads=1, intra_threads=4), tok


def translate(texts, src, tgt, system="nllb", beam=4):
    tr, tok = load(system)
    if system == "nllb":
        tok.src_lang = NLLB[src]
        toks = [tok.convert_ids_to_tokens(tok.encode(t)) for t in texts]
        res = tr.translate_batch(toks, target_prefix=[[NLLB[tgt]]] * len(texts), beam_size=beam, max_decoding_length=256)
        return [tok.decode(tok.convert_tokens_to_ids(r.hypotheses[0][1:]), skip_special_tokens=True) for r in res]
    if system == "m2m":
        tok.src_lang = src
        toks = [tok.convert_ids_to_tokens(tok.encode(t)) for t in texts]
        res = tr.translate_batch(toks, target_prefix=[[tok.get_lang_token(tgt)]] * len(texts), beam_size=beam, max_decoding_length=256)
        return [tok.decode(tok.convert_tokens_to_ids(r.hypotheses[0][1:]), skip_special_tokens=True) for r in res]
    if system == "madlad":
        toks = [tok.encode(f"<2{tgt}> " + t, out_type=str) + ["</s>"] for t in texts]
        res = tr.translate_batch(toks, beam_size=beam, max_decoding_length=256)
        return [tok.decode(r.hypotheses[0]) for r in res]
    raise ValueError(system)


if __name__ == "__main__":
    import sys, time
    s = ["I think you played the Gunther card too soon.", "She will kill you like a dog in the street.", "Bummer."]
    for tgt in sys.argv[1:] or ["es", "am"]:
        t = time.time(); out = translate(s, "en", tgt); print(tgt, round(time.time() - t, 1), "s", out)
