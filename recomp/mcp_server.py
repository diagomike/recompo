"""MCP stdio server: one tool per verb, generated from the registry.

Tool names use underscores (``cut_add``). Every tool accepts the verb's fields plus optional
``project`` and ``as_user``; results are the same JSON envelope the CLI prints.
"""

from __future__ import annotations

import copy
import json

import anyio
import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from . import __version__, registry

INSTRUCTIONS = (
    "Recomposer: operate a media project (sources, transcripts, chapters, cuts, journeys, exports). "
    "Call `context` first. Every tool returns {ok, data | error{code, hint}}. Heavy tools return a job; "
    "use job_wait. E_PRECEDENCE means the user owns that work: ask them, and pass as_user=true only "
    "with their explicit go-ahead. Never publish beyond this machine without asking."
)


def tool_name(verb_name: str) -> str:
    return verb_name.replace(".", "_").replace("-", "_")


def tool_schema(v: registry.Verb) -> dict:
    schema = copy.deepcopy(v.schema())
    schema.setdefault("type", "object")
    props = schema.setdefault("properties", {})
    for prop in props.values():
        prop.pop("pos", None)
    props["project"] = {"type": "string", "description": "Project name or folder (default: RECOMP_PROJECT / current)"}
    props["as_user"] = {"type": "boolean", "description": "Act as the user. Only after the user explicitly agreed in chat."}
    return schema


def tools() -> list[types.Tool]:
    out = []
    for v in sorted(registry.load_all().values(), key=lambda x: x.name):
        if v.name in ("setup.shim",):
            continue
        ann = types.ToolAnnotations(title=v.name, read_only_hint=v.effect == "read",
                                    destructive_hint=v.effect in ("write", "publish"),
                                    idempotent_hint=v.effect == "read")
        desc = v.doc
        if v.examples:
            desc += "\nCLI: " + " | ".join(v.examples[:2])
        out.append(types.Tool(name=tool_name(v.name), description=desc, inputSchema=tool_schema(v),
                              annotations=ann))
    return out


def call(name: str, arguments: dict | None) -> dict:
    by_tool = {tool_name(n): n for n in registry.load_all()}
    args = dict(arguments or {})
    project = args.pop("project", None)
    as_user = bool(args.pop("as_user", False))
    verb_name = by_tool.get(name, name)
    return registry.run(verb_name, args, actor="agent", project_arg=project, as_user=as_user)


def build() -> Server:
    async def on_list_tools(ctx, params):
        return types.ListToolsResult(tools=tools())

    async def on_call_tool(ctx, params: types.CallToolRequestParams):
        env = await anyio.to_thread.run_sync(call, params.name, params.arguments)
        text = json.dumps(env, ensure_ascii=False, default=str)
        return types.CallToolResult(content=[types.TextContent(text=text)], is_error=not env.get("ok"))

    return Server("recomposer", version=__version__, instructions=INSTRUCTIONS,
                  on_list_tools=on_list_tools, on_call_tool=on_call_tool)


async def _serve() -> None:
    server = build()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    anyio.run(_serve)
