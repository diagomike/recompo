"""``recomp worker run --project P [--idle 30]``: the per-project job runner process."""

from __future__ import annotations

import argparse

from .jobs import serve


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="recomp worker run")
    p.add_argument("--project", required=True)
    p.add_argument("--idle", type=float, default=30.0, help="Exit after this many idle seconds")
    a = p.parse_args(argv)
    n = serve(a.project, idle_exit=a.idle)
    print(f"runner done: {n} job(s)")
    return 0
