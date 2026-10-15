"""Generate docs/VERBS.md from the verb registry (a test fails when it drifts).

    python scripts/gen_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from recomp import registry  # noqa: E402


def _type(prop: dict) -> str:
    if "anyOf" in prop:
        return " | ".join(_type(p) for p in prop["anyOf"] if p.get("type") != "null")
    t = prop.get("type", "")
    if t == "array":
        return f"list[{_type(prop.get('items', {}))}]"
    return t or "any"


def render_verbs() -> str:
    verbs = registry.load_all()
    lines = [
        "# Verbs",
        "",
        "Generated from the registry by `python scripts/gen_docs.py`. Every verb is available as",
        "`recomp <noun> <verb>` (CLI), as the MCP tool `<noun>_<verb>`, and as",
        "`POST /api/verb/<noun>.<verb>` on the studio server. All return the same JSON envelope.",
        "",
        "Effects: `read` (no changes) · `write` (undoable op) · `heavy` (starts a job) ·",
        "`network` (talks to the internet) · `publish` (shares beyond this machine).",
        "",
    ]
    nouns: dict[str, list] = {}
    for v in sorted(verbs.values(), key=lambda x: x.name):
        nouns.setdefault(v.noun, []).append(v)
    lines.append("| Noun | Verbs |")
    lines.append("|---|---|")
    for noun, vs in nouns.items():
        lines.append(f"| `{noun}` | " + ", ".join(f"[`{v.name}`](#{v.name.replace('.', '')})" for v in vs) + " |")
    lines.append("")
    for noun, vs in nouns.items():
        lines.append(f"## {noun}")
        lines.append("")
        for v in vs:
            lines.append(f"### {v.name}")
            lines.append("")
            pos = v.positional()
            cli = "recomp " + v.name.replace(".", " ") + "".join(f" <{p}>" for p in pos)
            lines.append(f"`{cli}` · effect: **{v.effect}**" + (" · hidden (viewer use)" if v.hidden else ""))
            lines.append("")
            lines.append(v.doc)
            lines.append("")
            props = v.schema().get("properties", {})
            required = set(v.schema().get("required", []))
            if props:
                lines.append("| Field | Type | Default | Description |")
                lines.append("|---|---|---|---|")
                for name, prop in props.items():
                    flag = f"<{name}>" if name in pos else "--" + name.replace("_", "-")
                    default = "required" if name in required else repr(prop.get("default", None))
                    desc = (prop.get("description") or "").replace("|", "\\|")
                    lines.append(f"| `{flag}` | {_type(prop)} | {default} | {desc} |")
                lines.append("")
            if v.examples:
                lines.append("```")
                lines.extend(v.examples)
                lines.append("```")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    out = REPO / "docs" / "VERBS.md"
    out.write_text(render_verbs(), encoding="utf-8", newline="\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
