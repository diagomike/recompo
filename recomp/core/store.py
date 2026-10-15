"""The project database: connection, row codec, the precedence guard and the operation log.

Every write happens inside ``with db.op(verb, actor) as tx:``. The transaction records each
row's before and after state, so :func:`undo` and :func:`redo` can reverse it, and appends an
``event`` row that the studio server streams to the viewer.

Precedence: ``user`` > ``agent`` > ``machine``. A field last written by a higher-ranked actor
cannot be overwritten (or its row deleted) by a lower-ranked one; the store raises
``E_PRECEDENCE`` instead of relying on callers to remember.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ..envelope import RecompError
from . import schema
from .ids import ulid

RANK = {"machine": 0, "agent": 1, "user": 2}
SKIP_PROV = {"id", "ref", "created_at", "updated_at", "created_by", "prov"}


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _enc(table: str, col: str, value: Any) -> Any:
    if col in schema.JSON_COLS.get(table, ()) and value is not None and not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return int(value)
    return value


def decode(table: str, row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for col in schema.JSON_COLS.get(table, ()):
        if col in out and isinstance(out[col], str):
            try:
                out[col] = json.loads(out[col])
            except json.JSONDecodeError:
                pass
    return out


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for i, sql in enumerate(schema.MIGRATIONS[version:], start=version + 1):
        conn.execute("BEGIN IMMEDIATE")
        try:
            for stmt in _split_sql(sql):
                conn.execute(stmt)
            conn.execute(f"PRAGMA user_version={i}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _split_sql(sql: str) -> list[str]:
    """Split a migration script into statements, keeping trigger bodies whole."""
    out, buf, depth = [], [], 0
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        buf.append(line)
        upper = stripped.upper()
        if upper.startswith("CREATE TRIGGER"):
            depth += 1
        if depth and upper.startswith("END;"):
            depth -= 1
            out.append("\n".join(buf))
            buf = []
            continue
        if not depth and stripped.endswith(";"):
            out.append("\n".join(buf))
            buf = []
    if buf and "".join(buf).strip():
        out.append("\n".join(buf))
    return out


class Tx:
    """One verb's write transaction. Collects changes for the operation log."""

    def __init__(self, db: "Database", verb: str, actor: str, args: dict | None):
        self.db = db
        self.conn = db.conn
        self.verb = verb
        self.actor = actor
        self.args = args or {}
        self.changes: list[dict] = []
        self.refs: list[str] = []
        self.summary = ""
        self.redoable = True
        self.events: list[tuple[str, dict]] = []
        self.force = False
        self.op_id: str | None = None

    # ---- reads (inside the transaction) ----
    def get(self, table: str, id_: Any) -> dict | None:
        return self.db.get(table, id_)

    def one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def all(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    # ---- writes ----
    def next_ref(self, kind: str) -> str:
        row = self.conn.execute("SELECT next FROM refseq WHERE kind=?", (kind,)).fetchone()
        n = row[0] if row else 1
        self.conn.execute("INSERT INTO refseq(kind, next) VALUES(?, ?) ON CONFLICT(kind) DO UPDATE SET next=?",
                          (kind, n + 1, n + 1))
        return f"{kind}{n}"

    def insert(self, table: str, row: dict, ref_kind: str | None = None, log: bool = True) -> dict:
        row = dict(row)
        now = time.time()
        if table in schema.EDITORIAL:
            if table != "segment":
                row.setdefault("id", ulid())
            if ref_kind and not row.get("ref"):
                row["ref"] = self.next_ref(ref_kind)
            elif table in schema.REF_PREFIX and "ref" not in row:
                row["ref"] = self.next_ref(schema.REF_PREFIX[table])
            row.setdefault("created_at", now)
            row.setdefault("updated_at", now)
            row.setdefault("created_by", self.actor)
            row["prov"] = {k: self.actor for k in row if k not in SKIP_PROV}
        cols = list(row)
        sql = f"INSERT INTO {q(table)} ({', '.join(q(c) for c in cols)}) VALUES ({', '.join('?' for _ in cols)})"
        cur = self.conn.execute(sql, [_enc(table, c, row[c]) for c in cols])
        pk = row.get("id", cur.lastrowid)
        fresh = self.db.get(table, pk)
        if log:
            self.changes.append({"table": table, "id": pk, "before": None, "after": fresh})
            if fresh and fresh.get("ref"):
                self.refs.append(fresh["ref"])
        return fresh

    def update(self, table: str, id_: Any, fields: dict, log: bool = True) -> dict:
        before = self.db.get(table, id_)
        if before is None:
            raise RecompError("E_NOT_FOUND", f"{table} {id_!r} not found")
        fields = {k: v for k, v in fields.items() if k not in SKIP_PROV}
        changed = {k: v for k, v in fields.items() if _norm(before.get(k)) != _norm(v)}
        if not changed:
            return before
        if table in schema.EDITORIAL:
            self._guard(table, before, changed.keys())
            prov = dict(before.get("prov") or {})
            for k in changed:
                prov[k] = self.actor
            changed_db = dict(changed, prov=prov, updated_at=time.time())
        else:
            changed_db = dict(changed)
        sets = ", ".join(f"{q(c)}=?" for c in changed_db)
        pk = "id"
        self.conn.execute(f"UPDATE {q(table)} SET {sets} WHERE {q(pk)}=?",
                          [_enc(table, c, v) for c, v in changed_db.items()] + [id_])
        after = self.db.get(table, id_)
        if log:
            self.changes.append({"table": table, "id": id_, "before": before, "after": after})
            if after.get("ref"):
                self.refs.append(after["ref"])
        return after

    def delete(self, table: str, id_: Any, log: bool = True) -> dict:
        before = self.db.get(table, id_)
        if before is None:
            raise RecompError("E_NOT_FOUND", f"{table} {id_!r} not found")
        if table in schema.EDITORIAL:
            self._guard_row(table, before)
        if log:
            # Capture op-logged children first so undo can restore them in order.
            for child_table, fk in schema.CHILDREN.get(table, []):
                for crow in self.all(f"SELECT id FROM {q(child_table)} WHERE {q(fk)}=?", (id_,)):
                    self.delete(child_table, crow["id"], log=True)
        self.conn.execute(f"DELETE FROM {q(table)} WHERE id=?", (id_,))
        if log:
            self.changes.append({"table": table, "id": id_, "before": before, "after": None})
            if before.get("ref"):
                self.refs.append(before["ref"])
        return before

    def event(self, kind: str, payload: dict) -> None:
        self.events.append((kind, payload))

    # ---- precedence ----
    def _guard(self, table: str, before: dict, fields) -> None:
        if self.force:
            return
        prov = before.get("prov") or {}
        mine = RANK.get(self.actor, 0)
        blocked = [f for f in fields if RANK.get(prov.get(f, "machine"), 0) > mine]
        if blocked:
            ref = before.get("ref") or before.get("id")
            owner = max((prov.get(f, "machine") for f in blocked), key=lambda a: RANK.get(a, 0))
            raise RecompError(
                "E_PRECEDENCE",
                f"{ref}: field(s) {', '.join(sorted(blocked))} were written by the {owner}; "
                f"the {self.actor} cannot overwrite them",
                hint="Ask the user. If they confirm in chat, repeat the command with --as-user.",
                data={"ref": ref, "fields": sorted(blocked), "owner": owner},
            )

    def _guard_row(self, table: str, before: dict) -> None:
        if self.force:
            return
        creator = before.get("created_by", "machine")
        prov = before.get("prov") or {}
        top = max([RANK.get(creator, 0)] + [RANK.get(a, 0) for a in prov.values()])
        if top > RANK.get(self.actor, 0):
            ref = before.get("ref") or before.get("id")
            raise RecompError(
                "E_PRECEDENCE",
                f"{ref} contains work by a higher-precedence actor; the {self.actor} cannot delete it",
                hint="Ask the user. If they confirm in chat, repeat the command with --as-user.",
                data={"ref": ref},
            )


def _norm(v: Any) -> Any:
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True, ensure_ascii=False)
    if isinstance(v, bool):
        return int(v)
    return v


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.conn = connect(path)

    def close(self) -> None:
        self.conn.close()

    def get(self, table: str, id_: Any) -> dict | None:
        return decode(table, self.conn.execute(f"SELECT * FROM {q(table)} WHERE id=?", (id_,)).fetchone())

    def by_ref(self, table: str, ref: str) -> dict | None:
        return decode(table, self.conn.execute(f"SELECT * FROM {q(table)} WHERE ref=?", (ref,)).fetchone())

    def rows(self, table: str, sql: str = "", params: tuple | list = ()) -> list[dict]:
        cur = self.conn.execute(f"SELECT * FROM {q(table)} {sql}", params)
        return [decode(table, r) for r in cur.fetchall()]

    def all(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def scalar(self, sql: str, params: tuple | list = ()) -> Any:
        row = self.conn.execute(sql, params).fetchone()
        return row[0] if row else None

    def emit(self, kind: str, payload: dict) -> int:
        """Append an event outside an op (job progress, viewer state)."""
        cur = self.conn.execute("INSERT INTO event(time, kind, payload) VALUES(?,?,?)",
                                (time.time(), kind, json.dumps(payload, ensure_ascii=False)))
        return cur.lastrowid

    @contextmanager
    def op(self, verb: str, actor: str, args: dict | None = None, force: bool = False) -> Iterator[Tx]:
        tx = Tx(self, verb, actor, args)
        tx.force = force
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield tx
            op_id = None
            if tx.changes:
                op_id = ulid()
                # A new op ends any pending redo chain.
                self.conn.execute("UPDATE op SET state='dead' WHERE state='undone'")
                refs = list(dict.fromkeys(tx.refs))
                self.conn.execute(
                    "INSERT INTO op(id, time, actor, verb, args, summary, changes, refs, redoable) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (op_id, time.time(), actor, verb, json.dumps(_jsonable(tx.args), ensure_ascii=False),
                     tx.summary, json.dumps(tx.changes, ensure_ascii=False, default=str),
                     json.dumps(refs), int(tx.redoable)))
                tables = sorted({c["table"] for c in tx.changes})
                self.conn.execute("INSERT INTO event(time, kind, payload) VALUES(?,?,?)",
                                  (time.time(), "op", json.dumps({"op": op_id, "verb": verb, "actor": actor,
                                                                  "refs": refs, "tables": tables,
                                                                  "summary": tx.summary})))
            for kind, payload in tx.events:
                self.conn.execute("INSERT INTO event(time, kind, payload) VALUES(?,?,?)",
                                  (time.time(), kind, json.dumps(payload, ensure_ascii=False)))
            self.conn.execute("COMMIT")
            tx.op_id = op_id
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    # ---- undo / redo ----
    def undo(self, actor: str, force: bool = False) -> dict:
        row = self.conn.execute("SELECT * FROM op WHERE state='done' ORDER BY seq DESC LIMIT 1").fetchone()
        if row is None:
            raise RecompError("E_NOT_FOUND", "nothing to undo")
        op = decode("op", row)
        if RANK.get(op["actor"], 0) > RANK.get(actor, 0) and not force:
            raise RecompError("E_PRECEDENCE", f"the last change ({op['verb']}) was made by the {op['actor']}",
                              hint="Ask the user before undoing their work; then use --as-user.")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            for ch in reversed(op["changes"]):
                self._apply(ch["table"], ch["id"], current_should_be=ch["after"], target=ch["before"], force=force)
            self.conn.execute("UPDATE op SET state='undone' WHERE seq=?", (op["seq"],))
            self.conn.execute("INSERT INTO event(time, kind, payload) VALUES(?,?,?)",
                              (time.time(), "undo", json.dumps({"op": op["id"], "verb": op["verb"],
                                                                "refs": op["refs"]})))
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        return {"undone": op["id"], "verb": op["verb"], "actor": op["actor"], "refs": op["refs"]}

    def redo(self, actor: str, force: bool = False) -> dict:
        row = self.conn.execute("SELECT * FROM op WHERE state='undone' ORDER BY seq ASC LIMIT 1").fetchone()
        if row is None:
            raise RecompError("E_NOT_FOUND", "nothing to redo")
        op = decode("op", row)
        if not op["redoable"]:
            raise RecompError("E_CONFLICT", f"{op['verb']} cannot be redone; run it again instead")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            for ch in op["changes"]:
                self._apply(ch["table"], ch["id"], current_should_be=ch["before"], target=ch["after"], force=force)
            self.conn.execute("UPDATE op SET state='done' WHERE seq=?", (op["seq"],))
            self.conn.execute("INSERT INTO event(time, kind, payload) VALUES(?,?,?)",
                              (time.time(), "redo", json.dumps({"op": op["id"], "verb": op["verb"],
                                                                "refs": op["refs"]})))
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        return {"redone": op["id"], "verb": op["verb"], "refs": op["refs"]}

    def _apply(self, table: str, id_: Any, current_should_be: dict | None, target: dict | None,
               force: bool) -> None:
        current = self.get(table, id_)
        if not force and _row_key(current) != _row_key(current_should_be):
            raise RecompError("E_CONFLICT", f"{table} {id_} changed since; undo/redo would overwrite newer work",
                              hint="Inspect `recomp op log`; use --force only if the user agrees.")
        if target is None:
            if current is not None:
                self.conn.execute(f"DELETE FROM {q(table)} WHERE id=?", (id_,))
            return
        cols = list(target)
        values = [_enc(table, c, target[c]) for c in cols]
        if current is None:
            self.conn.execute(f"INSERT INTO {q(table)} ({', '.join(q(c) for c in cols)}) "
                              f"VALUES ({', '.join('?' for _ in cols)})", values)
        else:
            self.conn.execute(f"UPDATE {q(table)} SET {', '.join(f'{q(c)}=?' for c in cols)} WHERE id=?",
                              values + [id_])


def _row_key(row: dict | None) -> str | None:
    if row is None:
        return None
    return json.dumps({k: v for k, v in row.items() if k != "updated_at"}, sort_keys=True, default=str)


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return json.loads(json.dumps(value, default=str))
