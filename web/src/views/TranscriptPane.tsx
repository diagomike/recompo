import { useEffect, useMemo, useRef, useState } from "react";
import { Combine, Eraser, Pencil, Replace, Split, Trash2, Users, X } from "lucide-react";
import { clock, verb } from "../api";
import { Act, useActions } from "../actions";

type Seg = { idx: number; start: number; end: number; text: string; speaker: string | null; words: [number, number, string][] | null };
type Sel = { a: number; b: number } | null;

// The transcript beside the player: read along, select lines, and fix them in place.
// Every edit is a transcript or speaker verb (one undo each); the agent runs the same ones in bulk.
export default function TranscriptPane({ data, t, sel, seek, setSel, panel }: {
  data: any; t: number; sel: Sel; seek: (t: number, play?: boolean) => void; setSel: (s: Sel) => void; panel: string | null;
}) {
  const box = useRef<HTMLDivElement>(null);
  const userScroll = useRef(0);
  const anchor = useRef<number | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [find, setFind] = useState("");
  const [tool, setTool] = useState<null | "replace" | "speakers">(panel === "speakers" ? "speakers" : null);
  const { run } = useActions();
  const segs: Seg[] = data.segments;
  const tr = data.transcript;
  const voices: Record<string, { name: string | null }> = data.voices || {};
  const who = (label: string | null) => (label ? voices[label]?.name || label : null);

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
  const hits = q ? segs.filter((s) => s.text.toLowerCase().includes(q)).length : 0;

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
      <div className="transcript">
        <div className="empty" style={{ margin: 12 }}>
          No transcript yet.
          <div className="row" style={{ justifyContent: "center", marginTop: 8 }}>
            {data.source.kind === "link"
              ? <Act verb="transcript.fetch-captions" args={{ ref: data.source.ref }} small primary agent>Fetch captions</Act>
              : <Act verb="transcript.asr" args={{ ref: data.source.ref }} small primary agent>Transcribe (ASR)</Act>}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="transcript tpane">
      <div className="thead">
        <div className="row" style={{ gap: 4 }}>
          <select className="input small" value={tr.ref} aria-label="Transcript"
                  onChange={(e) => run("transcript.set-primary", { ref: e.target.value }, { label: `Use ${e.target.value}` })}>
            {(data.transcripts || [tr]).map((x: any) => <option key={x.ref} value={x.ref}>{x.ref} · {x.origin} · {x.language}{x.label ? ` · ${x.label.slice(0, 28)}` : ""}</option>)}
          </select>
          <span className="muted2">{segs.length} lines{tr.has_words ? " · word timing" : ""}</span>
          <div className="spacer" />
          <button className={"btn ghost small" + (tool === "replace" ? " on" : "")} onClick={() => setTool(tool === "replace" ? null : "replace")} title="Find and replace"><Replace size={13} /></button>
          <button className={"btn ghost small" + (tool === "speakers" ? " on" : "")} onClick={() => setTool(tool === "speakers" ? null : "speakers")} title="Speakers"><Users size={13} /></button>
        </div>
        <div className="row" style={{ gap: 4, marginTop: 4 }}>
          <input className="input grow small" placeholder="Find in transcript" value={find} onChange={(e) => setFind(e.target.value)} data-filter="tq"
                 onKeyDown={(e) => {
                   if (e.key !== "Enter" || !q) return;
                   const next = segs.find((s) => s.start > t + 0.2 && s.text.toLowerCase().includes(q)) || segs.find((s) => s.text.toLowerCase().includes(q));
                   if (next) { setSel({ a: next.start, b: next.end }); seek(next.start); userScroll.current = 0; }
                 }} />
          {q && <span className="chip">{hits} lines</span>}
        </div>
        {tool === "replace" && <ReplacePanel trRef={tr.ref} find={find} setFind={setFind} lines={lines} onClose={() => setTool(null)} />}
        {tool === "speakers" && <SpeakersPanel data={data} lines={lines} onClose={() => setTool(null)} />}
        {!!selected.length && (
          <div className="linebar">
            <b>{selected.length === 1 ? `Line #${selected[0].idx}` : `Lines #${lines}`}</b>
            <SpeakerSet trRef={tr.ref} lines={lines} people={data.people} />
            {selected.length > 1 && <Act verb="transcript.merge" args={{ ref: tr.ref, lines }} small ghost icon={<Combine size={12} />} title="Join into one line">Merge</Act>}
            {selected.length === 1 && t > selected[0].start + 0.2 && t < selected[0].end - 0.2 &&
              <Act verb="transcript.split" args={{ ref: tr.ref, idx: selected[0].idx, at: t.toFixed(2) }} small ghost icon={<Split size={12} />} title="Split at the playhead">Split at {clock(t)}</Act>}
            <Act verb="transcript.clean" args={{ ref: tr.ref, lines }} small ghost icon={<Eraser size={12} />} title="Remove >> marks, [tags], ♪, doubled words">Clean</Act>
            <Act verb="transcript.delete" args={{ ref: tr.ref, lines }} small ghost icon={<Trash2 size={12} />} confirm={`Delete line(s) #${lines}? (undo brings them back)`}>Delete</Act>
            <button className="btn ghost small" onClick={() => setSel(null)} title="Clear the selection"><X size={12} /></button>
          </div>
        )}
      </div>
      <div className="tbody" ref={box} onWheel={() => (userScroll.current = Date.now())}>
        {segs.map((s, i) => {
          const c = chapStarts.get(i);
          const inSel = sel && s.end > sel.a + 0.01 && s.start < sel.b - 0.01;
          const hit = q && s.text.toLowerCase().includes(q);
          return (
            <div key={s.idx}>
              {c && <div className="chaphead">{c.ref} {c.title}<span className="s">{clock(c.start, 0)}</span></div>}
              <div className={"seg" + (i === cur ? " now" : "") + (inSel ? " sel" : "") + (hit ? " hit" : "")} data-i={i}
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
                    {s.speaker && <b className="who">{who(s.speaker)}: </b>}
                    {i === cur && s.words ? s.words.map((w, k) => <span key={k} className={"w" + (t >= w[0] && t < w[1] ? " now" : "")}>{w[2]} </span>) : s.text}
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

function ReplacePanel({ trRef, find, setFind, lines, onClose }: { trRef: string; find: string; setFind: (v: string) => void; lines: string; onClose: () => void }) {
  const [repl, setRepl] = useState("");
  const [scope, setScope] = useState<"this" | "all" | "lines">("this");
  const [whole, setWhole] = useState(false);
  const [preview, setPreview] = useState<any>(null);
  const args = { ref: scope === "all" ? "all" : trRef, find, replace: repl, whole, ...(scope === "lines" && lines ? { lines } : {}) };
  useEffect(() => setPreview(null), [find, repl, scope, whole]);
  return (
    <div className="toolpanel">
      <div className="row" style={{ gap: 4 }}>
        <b>Find and replace</b><div className="spacer" /><button className="btn ghost small" onClick={onClose}><X size={12} /></button>
      </div>
      <div className="row" style={{ gap: 4 }}>
        <input className="input grow small" placeholder="find" value={find} onChange={(e) => setFind(e.target.value)} />
        <input className="input grow small" placeholder="replace with" value={repl} onChange={(e) => setRepl(e.target.value)} />
      </div>
      <div className="row" style={{ gap: 4, marginTop: 4 }}>
        <select className="input small" value={scope} onChange={(e) => setScope(e.target.value as any)}>
          <option value="this">this transcript</option><option value="all">every source</option>{lines && <option value="lines">selected lines</option>}
        </select>
        <label className="chip"><input type="checkbox" checked={whole} onChange={(e) => setWhole(e.target.checked)} /> whole words</label>
        <div className="spacer" />
        <button className="btn small" disabled={!find} onClick={async () => { const e = await verb("transcript.replace", { ...args, dry_run: true }); setPreview(e.ok ? e.data : { error: e.error?.message }); }}>Preview</button>
        <Act verb="transcript.replace" args={args} small primary disabled={!find || !preview || !preview.replaced} onDone={() => setPreview(null)}>{`Replace ${preview?.replaced ?? ""}`}</Act>
      </div>
      {preview?.error && <div className="err">{preview.error}</div>}
      {preview && !preview.error && (
        <div className="previewlist">
          {!preview.replaced && <div className="muted2">No line changes.</div>}
          {(preview.changes || []).slice(0, 12).map((c: any) => (
            <div key={c.line}><span className="mono">{c.line}</span> <s>{c.before}</s><br />→ {c.after}</div>
          ))}
          {preview.more ? <div className="muted2">… and {preview.more} more</div> : null}
        </div>
      )}
    </div>
  );
}

function SpeakersPanel({ data, lines, onClose }: { data: any; lines: string; onClose: () => void }) {
  const tr = data.transcript;
  const marks = data.segments.filter((s: Seg) => s.text.includes(">>")).length;
  const [names, setNames] = useState("");
  const [dry, setDry] = useState<any>(null);
  const voices = Object.entries(data.voices || {}) as [string, any][];
  return (
    <div className="toolpanel">
      <div className="row" style={{ gap: 4 }}>
        <b>Speakers</b><span className="muted2">name lines directly; no model needed</span><div className="spacer" />
        <button className="btn ghost small" onClick={onClose}><X size={12} /></button>
      </div>
      {!!voices.length && (
        <div style={{ margin: "4px 0" }}>
          {voices.map(([label, v]) => (
            <div key={label} className="row" style={{ gap: 4, fontSize: 12 }}>
              <span className="mono">{label}</span>→<b>{v.name || "unnamed"}</b>
              {!v.name && <VoiceName voice={`${data.source.ref}:${label}`} />}
            </div>
          ))}
        </div>
      )}
      {marks > 0 && (
        <>
          <div className="muted2">This transcript has {marks} “&gt;&gt;” turn marks. Give the speakers in order of who talks first:</div>
          <div className="row" style={{ gap: 4 }}>
            <input className="input grow small" placeholder="Alex O'Connor, Guest name" value={names} onChange={(e) => { setNames(e.target.value); setDry(null); }} />
            <button className="btn small" disabled={names.split(",").filter((x) => x.trim()).length < 2}
                    onClick={async () => { const e = await verb("speaker.assign", { ref: tr.ref, by: "marks", names, dry_run: true }); setDry(e); }}>Preview</button>
            <Act verb="speaker.assign" args={{ ref: tr.ref, by: "marks", names }} small primary disabled={!dry?.ok}>Apply</Act>
          </div>
          {dry?.ok && <div className="muted2">{dry.data.lines} lines: {Object.entries(dry.data.by_person).map(([k, v]) => `${k} ${v}`).join(", ")} · {dry.data.marks?.per_minute} marks/min</div>}
          {dry?.warnings?.map((w: string) => <div key={w} className="warn">{w}</div>)}
        </>
      )}
      <div className="row" style={{ gap: 4, marginTop: 4 }}>
        <Act verb="speaker.assign" args={{ ref: tr.ref, by: "prefix", dry_run: true }} small ghost title="Film subtitles: lines that start with NAME:">Preview NAME: prefixes</Act>
        <Act verb="speaker.diarize" args={{ ref: data.source.ref }} small ghost agent title="Heavy: pyannote on the CPU (about 2× the audio length)">Diarise (slow)</Act>
        {lines && <span className="muted2">or name the selected lines with the Speaker box below</span>}
      </div>
    </div>
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

