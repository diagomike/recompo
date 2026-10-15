"""Worker self-test: copies --in to --out uppercased, reporting progress (checks the remote protocol)."""

import argparse
import json
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
text = open(a.inp, encoding="utf-8").read()
for k in range(3):
    time.sleep(0.2)
    sys.stdout.write(json.dumps({"progress": (k + 1) / 3, "message": f"step {k + 1}"}) + "\n")
    sys.stdout.flush()
open(a.out, "w", encoding="utf-8").write(text.upper())
