"""The agent contract: envelope shape, CLI, registry docs and MCP stay in sync."""

import io
import json
import sys
from pathlib import Path

import pytest

from recomp import cli, mcp_server, registry

REPO = Path(__file__).resolve().parents[2]


def run_cli(argv, capsys):
    code = cli.main(argv)
    out = capsys.readouterr().out
    return code, json.loads(out)


def test_cli_envelope_ok_and_error(proj, capsys):
    code, env = run_cli(["--project", str(proj), "context"], capsys)
    assert code == 0 and env["ok"] and env["verb"] == "context"
    code, env = run_cli(["--project", str(proj), "ui", "show"], capsys)
    assert code == 2  # argparse usage error: missing ref
    code, env = run_cli(["--project", str(proj), "nonsense", "verb"], capsys)
    assert code == 2 and env["error"]["code"] == "E_USAGE"


def test_no_project_is_clean_error(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    code, env = run_cli(["context"], capsys)
    assert code == 3 and env["error"]["code"] == "E_NO_PROJECT" and "hint" in env["error"]


def test_invalid_input_lists_fields(proj):
    env = registry.run("op.log", {"limit": "many"}, project_arg=str(proj))
    assert not env["ok"] and env["error"]["code"] == "E_INVALID"
    assert env["error"]["data"][0]["field"] == "limit"


def test_every_verb_documented():
    verbs = registry.load_all()
    for v in verbs.values():
        assert v.summary and v.summary != v.name, v.name
        assert v.effect in registry.EFFECTS


def test_mcp_tools_match_registry():
    names = {t.name for t in mcp_server.tools()}
    expected = {mcp_server.tool_name(n) for n in registry.load_all() if n != "setup.shim"}
    assert names == expected
    for t in mcp_server.tools():
        assert t.input_schema["type"] == "object"
        assert "project" in t.input_schema["properties"]


def test_mcp_call_runs_verb(proj):
    env = mcp_server.call("context", {"project": str(proj)})
    assert env["ok"]


def test_verbs_doc_is_current():
    from scripts.gen_docs import render_verbs
    doc = (REPO / "docs" / "VERBS.md").read_text(encoding="utf-8")
    assert doc == render_verbs(), "docs/VERBS.md is stale: run `python scripts/gen_docs.py`"


def test_input_file_list_becomes_items(proj, tmp_path, capsys):
    f = tmp_path / "in.json"
    f.write_text(json.dumps({"text": "from file"}), encoding="utf-8")
    code, env = run_cli(["--project", str(proj), "--input", str(f), "ui", "ask", "--refs", "C1,C2"], capsys)
    assert code == 0 and env["data"]["text"] == "from file" and env["data"]["refs"] == ["C1", "C2"]


def test_agent_kit_install(tmp_path):
    from recomp.verbs import agentkit
    written = agentkit.install(tmp_path)
    assert "AGENTS.md" in written and (tmp_path / ".mcp.json").exists()
    claude = tmp_path / "CLAUDE.md"
    claude.write_text(claude.read_text(encoding="utf-8") + "\nmy own note\n", encoding="utf-8")
    agentkit.install(tmp_path)
    assert "my own note" in claude.read_text(encoding="utf-8")
    skills = list((tmp_path / ".claude" / "skills").glob("*/SKILL.md"))
    assert len(skills) == 6
    for s in skills:
        head = s.read_text(encoding="utf-8").split("---")[1]
        assert "name:" in head and "description:" in head
