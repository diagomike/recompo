import { useState } from "react";
import { ArrowUp, CheckCircle2, Film, Folder, FolderOpen, Link2, Plus, Scissors, X } from "lucide-react";
import { frameUrl, must } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { FilterBar, textMatch, useFilters } from "../filters";
import { Disclosure, Empty, Menu, SrcBadge } from "../ui";
import { asSourceAddArgs, DubFields, DubFieldsForm, DubSettingsDialog } from "./DubSettings";

const STAGES = ["probe", "audio", "peaks", "shots", "thumbs", "transcript", "chapters"];
const secs = (hms: string) => String(hms || "0").split(":").reduce((a, x) => a * 60 + parseFloat(x), 0);

export default function Sources() {
  const { go } = useApp();
  const { run } = useActions();
  const [f, setF] = useFilters();
  const { data, error } = useData(() => must<any[]>("source.status"));
  const { data: list } = useData(() => must<any[]>("source.list"));
  const [target, setTarget] = useState("");
  const [dub, setDub] = useState<DubFields>({});
  const [dubFor, setDubFor] = useState<string | null>(null);
  const byRef: Record<string, any> = {};
  (list || []).forEach((s) => (byRef[s.ref] = s));
  const rows = (data || []).filter((s) => {
    const b = byRef[s.ref] || {};
    return textMatch(f.q, s.title, s.ref) && (!f.kind || b.kind === f.kind) &&
      (!f.need || (f.need === "transcript" ? !b.transcript : f.need === "chapters" ? !b.chapters : f.need === "cuts" ? !b.cuts : true));
  });
  const adding = !!f.add || !!f.browse || (data && !data.length);

  const add = async (t: string) => {
    if (!t.trim()) return;
    const env = await run("source.add", { target: t.trim(), ...asSourceAddArgs(dub) }, { label: "Add source" });
    if (env.ok) setTarget("");
  };

  return (
    <div className="page">
      <div className="pagehead">
        <div className="titles">
          <h1 className="h1">Sources</h1>
          <p className="sub">Films, talks and podcasts in this project. Files stay where they are; links bring metadata and captions first, and video only when a journey needs it.</p>
        </div>
        {!adding && <button className="btn primary" onClick={() => setF("add", "1")}><Plus size={14} />Add sources</button>}
      </div>
      {adding && (
        <div className="card stack" style={{ marginBottom: 24 }}>
          <div className="row nowrap"><h2 className="h3 grow" style={{ margin: 0 }}>Add sources</h2>
            {!!data?.length && <button className="btn ghost icon" aria-label="Close" onClick={() => { setF("add", null); setF("browse", null); }}><X size={14} /></button>}</div>
          <div className="row nowrap">
            <input className="input grow" placeholder='Paste a link (YouTube video, playlist, channel), a file, a folder or a glob ("D:\Movies\*.mp4")'
                   value={target} onChange={(e) => setTarget(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add(target)} />
            <Act verb="source.add" args={{ target: target.trim(), ...asSourceAddArgs(dub) }} primary agent disabled={!target.trim()} onDone={() => setTarget("")}>Add</Act>
          </div>
          <div className="row">
            <button className={"btn" + (f.browse ? " on" : "")} onClick={() => setF("browse", f.browse ? null : "1")}><FolderOpen size={14} />Browse this computer</button>
            <span className="muted2">Subtitles next to a video (.srt, .vtt) are picked up automatically.</span>
          </div>
          <Disclosure id="src.add.dub" label="Dubbing: languages and LLM dub route for these sources">
            <DubFieldsForm value={dub} onChange={setDub} withTargets />
          </Disclosure>
          {f.browse && <Browser onAdd={(paths) => paths.forEach((p) => add(p))} start={f.dir || null} setDir={(d) => setF("dir", d)} />}
        </div>
      )}
      {error && <div className="err">{error}</div>}
      {data && !data.length && <Empty icon={<Film size={14} />} title="No sources yet">Paste a link or a path above, or browse this computer. Your agent can add them too.</Empty>}
      {!!data?.length && (
        <>
          <FilterBar count={rows.length} noun={rows.length === 1 ? "source" : "sources"} keep={["browse", "dir", "add"]} fields={[
            { key: "q", label: "Title", type: "text", placeholder: "Search sources" },
            { key: "need", label: "Missing", type: "select", options: [["transcript", "no transcript"], ["chapters", "no chapters"], ["cuts", "no cuts"]] },
            { key: "kind", label: "Kind", type: "select", options: [["file", "files"], ["link", "links"]] },
          ]} />
          <table className="table">
            <thead><tr><th style={{ width: 92 }}></th><th>Source</th><th>Length</th><th>Transcript</th><th>Chapters</th><th>Cuts</th><th>Pipeline</th><th></th></tr></thead>
            <tbody>
            {rows.map((s) => {
              const b = byRef[s.ref] || {};
              const stages = STAGES.filter((k) => s.status?.[k]);
              const pending = stages.filter((k) => s.status[k] !== "done");
              return (
                <tr key={s.ref} className="click" onClick={() => go("room", s.ref)}>
                  <td>{b.has_media ? <img className="thumb" src={frameUrl(s.ref, Math.min(60, secs(b.duration) / 3), 160)} alt="" loading="lazy" />
                    : <div className="thumb" style={{ display: "grid", placeItems: "center", color: "var(--faint)" }}>{b.kind === "link" ? <Link2 size={14} /> : <Film size={14} />}</div>}</td>
                  <td><div className="row nowrap tight"><SrcBadge ref_={s.ref} /><b className="ellipsis" style={{ maxWidth: 380 }}>{s.title}</b>{b.kind === "link" && <span className="chip">link</span>}</div></td>
                  <td className="mono nowrap">{String(b.duration || "").replace(/^00:/, "").replace(/\.\d+$/, "")}</td>
                  <td onClick={(e) => e.stopPropagation()}>{b.transcript ? <span className="chip ok" data-tip={`${b.transcript.origin}, ${b.transcript.language}`}><CheckCircle2 size={11} />{b.transcript.origin}</span>
                    : b.kind === "link" ? <Act verb="transcript.fetch-captions" args={{ ref: s.ref }} small primary>Fetch captions</Act>
                      : <Act verb="transcript.asr" args={{ ref: s.ref }} small primary agent>Transcribe</Act>}</td>
                  <td>{b.chapters || 0}</td>
                  <td>{b.cuts ? <a href="#" onClick={(e) => { e.preventDefault(); e.stopPropagation(); go("cuts", null, { source: s.ref }); }}>{b.cuts}</a> : 0}</td>
                  <td><div className="row tight">
                    {pending.length || s.jobs.length ? <>
                      {pending.map((k) => <span key={k} className={"chip " + (s.status[k] === "failed" ? "failed" : "partial")}>{k}: {s.status[k]}</span>)}
                      {s.jobs.map((j: any) => <span key={j.ref} className={"chip " + j.status}>{j.type} {Math.round(j.progress * 100)}%</span>)}
                    </> : <span className="chip ok" data-tip={stages.join(" · ")}>ready</span>}
                  </div></td>
                  <td onClick={(e) => e.stopPropagation()} style={{ textAlign: "right" }}><div className="row nowrap tight" style={{ justifyContent: "flex-end" }}>
                    <button className="btn small" onClick={() => go("room", s.ref)}><Scissors size={13} />Open</button>
                    <Menu small label={`More for ${s.ref}`} items={[
                      { label: "Show its cuts", onSelect: () => go("cuts", null, { source: s.ref }) },
                      { label: "Dub settings…", desc: "Route, middle languages, MT and checks for the LLM dubber", onSelect: () => setDubFor(s.ref) },
                      { label: "Build frames and waveform", desc: "source process --jobs audio,peaks,thumbs", onSelect: () => run("source.process", { ref: s.ref, jobs: ["audio", "peaks", "thumbs"] }, { label: "Process" }) },
                      ...(b.kind === "link" ? [{ label: "Creator chapters", onSelect: () => run("chapter.seed", { ref: s.ref }, { label: "Chapters" }) }] : []),
                      { label: b.kind === "link" ? "Transcribe locally (ASR)" : "Transcribe again (ASR)", onSelect: () => run("transcript.asr", { ref: s.ref }, { label: "Transcribe" }) },
                    ]} />
                  </div></td>
                </tr>
              );
            })}
            </tbody>
          </table>
        </>
      )}
      {dubFor && <DubSettingsDialog target={dubFor} title={`Dub settings for ${dubFor}`} onClose={() => setDubFor(null)}
                                    scopes={[[dubFor, `this source (${dubFor})`], ["project", "the project"], ["studio", "the studio (every project)"]]} />}
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
      <div className="row">
        <button className="btn small ghost" disabled={!data?.parent && !data?.path} onClick={() => setDir(data?.parent || null)}><ArrowUp size={14} />Up</button>
        <span className="mono grow" style={{ overflowWrap: "anywhere" }}>{data?.path || "This computer"}</span>
        {data?.path && !!media.length && <button className="btn small" onClick={() => onAdd([data.path])} data-tip="Add every media file in this folder (with its subtitles)">Add whole folder ({media.length})</button>}
        <button className="btn small primary" disabled={!picked.length} onClick={() => { onAdd(picked); setPicked([]); }}>Add {picked.length || ""} selected</button>
      </div>
      {error && <div className="err">{error}</div>}
      <div className="blist">
        {(data?.dirs || []).map((d: any) => (
          <div key={d.path} className="brow click" onClick={() => setDir(d.path)}><Folder size={14} /> {d.name}</div>
        ))}
        {(data?.files || []).map((x: any) => (
          <label key={x.path} className={"brow" + (x.kind === "media" ? "" : " sub")}>
            {x.kind === "media" ? <input type="checkbox" checked={picked.includes(x.path)} onChange={(e) => setPicked(e.target.checked ? [...picked, x.path] : picked.filter((p) => p !== x.path))} />
              : <span style={{ width: 17 }} />}
            {x.name} <span className="muted2">{x.kind === "subtitle" ? "subtitles (found automatically)" : `${x.mb} MB`}</span>
          </label>
        ))}
        {data && !data.dirs.length && !data.files.length && <div className="brow muted2">No folders or media here.</div>}
      </div>
    </div>
  );
}
