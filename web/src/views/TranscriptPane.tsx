import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Combine, Download, Eraser, FileText, ListFilter, Mic, Pencil, Replace, Search, Split, Trash2, Users, X } from "lucide-react";
import { clock, verb } from "../api";
import { Act, useActions } from "../actions";
import { Dialog, Disclosure, Empty, Menu, personColors } from "../ui";

type Seg = { idx: number; start: number; end: number; text: string; speaker: string | null; words: [number, number, string][] | null };
type Sel = { a: number; b: number } | null;

// "free will" stays a phrase; other words must all appear in the line (any order, any case).
function terms(q: string): string[] {
  const out: string[] = [];
  q.replace(/"([^"]+)"|(\S+)/g, (_m, phrase, word) => { out.push(String(phrase || word).toLowerCase()); return ""; });
  return out.filter(Boolean);
}
const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function Marked({ text, ts }: { text: string; ts: string[] }) {
  if (!ts.length) return <>{text}</>;
  const re = new RegExp(`(${ts.map(escapeRe).join("|")})`, "gi");
  return <>{text.split(re).map((part, k) => (k % 2 ? <mark key={k}>{part}</mark> : part))}</>;
}

// The transcript beside the player: read along, select lines, and fix them in place.
// Every edit is a transcript or speaker verb (one undo each); the agent runs the same ones in bulk.
export default function TranscriptPane({ data, t, sel, seek, setSel, panel, query, onHits }: {
  data: any; t: number; sel: Sel; seek: (t: number, play?: boolean) => void; setSel: (s: Sel) => void; panel: string | null;
  query?: string | null; onHits?: (times: number[]) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const userScroll = useRef(0);
  const anchor = useRef<number | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [find, setFind] = useState(query || "");
  const [only, setOnly] = useState(false);
  const [pos, setPos] = useState(-1);
  const findBox = useRef<HTMLInputElement>(null);
  useEffect(() => { if (query != null) setFind(query); }, [query]);
  const [tool, setTool] = useState<null | "replace" | "replace-lines" | "speakers">(panel === "speakers" ? "speakers" : null);
  const [delLines, setDelLines] = useState<string | null>(null);
  const { run } = useActions();
  const segs: Seg[] = data.segments;
  const tr = data.transcript;
  const voices: Record<string, { name: string | null }> = data.voices || {};
  const who = (label: string | null) => (label ? voices[label]?.name || label : null);
  // the same names as the room's lanes, so a person has one colour in both
  const whoColor = useMemo(() => personColors([...(data.turns || []).map((x: any) => who(x.label)!),
                                               ...segs.filter((s) => s.speaker).map((s) => who(s.speaker)!)]),
                           [data.turns, segs, voices]);

  const cur = useMemo(() => {
    let lo = 0, hi = segs.length - 1, ans = -1;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (segs[m].start <= t) { ans = m; lo = m + 1; } else hi = m - 1; }
    return ans;
  }, [t, segs]);
  useEffect(() => {
    if (Date.now() - userScroll.current < 4000 || cur < 0 || editing != null) return;
    const el = box.current?.querySelector(`[data-i="${cur}"]`) as HTMLElement | null;
    if (el && box.current) {
      const top = el.offsetTop - box.current.clientHeight / 3;
      if (Math.abs(box.current.scrollTop - top) > box.current.clientHeight / 3) box.current.scrollTop = top;
    }
  }, [cur, editing]);

  const selected = sel ? segs.filter((s) => s.end > sel.a + 0.01 && s.start < sel.b - 0.01) : [];
  const lines = selected.length ? `${selected[0].idx}-${selected[selected.length - 1].idx}` : "";
  const q = find.trim().toLowerCase();
  const ts = useMemo(() => terms(q), [q]);
  // A term matches in the line itself, or (for phrases) starting in it and running on into the next line,
  // which is how rolling auto-captions break sentences.
  const hitSet = useMemo(() => {
    const out = new Set<number>();
    if (!ts.length) return out;
    const low = segs.map((s) => s.text.toLowerCase());
    low.forEach((line, i) => {
      const next = low[i + 1] || "";
      if (ts.every((x) => line.includes(x) || (x.includes(" ") && (line + " " + next).includes(x) && !next.includes(x)))) out.add(i);
    });
    return out;
  }, [ts, segs]);
  const hitIdx = useMemo(() => Array.from(hitSet).sort((a, b) => a - b), [hitSet]);
  useEffect(() => setPos(-1), [q]);
  useEffect(() => { onHits?.(hitIdx.map((i) => segs[i].start)); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [hitIdx]);
  // Jump to a hit: select its line, seek the player there, and bring the line into view.
  const jump = (k: number) => {
    if (!hitIdx.length) return;
    const p = ((k % hitIdx.length) + hitIdx.length) % hitIdx.length;
    const s = segs[hitIdx[p]];
    setPos(p);
    setSel({ a: s.start, b: s.end });
    seek(s.start);
    userScroll.current = Date.now();
    window.setTimeout(() => {
      const el = box.current?.querySelector(`[data-i="${hitIdx[p]}"]`) as HTMLElement | null;
      if (el && box.current) box.current.scrollTop = el.offsetTop - box.current.clientHeight / 3;
    }, 30);
  };
  const nextFromPlayhead = (dir: 1 | -1) => {
    if (!hitIdx.length) return;
    if (pos >= 0) return jump(pos + dir);
    const after = hitIdx.findIndex((i) => segs[i].start > t + 0.2);
    jump(dir === 1 ? (after < 0 ? 0 : after) : (after < 0 ? hitIdx.length - 1 : after - 1));
  };
  // Ctrl+F (or F3) searches this source instead of the browser page; Ctrl+H opens find and replace.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (document.querySelector(".modal") || !tr) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "h") { e.preventDefault(); setTool("replace"); return; }
      if (((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") || e.key === "F3") {
        e.preventDefault();
        if (e.key === "F3" && hitIdx.length) nextFromPlayhead(e.shiftKey ? -1 : 1);
        else { findBox.current?.focus(); findBox.current?.select(); }
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  });

  const chapStarts = new Map<number, any>();
  for (const c of data.chapters) {
    const i = segs.findIndex((s) => s.end > c.start);
    if (i >= 0 && !chapStarts.has(i)) chapStarts.set(i, c);
  }

  const save = async (s: Seg) => {
    const text = draft.trim();
    setEditing(null);
    if (!text || text === s.text) return;
    await run("transcript.edit-segment", { ref: tr.ref, idx: s.idx, text }, { label: `Edit line #${s.idx}` });
  };

  if (!tr) {
    return (
      <div className="transcript" style={{ padding: 12 }}>
        <Empty icon={<FileText size={16} />} title="No transcript yet"
               actions={data.source.kind === "link"
                 ? <Act verb="transcript.fetch-captions" args={{ ref: data.source.ref }} small primary agent>Fetch captions</Act>
                 : <Act verb="transcript.asr" args={{ ref: data.source.ref }} small primary agent title="A background job on this computer">Transcribe (ASR)</Act>}>
          The transcript lets you find moments by what is said, select by lines and cut on word edges.
        </Empty>
      </div>
    );
  }
  const canSplit = selected.length === 1 && t > selected[0].start + 0.2 && t < selected[0].end - 0.2;
  const isLink = data.source.kind === "link";
  return (
    <div className="transcript tpane">
      <div className="thead">
        <div className="row nowrap findrow" role="toolbar" aria-label="Transcript commands" style={{ gap: 4 }}>
          <select className="input small" value={tr.ref} aria-label="Transcript" style={{ maxWidth: 150, flex: "none" }}
                  data-tip={`The transcript in use: ${segs.length} lines${tr.has_words ? ", with word timing" : ""}. Pick another to switch.`}
                  data-tip-cmd={`recomp transcript set-primary ${tr.ref}`}
                  onChange={(e) => run("transcript.set-primary", { ref: e.target.value }, { label: `Use ${e.target.value}` })}>
            {(data.transcripts || [tr]).map((x: any) => <option key={x.ref} value={x.ref}>{x.ref} · {x.origin} · {x.language}{x.label ? ` · ${x.label.slice(0, 28)}` : ""}</option>)}
          </select>
          <div className="search grow" style={{ position: "relative", display: "flex" }}>
            <Search size={13} style={{ position: "absolute", left: 6, top: "50%", transform: "translateY(-50%)", color: "var(--faint)", pointerEvents: "none" }} />
            <input ref={findBox} className={"input small grow" + (q ? " on" : "")} style={{ paddingLeft: 22 }} placeholder='Find in this source · words or "a phrase"' value={find}
                   onChange={(e) => setFind(e.target.value)} data-filter="tq" aria-label="Search this transcript" data-tip="Find in this source" data-tip-key="Ctrl+F"
                   onKeyDown={(e) => {
                     if (e.key === "Enter") { e.preventDefault(); nextFromPlayhead(e.shiftKey ? -1 : 1); }
                     if (e.key === "ArrowDown") { e.preventDefault(); nextFromPlayhead(1); }
                     if (e.key === "ArrowUp") { e.preventDefault(); nextFromPlayhead(-1); }
                     if (e.key === "Escape") { setFind(""); setOnly(false); }
                   }} />
          </div>
          {q && <span className={"chip" + (hitIdx.length ? "" : " failed")} style={{ flex: "none" }}>{hitIdx.length ? `${pos >= 0 ? pos + 1 : "–"}/${hitIdx.length}` : "none"}</span>}
          {q && <button className="btn ghost small icon" disabled={!hitIdx.length} onClick={() => nextFromPlayhead(-1)} aria-label="Previous match" data-tip="Previous match" data-tip-key="Shift+Enter"><ChevronUp size={13} /></button>}
          {q && <button className="btn ghost small icon" disabled={!hitIdx.length} onClick={() => nextFromPlayhead(1)} aria-label="Next match" data-tip="Next match" data-tip-key="Enter · F3"><ChevronDown size={13} /></button>}
          {q && <button className={"btn ghost small icon" + (only ? " on" : "")} onClick={() => setOnly(!only)} aria-label="Only matching lines" aria-pressed={only} data-tip="Show only the matching lines"><ListFilter size={13} /></button>}
          {q && <button className="btn ghost small icon" onClick={() => { setFind(""); setOnly(false); }} aria-label="Clear the search" data-tip="Clear the search" data-tip-key="Esc"><X size={12} /></button>}
          <Menu small label="Transcript actions" items={[
            { header: `${tr.ref} · ${segs.length} lines` },
            { label: "Find and replace…", icon: <Replace size={14} />, desc: "Preview first; this transcript, every source, or the selected lines", onSelect: () => setTool("replace") },
            { label: "Speakers…", icon: <Users size={14} />, desc: "Name voices, apply >> turn marks, diarise", onSelect: () => setTool("speakers") },
            { label: "Clean every line", icon: <Eraser size={14} />, desc: "Removes >> marks, [tags], ♪, doubled words; undo brings them back",
              onSelect: () => run("transcript.clean", { ref: tr.ref }, { label: `Clean ${tr.ref}` }) },
            "sep",
            isLink ? { label: "Fetch captions again", icon: <Download size={14} />, desc: "From the platform, as another transcript", onSelect: () => run("transcript.fetch-captions", { ref: data.source.ref }, { label: "Fetch captions" }) }
              : { label: "Transcribe again (ASR)", icon: <Mic size={14} />, desc: "A background job; makes another transcript", onSelect: () => run("transcript.asr", { ref: data.source.ref }, { label: "Transcribe" }) },
          ]} />
        </div>
        {!!selected.length && (
          <div className="linebar" role="toolbar" aria-label="Selected lines">
            <b className="nowrap">{selected.length === 1 ? `Line #${selected[0].idx}` : `Lines #${lines}`}</b>
            <SpeakerSet trRef={tr.ref} lines={lines} people={data.people} />
            {selected.length > 1 && <Act verb="transcript.merge" args={{ ref: tr.ref, lines }} small ghost icon={<Combine size={12} />} title="Join the selected lines into one">Merge</Act>}
            {canSplit && <Act verb="transcript.split" args={{ ref: tr.ref, idx: selected[0].idx, at: t.toFixed(2) }} small ghost icon={<Split size={12} />} title="Split this line at the playhead">Split at {clock(t, 0)}</Act>}
            <div className="spacer" />
            <Menu small label="More for the selected lines" items={[
              { label: "Clean these lines", icon: <Eraser size={14} />, desc: "Removes >> marks, [tags], ♪, doubled words", onSelect: () => run("transcript.clean", { ref: tr.ref, lines }, { label: `Clean #${lines}` }) },
              { label: "Find and replace in these lines…", icon: <Replace size={14} />, onSelect: () => setTool("replace-lines") },
              ...(selected.length === 1 && !canSplit ? [{ label: "Split at the playhead", icon: <Split size={14} />, disabled: true, desc: "Move the playhead inside the line first", onSelect: () => {} }] : []),
              "sep",
              { label: `Delete ${selected.length === 1 ? "this line" : `${selected.length} lines`}…`, icon: <Trash2 size={14} />, danger: true, desc: "Undo brings them back", onSelect: () => setDelLines(lines) },
            ]} />
            <button className="btn ghost small icon" onClick={() => setSel(null)} aria-label="Clear the selection" data-tip="Clear the selection" data-tip-key="Esc"><X size={12} /></button>
          </div>
        )}
      </div>
      {(tool === "replace" || tool === "replace-lines") && <ReplaceDialog trRef={tr.ref} find={find} setFind={setFind} lines={lines} inLines={tool === "replace-lines"} onClose={() => setTool(null)} />}
      {tool === "speakers" && <SpeakersDialog data={data} lines={lines} onClose={() => setTool(null)} />}
      {delLines && (
        <Dialog title={`Delete line${delLines.includes("-") ? "s" : ""} #${delLines}?`} sub="The text and its word timings go; undo (Ctrl+Z) brings them back." onClose={() => setDelLines(null)}
                footer={<><div className="spacer" /><button className="btn" onClick={() => setDelLines(null)}>Keep</button>
                  <Act verb="transcript.delete" args={{ ref: tr.ref, lines: delLines }} className="danger" onDone={() => { setDelLines(null); setSel(null); }}>Delete</Act></>}>
          <p className="muted2" style={{ margin: 0 }}>{selected.slice(0, 3).map((s) => s.text).join(" ").slice(0, 200)}{selected.length > 3 ? " …" : ""}</p>
        </Dialog>
      )}
      <div className="tbody" ref={box} onWheel={() => (userScroll.current = Date.now())}>
        {only && !hitIdx.length && <div className="muted2" style={{ padding: 12 }}>No line matches “{find}”.</div>}
        {segs.map((s, i) => {
          const c = chapStarts.get(i);
          const inSel = sel && s.end > sel.a + 0.01 && s.start < sel.b - 0.01;
          const hit = hitSet.has(i);
          if (only && !hit) return null;
          const focused = pos >= 0 && hitIdx[pos] === i;
          return (
            <div key={s.idx}>
              {c && !only && <div className="chaphead">{c.ref} {c.title}<span className="s">{clock(c.start, 0)}</span></div>}
              <div className={"seg" + (i === cur ? " now" : "") + (inSel ? " sel" : "") + (hit ? " hit" : "") + (focused ? " hitnow" : "")} data-i={i}
                   onClick={(e) => {
                     if (editing === s.idx) return;
                     if (e.shiftKey && anchor.current != null) {
                       const a0 = segs.find((x) => x.idx === anchor.current)!;
                       setSel({ a: Math.min(a0.start, s.start), b: Math.max(a0.end, s.end) });
                     } else { anchor.current = s.idx; setSel({ a: s.start, b: s.end }); seek(s.start); }
                   }}
                   onDoubleClick={() => { setEditing(s.idx); setDraft(s.text); }}>
                <span className="t">#{s.idx} {clock(s.start, 0)}</span>
                {editing === s.idx ? (
                  <span>
                    <textarea className="input lineedit" autoFocus value={draft} rows={Math.min(5, Math.ceil(draft.length / 48) + 1)}
                              onChange={(e) => setDraft(e.target.value)} onClick={(e) => e.stopPropagation()}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); save(s); }
                                if (e.key === "Escape") setEditing(null);
                              }} onBlur={() => save(s)} />
                    <span className="muted2">Enter saves · Esc cancels · word timings follow the text</span>
                  </span>
                ) : (
                  <span className="segtext">
                    {s.speaker && <b className="who" style={{ "--who": whoColor[who(s.speaker)!] } as React.CSSProperties}>{who(s.speaker)}: </b>}
                    {i === cur && s.words && !hit ? s.words.map((w, k) => <span key={k} className={"w" + (t >= w[0] && t < w[1] ? " now" : "")}>{w[2]} </span>)
                      : <Marked text={s.text} ts={hit ? ts : []} />}
                    <button className="btn ghost small editbtn" title="Edit this line (or double-click)" onClick={(e) => { e.stopPropagation(); setEditing(s.idx); setDraft(s.text); }}><Pencil size={11} /></button>
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SpeakerSet({ trRef, lines, people }: { trRef: string; lines: string; people: any[] }) {
  const [name, setName] = useState("");
  return (
    <span className="act-wrap">
      <input className="input small" list="people-list" style={{ width: 130 }} placeholder="Speaker…" value={name} onChange={(e) => setName(e.target.value)} />
      <datalist id="people-list">{people.map((p) => <option key={p.ref} value={p.name} />)}</datalist>
      <Act verb="speaker.assign" args={{ ref: trRef, name, lines }} small disabled={!name.trim()} onDone={() => setName("")}>Name</Act>
    </span>
  );
}

function ReplaceDialog({ trRef, find, setFind, lines, inLines, onClose }: {
  trRef: string; find: string; setFind: (v: string) => void; lines: string; inLines: boolean; onClose: () => void;
}) {
  const [repl, setRepl] = useState("");
  const [scope, setScope] = useState<"this" | "all" | "lines">(inLines && lines ? "lines" : "this");
  const [whole, setWhole] = useState(false);
  const [preview, setPreview] = useState<any>(null);
  const args = { ref: scope === "all" ? "all" : trRef, find, replace: repl, whole, ...(scope === "lines" && lines ? { lines } : {}) };
  useEffect(() => setPreview(null), [find, repl, scope, whole]);
  const dry = async () => { const e = await verb("transcript.replace", { ...args, dry_run: true }); setPreview(e.ok ? e.data : { error: e.error?.message }); };
  return (
    <Dialog title="Find and replace" sub="Preview the changes, then replace. One undo takes the whole replace back." icon={<Replace size={16} />} wide onClose={onClose}
            footer={<>
              <span className="muted2">{preview && !preview.error ? `${preview.replaced || 0} line${preview.replaced === 1 ? "" : "s"} would change` : "Preview first"}</span>
              <div className="spacer" />
              <button className="btn" onClick={onClose}>Close</button>
              <button className={"btn" + (preview ? "" : " primary")} disabled={!find} onClick={dry} data-tip="Shows the changes without making them" data-tip-cmd="recomp transcript replace … --dry-run">Preview</button>
              <Act verb="transcript.replace" args={args} primary disabled={!find || !preview || !preview.replaced} onDone={onClose}>{`Replace ${preview?.replaced ?? ""}`}</Act>
            </>}>
      <form className="stack" onSubmit={(e) => { e.preventDefault(); if (find) dry(); }}>
        <div className="grid2">
          <div className="field"><label htmlFor="rp-find">Find</label><input id="rp-find" className="input" value={find} onChange={(e) => setFind(e.target.value)} /></div>
          <div className="field"><label htmlFor="rp-repl">Replace with</label><input id="rp-repl" className="input" value={repl} onChange={(e) => setRepl(e.target.value)} placeholder="(empty removes it)" /></div>
        </div>
        <div className="row">
          <span className="label">In</span>
          <div className="segmented" role="radiogroup" aria-label="Where">
            <button type="button" className={scope === "this" ? "on" : ""} aria-pressed={scope === "this"} onClick={() => setScope("this")}>This transcript</button>
            <button type="button" className={scope === "all" ? "on" : ""} aria-pressed={scope === "all"} onClick={() => setScope("all")}>Every source</button>
            {lines && <button type="button" className={scope === "lines" ? "on" : ""} aria-pressed={scope === "lines"} onClick={() => setScope("lines")}>Lines #{lines}</button>}
          </div>
          <label className="check muted2"><input type="checkbox" checked={whole} onChange={(e) => setWhole(e.target.checked)} />Whole words only</label>
        </div>
        <button type="submit" hidden />
      </form>
      {preview?.error && <div className="err">{preview.error}</div>}
      {preview && !preview.error && (
        <div className="previewlist" style={{ marginTop: 8, maxHeight: 260 }}>
          {!preview.replaced && <div className="muted2">No line changes.</div>}
          {(preview.changes || []).slice(0, 20).map((c: any) => (
            <div key={c.line}><span className="mono faint">{c.line}</span> <s>{c.before}</s><br />→ {c.after}</div>
          ))}
          {preview.more ? <div className="muted2">… and {preview.more} more</div> : null}
        </div>
      )}
    </Dialog>
  );
}

function SpeakersDialog({ data, lines, onClose }: { data: any; lines: string; onClose: () => void }) {
  const tr = data.transcript;
  const marks = data.segments.filter((s: Seg) => s.text.includes(">>")).length;
  const [names, setNames] = useState("");
  const [dry, setDry] = useState<any>(null);
  const voices = Object.entries(data.voices || {}) as [string, any][];
  return (
    <Dialog title="Speakers" sub="Name who speaks. No model needed: name lines directly, or apply the >> turn marks of captions." icon={<Users size={16} />} wide onClose={onClose}
            footer={<><span className="muted2">{lines ? `Lines #${lines} are selected: name them in the line bar.` : "Select lines in the transcript to name them directly."}</span>
              <div className="spacer" /><button className="btn" onClick={onClose}>Done</button></>}>
      <div className="stack">
        {!!voices.length && (
          <div className="field"><span className="label">Voices found</span>
            <table className="table"><tbody>
              {voices.map(([label, v]) => (
                <tr key={label}><td className="mono faint" style={{ width: 90 }}>{label}</td>
                  <td>{v.name ? <b>{v.name}</b> : <VoiceName voice={`${data.source.ref}:${label}`} />}</td></tr>
              ))}
            </tbody></table>
          </div>
        )}
        {marks > 0 && (
          <div className="field"><span className="label">From the {marks} “&gt;&gt;” turn marks</span>
            <div className="row nowrap">
              <input className="input grow" placeholder="Speakers in the order they first talk: Alex O'Connor, Guest name" value={names} onChange={(e) => { setNames(e.target.value); setDry(null); }} />
              <button className="btn" disabled={names.split(",").filter((x) => x.trim()).length < 2}
                      onClick={async () => { const e = await verb("speaker.assign", { ref: tr.ref, by: "marks", names, dry_run: true }); setDry(e); }}>Preview</button>
              <Act verb="speaker.assign" args={{ ref: tr.ref, by: "marks", names }} primary disabled={!dry?.ok}>Apply</Act>
            </div>
            {dry?.ok && <span className="help">{dry.data.lines} lines: {Object.entries(dry.data.by_person).map(([k, v]) => `${k} ${v}`).join(", ")} · {dry.data.marks?.per_minute} marks/min</span>}
            {dry?.warnings?.map((w: string) => <div key={w} className="warn">{w}</div>)}
          </div>
        )}
        {!voices.length && !marks && <div className="muted2">No voices or turn marks in this transcript yet. Select lines and name them, or use one of the ways below.</div>}
        <Disclosure id="room.speakers.more" label="Other ways: NAME: prefixes, diarisation">
          <div className="row">
            <Act verb="speaker.assign" args={{ ref: tr.ref, by: "prefix", dry_run: true }} small title="Film subtitles: lines that start with NAME:">Preview NAME: prefixes</Act>
            <Act verb="speaker.diarize" args={{ ref: data.source.ref }} small agent title="Heavy: pyannote on the CPU (about 2× the audio length)">Diarise (slow)</Act>
          </div>
        </Disclosure>
      </div>
    </Dialog>
  );
}

function VoiceName({ voice }: { voice: string }) {
  const [name, setName] = useState("");
  return (
    <span className="act-wrap">
      <input className="input small" style={{ width: 120 }} placeholder="who is it?" value={name} onChange={(e) => setName(e.target.value)} />
      <Act verb="speaker.name" args={{ voice, name }} small disabled={!name.trim()}>Name</Act>
    </span>
  );
}

