"""The co-work bridge between the viewer and the agent.

The viewer stores what you selected; the agent reads it (``ui selection``), moves your view
(``ui show``) and pins questions for you (``ui ask``). You can leave notes for the agent
(``ui note``). None of this is undoable editorial content; it is shared state with events.
"""

from __future__ import annotations

import json
import time

from pydantic import BaseModel, Field

from ..core.ids import ulid
from ..core.timecode import parse
from ..registry import Ctx, NoInput, verb


def get_state(db, key: str, default=None):
    row = db.one("SELECT value FROM ui_state WHERE key=?", (key,))
    return json.loads(row[0]) if row else default


def set_state(db, key: str, value) -> None:
    db.conn.execute("INSERT INTO ui_state(key, value, updated_at) VALUES(?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                    (key, json.dumps(value, ensure_ascii=False), time.time()))
    db.emit("ui", {"key": key, "value": value})


@verb("ui.selection", NoInput)
def ui_selection(ctx: Ctx, inp: NoInput):
    """What the user currently has selected in the viewer (a time range on a source, and/or refs)."""
    sel = get_state(ctx.db, "selection")
    row = ctx.db.one("SELECT updated_at FROM ui_state WHERE key='selection'")
    if sel and row:
        sel["age_s"] = round(time.time() - row[0])
    return sel or {"empty": True, "hint": "The user has nothing selected in the viewer."}


class SelectIn(BaseModel):
    source: str | None = Field(None, description="Source ref, e.g. S1")
    start: str | None = Field(None, description="Range start (time)")
    end: str | None = Field(None, description="Range end (time)")
    refs: list[str] = Field(default_factory=list, description="Selected refs (cuts, slots, chapters)")
    t: str | None = Field(None, description="Playhead time")


@verb("ui.select", SelectIn, effect="write",
      examples=["recomp ui select --refs C3,C7,C9   # tick cuts in the user's cut bin",
                "recomp ui select --source S1 --start 12:03 --end 12:48"])
def ui_select(ctx: Ctx, inp: SelectIn):
    """Set the shared selection: a time range on a source and/or refs. The viewer records the user's selection here,
    and the agent can select for the user (cuts ticked in the cut bin, a range in a source room)."""
    value = {"source": inp.source, "start": parse(inp.start), "end": parse(inp.end), "refs": inp.refs,
             "t": parse(inp.t), "by": ctx.actor}
    set_state(ctx.db, "selection", value)
    return value


VIEWS = ("home", "sources", "cuts", "search", "journeys", "exports", "translations", "jobs", "activity", "follows", "topics")


class ShowIn(BaseModel):
    ref: str = Field(..., description="What to show: S1, S1.c3, C17, J2, J2#3, X1, T1 (a topic's brief), or a view: "
                                      "home, sources, cuts, search, journeys, exports, translations, jobs, activity, "
                                      "follows, topics",
                     json_schema_extra={"pos": 0})
    at: str | None = Field(None, description="Time to seek to (source time for sources/chapters/cuts)")
    play: bool = Field(False, description="Start playing")
    filter: str | None = Field(None, description="Filters for a list view, e.g. \"source=S1&tag=fear\" or \"q=consciousness\"")
    highlight: str | None = Field(None, description="Point at the button that runs this verb, e.g. export.run")


@verb("ui.show", ShowIn, effect="write",
      examples=["recomp ui show C17", "recomp ui show S1 --at 1:02:10",
                'recomp ui show cuts --filter "source=S2&min=20"', "recomp ui show J1 --highlight export.run"])
def ui_show(ctx: Ctx, inp: ShowIn):
    """Move the user's viewer to a ref or a view (optionally a time, list filters, and a button to point at)."""
    flt = {}
    for part in (inp.filter or "").replace(";", "&").split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            flt[k.strip()] = v.strip()
    ref = inp.ref.lower() if inp.ref.lower() in VIEWS else inp.ref
    value = {"ref": ref, "at": parse(inp.at), "play": inp.play, "filter": flt, "highlight": inp.highlight,
             "by": ctx.actor, "nonce": ulid()}
    set_state(ctx.db, "focus", value)
    return value


class AskIn(BaseModel):
    text: str = Field(..., description="The question for the user", json_schema_extra={"pos": 0})
    refs: list[str] = Field(default_factory=list, description="Refs the question is about")
    options: list[str] = Field(default_factory=list, description="Optional answer choices")


@verb("ui.ask", AskIn, effect="write",
      examples=['recomp ui ask "Keep the laugh at the end of C4?" --refs C4 --options keep,trim'])
def ui_ask(ctx: Ctx, inp: AskIn):
    """Pin a question for the user in the viewer. Answers show up in `recomp ui notes`."""
    asks = get_state(ctx.db, "asks", [])
    item = {"id": ulid(), "text": inp.text, "refs": inp.refs, "options": inp.options, "by": ctx.actor,
            "time": time.time(), "answer": None}
    asks.append(item)
    set_state(ctx.db, "asks", asks[-50:])
    return item


class AnswerIn(BaseModel):
    id: str = Field(..., description="Ask id", json_schema_extra={"pos": 0})
    answer: str = Field(..., description="The answer", json_schema_extra={"pos": 1})


@verb("ui.answer", AnswerIn, effect="write", hidden=True)
def ui_answer(ctx: Ctx, inp: AnswerIn):
    """Answer a pinned question (the viewer calls this)."""
    asks = get_state(ctx.db, "asks", [])
    for a in asks:
        if a["id"] == inp.id:
            a["answer"] = inp.answer
            a["answered_at"] = time.time()
    set_state(ctx.db, "asks", asks)
    return {"id": inp.id, "answer": inp.answer}


class NoteIn(BaseModel):
    text: str = Field(..., description="Note for the agent", json_schema_extra={"pos": 0})
    refs: list[str] = Field(default_factory=list)
    verb: str | None = Field(None, description="A verb the user hands to the agent to run (with args)")
    args: dict = Field(default_factory=dict, description="Its arguments")


@verb("ui.note", NoteIn, effect="write", hidden=True)
def ui_note(ctx: Ctx, inp: NoteIn):
    """Leave a note for the agent (the viewer calls this); with a verb, it is an action handed to the agent."""
    notes = get_state(ctx.db, "notes", [])
    item = {"id": ulid(), "text": inp.text, "refs": inp.refs, "by": ctx.actor, "time": time.time(), "seen": False}
    if inp.verb:
        from ..cli import cli_line
        item["request"] = {"verb": inp.verb, "args": inp.args, "cli": cli_line(inp.verb, inp.args)}
        item["selection"] = get_state(ctx.db, "selection")
    notes.append(item)
    set_state(ctx.db, "notes", notes[-100:])
    return item


class NotesIn(BaseModel):
    mark_seen: bool = Field(True, description="Mark the user's notes as seen")


@verb("ui.notes", NotesIn)
def ui_notes(ctx: Ctx, inp: NotesIn):
    """Open questions you pinned, the user's answers, and notes the user left for you."""
    asks = get_state(ctx.db, "asks", [])
    notes = get_state(ctx.db, "notes", [])
    out = {"answered": [a for a in asks if a.get("answer") is not None][-20:],
           "open_asks": [a for a in asks if a.get("answer") is None],
           "notes": [n for n in notes if not n.get("seen")]}
    if inp.mark_seen and out["notes"]:
        for n in notes:
            n["seen"] = True
        set_state(ctx.db, "notes", notes)
    return out
