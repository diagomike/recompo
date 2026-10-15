"""Create local test accounts on a running local hub; credentials go to <hub data>/seed_users.json.

    python -m hub.seed [--url http://127.0.0.1:8790] [--users ada,ben,cleo]
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
from pathlib import Path

import httpx


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8790")
    ap.add_argument("--users", default="ada,ben,cleo")
    ap.add_argument("--data", default=os.environ.get("RECOMP_HUB_DATA") or str(Path.home() / ".recomp" / "hub"))
    a = ap.parse_args()
    if "127.0.0.1" not in a.url and "localhost" not in a.url:
        raise SystemExit("seed only creates accounts on a local hub")
    path = Path(a.data) / "seed_users.json"
    users = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for h in a.users.split(","):
        if h in users:
            continue
        pw = secrets.token_urlsafe(12)
        r = httpx.post(a.url + "/api/hub/auth/register", json={"handle": h, "password": pw, "display": h.title()}, timeout=20)
        if r.status_code == 200:
            users[h] = pw
        else:
            print(h, r.status_code, r.text[:100])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(users, indent=1), encoding="utf-8")
    print(f"{len(users)} local test account(s) in {path}")


if __name__ == "__main__":
    main()
