import { useState } from "react";
import { ArrowUp, Folder, FolderOpen, Plus } from "lucide-react";
import { must } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { FilterBar, textMatch, useFilters } from "../filters";

const STAGES = ["probe", "audio", "peaks", "shots", "thumbs", "transcript", "chapters"];

export default function Sources() {
  const { go } = useApp();
  const { run } = useActions();
  const [f, setF] = useFilters();
  const { data, error } = useData(() => must<any[]>("source.status"));
  const { data: list } = useData(() => must<any[]>("source.list"));
  const [target, setTarget] = useState("");
  const byRef: Record<string, any> = {};
  (list || []).forEach((s) => (byRef[s.ref] = s));
  const rows = (data || []).filter((s) => {
    const b = byRef[s.ref] || {};
    return textMatch(f.q, s.title, s.ref) && (!f.kind || b.kind === f.kind) &&
      (!f.need || (f.need === "transcript" ? !b.transcript : f.need === "chapters" ? !b.chapters : f.need === "cuts" ? !b.cuts : true));
  });

  const add = async (t: string) => {
    if (!t.trim()) return;
    const env = await run("source.add", { target: t.trim() }, { label: "Add source" });
    if (env.ok) setTarget("");
  };

  return (
    <div className="page">
      <div className="row" style={{ marginBottom: 4 }}>
        <h1 className="h1" style={{ margin: 0 }}>Sources</h1>
        <div className="spacer" />
        <button className="btn small" onClick={() => setF("browse", f.browse ? null : "1")}><FolderOpen size={13} />Browse for files</button>
      </div>
      <p className="sub">Films, talks and podcasts in this project. Files stay where they are; links bring metadata and captions first, and video only when a journey needs it.</p>
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="row">
          <Plus size={16} />
          <input className="input grow" placeholder='A file, folder, glob ("D:\Movies\*.mp4") or link (YouTube video, playlist, channel)'
                 value={target} onChange={(e) => setTarget(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add(target)} />
          <Act verb="source.add" args={{ target: target.trim() }} primary agent disabled={!target.trim()} onDone={() => setTarget("")}>Add</Act>
        </div>
        {f.browse && <Browser onAdd={(paths) => paths.forEach((p) => add(p))} start={f.dir || null} setDir={(d) => setF("dir", d)} />}
      </div>
      {error && <div className="err">{error}</div>}
      {data && !data.length && <div className="empty">No sources yet. Browse for files, paste a path or a link above, or ask your agent.</div>}
      {!!data?.length && (
        <>
          <FilterBar count={rows.length} keep={["browse", "dir"]} fields={[
            { key: "q", label: "Title", type: "text" },
            { key: "kind", label: "Kind", type: "select", options: [["file", "files"], ["link", "links"]] },
            { key: "need", label: "Missing", type: "select", options: [["transcript", "no transcript"], ["chapters", "no chapters"], ["cuts", "no cuts"]] },
          ]} />
          <table className="table">
            <thead><tr><th>Ref</th><th>Title</th><th>Length</th><th>Transcript</th><th>Chapters</th><th>Cuts</th><th>Pipeline</th></tr></thead>
            <tbody>
              {rows.map((s) => {
                const b = byRef[s.ref] || {};
                return (
                  <tr key={s.ref} className="click" onClick={() => go("room", s.ref)}>
                    <td className="mono">{s.ref}</td>
                    <td><b>{s.title}</b> {b.kind === "link" && <span className="chip">link</span>}</td>
                    <td className="mono">{b.duration}</td>
                    <td onClick={(e) => e.stopPropagation()}>{b.transcript ? <span className="chip done">{b.transcript.origin} · {b.transcript.language}</span>
                      : b.kind === "link" ? <Act verb="transcript.fetch-captions" args={{ ref: s.ref }} small>Fetch captions</Act>
                        : <Act verb="transcript.asr" args={{ ref: s.ref }} small agent>Transcribe</Act>}</td>
                    <td>{b.chapters}</td>
                    <td>{b.cuts ? <a href="#" onClick={(e) => { e.preventDefault(); e.stopPropagation(); go("cuts", null, { source: s.ref }); }}>{b.cuts}</a> : 0}</td>
                    <td>
                      <div className="row" style={{ gap: 3 }}>
                        {STAGES.filter((k) => s.status?.[k]).map((k) => <span key={k} className={"chip " + (s.status[k] === "done" ? "done" : s.status[k] === "failed" ? "failed" : "")}>{k}</span>)}
                        {s.jobs.map((j: any) => <span key={j.ref} className={"chip " + j.status}>{j.type} {Math.round(j.progress * 100)}%</span>)}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

// A read-only file browser (`recomp source browse`): pick media files and add them.
function Browser({ onAdd, start, setDir }: { onAdd: (paths: string[]) => void; start: string | null; setDir: (d: string | null) => void }) {
  const { data, error } = useData(() => must<any>("source.browse", start ? { path: start } : {}), [start]);
  const [picked, setPicked] = useState<string[]>([]);
  const media = (data?.files || []).filter((x: any) => x.kind === "media");
  return (
    <div className="browser">
      <div className="row" style={{ gap: 4 }}>
        <button className="btn small ghost" disabled={!data?.parent && !data?.path} onClick={() => setDir(data?.parent || null)}><ArrowUp size={12} />Up</button>
        <span className="mono grow" style={{ overflowWrap: "anywhere" }}>{data?.path || "This computer"}</span>
        {data?.path && !!media.length && <button className="btn small" onClick={() => onAdd([data.path])} title="Add every media file in this folder (with its subtitles)">Add whole folder ({media.length})</button>}
        <button className="btn small primary" disabled={!picked.length} onClick={() => { onAdd(picked); setPicked([]); }}>Add {picked.length || ""} selected</button>
      </div>
      {error && <div className="err">{error}</div>}
      <div className="blist">
        {(data?.dirs || []).map((d: any) => (
          <div key={d.path} className="brow click" onClick={() => setDir(d.path)}><Folder size={13} /> {d.name}</div>
        ))}
        {(data?.files || []).map((x: any) => (
          <label key={x.path} className={"brow" + (x.kind === "media" ? "" : " sub")}>
            {x.kind === "media" ? <input type="checkbox" checked={picked.includes(x.path)} onChange={(e) => setPicked(e.target.checked ? [...picked, x.path] : picked.filter((p) => p !== x.path))} />
              : <span style={{ width: 13 }} />}
            {x.name} <span className="muted2">{x.kind === "subtitle" ? "subtitles (found automatically)" : `${x.mb} MB`}</span>
          </label>
        ))}
        {data && !data.dirs.length && !data.files.length && <div className="muted2">No folders or media here.</div>}
      </div>
    </div>
  );
}
