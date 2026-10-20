"""Overlays: title cards, lower thirds (who/what/where), pull quotes, free text, endcard text."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..compose import recipe as R
from ..core import refs
from ..core.timecode import parse
from ..envelope import RecompError, Result
from ..registry import Ctx, verb
from .journey import journey_of, mirror

KINDS = ("title", "lower_third", "quote", "text", "endcard", "section")


def brief(db, o: dict) -> dict:
    slot = db.get("slot", o["slot_id"]) if o.get("slot_id") else None
    return {"ref": o["ref"], "kind": o["kind"], "text": o["text"], "slot": refs.slot_ref(db, slot) if slot else None,
            "at": o["at"], "dur": o["dur"], "style": o["style"], "by": o["created_by"]}


class AddIn(BaseModel):
    target: str = Field(..., description="Journey (J1: whole-journey overlay) or slot (J1#3)", json_schema_extra={"pos": 0})
    kind: str = Field("text", description="title | lower_third | quote | text | endcard | section")
    text: str = Field(..., description="Text; use \\n for a second line")
    at: str = Field("0", description="Seconds into the slot (or the journey)")
    dur: float | None = Field(None, description="Seconds shown (default depends on kind)")
    position: str | None = Field(None, description="top | middle | bottom (default by kind)")
    size: float | None = Field(None, description="Relative text size (1.0 = default)")


DEFAULT_DUR = {"title": 3.0, "lower_third": 4.0, "quote": 5.0, "text": 4.0, "endcard": 3.5, "section": 2.5}


@verb("overlay.add", AddIn, effect="write",
      examples=['recomp overlay add J1 --kind title --text "Live long enough"',
                'recomp overlay add J1#2 --kind quote --text "You either die a hero…" --at 1'])
def overlay_add(ctx: Ctx, inp: AddIn):
    """Add text over a journey or one slot: title card, lower third, pull quote, free text."""
    if inp.kind not in KINDS:
        raise RecompError("E_INVALID", f"kind must be one of {KINDS}")
    db = ctx.db
    slot = None
    if "#" in inp.target:
        _, slot = refs.resolve(db, inp.target, "slot")
        j = db.get("journey", slot["journey_id"])
    else:
        j = journey_of(db, inp.target)
    style = {k: v for k, v in {"position": inp.position, "size": inp.size}.items() if v is not None}
    with ctx.op(f"overlay {inp.kind} on {inp.target}") as tx:
        o = tx.insert("overlay", {"journey_id": j["id"], "slot_id": slot["id"] if slot else None, "kind": inp.kind,
                                  "text": inp.text.replace("\\n", "\n"), "style": style, "at": parse(inp.at) or 0.0,
                                  "dur": inp.dur if inp.dur is not None else DEFAULT_DUR[inp.kind]})
    mirror(ctx, j["id"])
    return Result(data=brief(db, o), refs=[o["ref"]])


class AutoIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    replace: bool = Field(True, description="Replace lower thirds made earlier by this verb")
    template: str = Field("{people}{title_sep}{source}", description="Fields: {people} {source} {year} {creator} {cut}")


@verb("overlay.auto-lower-thirds", AutoIn, effect="write", examples=["recomp overlay auto-lower-thirds J1"])
def overlay_auto_lower_thirds(ctx: Ctx, inp: AutoIn):
    """Credit every slot on screen: who is speaking and where it is from (people · source (year))."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    made = []
    with ctx.op(f"lower thirds {j['ref']}") as tx:
        if inp.replace:
            for o in db.rows("overlay", "WHERE journey_id=? AND kind='lower_third'", (j["id"],)):
                if (o["style"] or {}).get("auto") and o["created_by"] != "user":
                    tx.delete("overlay", o["id"])
        prev_src = None
        for it in R.timeline(db, j):
            src = it["source"]
            people = ", ".join(it["cut"]["people"] or [])
            if src["kind"] == "link":
                # Episodes: the title says enough; add the channel only when nobody on screen is the channel.
                name = src["title"]
                for person in it["cut"]["people"] or []:
                    for sep in (" - ", " – ", " | "):  # "… - Anil Seth", "… | Jeffrey Ladish": the guest ends the title
                        if name.endswith(sep + person):
                            name = name[: -len(sep + person)]
                if src.get("creator") and src["creator"] not in name and src["creator"] not in people:
                    name = f"{src['creator']} · {name}"
            else:
                name = src["title"] + (f" ({src['year']})" if src.get("year") else "")
            text = inp.template.format(people=people, title_sep="\n" if people else "", source=name, year=src.get("year") or "",
                                       creator=src.get("creator") or "", cut=it["cut"]["title"])
            if not people and prev_src == src["id"]:
                continue  # same source, nobody named: don't repeat the credit on every slot
            prev_src = src["id"]
            o = tx.insert("overlay", {"journey_id": j["id"], "slot_id": it["id"], "kind": "lower_third", "text": text.strip(),
                                      "style": {"auto": True}, "at": 0.6, "dur": min(4.0, max(2.0, it["dur"] - 1.0))})
            made.append(o)
    mirror(ctx, j["id"])
    return Result(data=[brief(db, o) for o in made], refs=[o["ref"] for o in made])


class EditIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    text: str | None = None
    at: str | None = None
    dur: float | None = None
    kind: str | None = None
    position: str | None = None
    size: float | None = None


@verb("overlay.edit", EditIn, effect="write")
def overlay_edit(ctx: Ctx, inp: EditIn):
    """Change an overlay's text, timing, kind or style."""
    db = ctx.db
    o = refs.resolve(db, inp.ref, "overlay")[1]
    fields = {}
    if inp.text is not None:
        fields["text"] = inp.text.replace("\\n", "\n")
    if inp.at is not None:
        fields["at"] = parse(inp.at)
    if inp.dur is not None:
        fields["dur"] = inp.dur
    if inp.kind is not None:
        fields["kind"] = inp.kind
    if inp.position is not None or inp.size is not None:
        style = dict(o["style"] or {})
        if inp.position is not None:
            style["position"] = inp.position
        if inp.size is not None:
            style["size"] = inp.size
        style.pop("auto", None)
        fields["style"] = style
    with ctx.op(f"edit {o['ref']}") as tx:
        o = tx.update("overlay", o["id"], fields)
    mirror(ctx, o["journey_id"])
    return brief(db, o)


class RefIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})


@verb("overlay.remove", RefIn, effect="write")
def overlay_remove(ctx: Ctx, inp: RefIn):
    """Delete an overlay."""
    db = ctx.db
    o = refs.resolve(db, inp.ref, "overlay")[1]
    with ctx.op(f"remove {o['ref']}") as tx:
        tx.delete("overlay", o["id"])
    mirror(ctx, o["journey_id"])
    return {"removed": o["ref"]}


class ListIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})


@verb("overlay.list", ListIn)
def overlay_list(ctx: Ctx, inp: ListIn):
    """Overlays of a journey."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    return [brief(db, o) for o in db.rows("overlay", "WHERE journey_id=? ORDER BY at", (j["id"],))]
