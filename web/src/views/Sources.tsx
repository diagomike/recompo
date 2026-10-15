import { useState } from "react";
import { Plus } from "lucide-react";
import { must, verb } from "../api";
import { useApp, useData } from "../App";

const STAGES = ["probe", "audio", "peaks", "shots", "thumbs", "transcript", "chapters"];

export default function Sources() {
  const { go } = useApp();
  const { data, error } = useData(() => must<any[]>("source.status"));
  const { data: list } = useData(() => must<any[]>("source.list"));
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const byRef: Record<string, any> = {};
  (list || []).forEach((s) => (byRef[s.ref] = s));

  const add = async () => {
    if (!target.trim()) return;
    setBusy(true);
    const env = await verb("source.add", { target: target.trim() });
    setBusy(false);
    if (!env.ok) setMsg({ ok: false, text: `${env.error!.message}${env.error!.hint ? " — " + env.error!.hint : ""}` });
    else {
      const d = env.data;
      if (d.entries) setMsg({ ok: true, text: `${d.entries.length} entries listed: pick them from the agent panel or ask your agent.` });
      else setMsg({ ok: true, text: `Added ${d.added.map((a: any) => a.ref).join(", ") || "nothing new"}${d.skipped?.length ? `; ${d.skipped.length} already here` : ""}.` });
      setTarget("");
    }
  };

  return (
    <div className="page">
      <h1 className="h1">Sources</h1>
      <p className="sub">Films, talks and podcasts in this project. Files stay where they are; links bring metadata and captions first, and video only when a journey needs it.</p>
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="row">
          <Plus size={16} />
          <input className="input grow" placeholder='A file, folder, glob ("D:\Movies\*.mp4") or link (YouTube video, playlist, channel)'
                 value={target} onChange={(e) => setTarget(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} />
          <button className="btn primary" disabled={busy} onClick={add}>{busy ? "Adding…" : "Add"}</button>
        </div>
        {msg && <div className={msg.ok ? "warn" : "err"} style={msg.ok ? { color: "var(--accent)", background: "var(--accent-soft)" } : undefined}>{msg.text}</div>}
      </div>
      {error && <div className="err">{error}</div>}
      {data && !data.length && <div className="empty">No sources yet. Add a file or a link above, or ask your agent: <code>recomp source add …</code></div>}
      {!!data?.length && (
        <table className="table">
          <thead><tr><th>Ref</th><th>Title</th><th>Length</th><th>Transcript</th><th>Chapters</th><th>Cuts</th><th>Pipeline</th></tr></thead>
          <tbody>
            {data.map((s) => {
              const b = byRef[s.ref] || {};
              return (
                <tr key={s.ref} className="click" onClick={() => go("room", s.ref)}>
                  <td className="mono">{s.ref}</td>
                  <td><b>{s.title}</b></td>
                  <td className="mono">{b.duration}</td>
                  <td>{b.transcript ? <span className="chip done">{b.transcript.origin} · {b.transcript.language}</span> : <span className="chip">none</span>}</td>
                  <td>{b.chapters}</td>
                  <td>{b.cuts}</td>
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
      )}
    </div>
  );
}
