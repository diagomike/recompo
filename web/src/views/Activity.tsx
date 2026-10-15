import { useState } from "react";
import { Undo2, Redo2 } from "lucide-react";
import { must, verb } from "../api";
import { useApp, useData } from "../App";

export default function ActivityView() {
  const { go } = useApp();
  const [actor, setActor] = useState("");
  const { data, error } = useData(() => must<any[]>("op.log", { limit: 150, ...(actor ? { actor } : {}) }), [actor]);
  const [msg, setMsg] = useState<string | null>(null);
  const act = async (name: string) => {
    const env = await verb(name, {});
    setMsg(env.ok ? null : env.error!.message + (env.error!.hint ? " — " + env.error!.hint : ""));
  };
  return (
    <div className="page">
      <h1 className="h1">Activity</h1>
      <p className="sub">Every change, who made it (you, the agent, or a machine job), and undo. You outrank the agent: it cannot overwrite or undo your work.</p>
      <div className="row" style={{ marginBottom: 10 }}>
        <button className="btn" onClick={() => act("op.undo")}><Undo2 size={14} />Undo</button>
        <button className="btn" onClick={() => act("op.redo")}><Redo2 size={14} />Redo</button>
        <div className="spacer" />
        <select className="input" value={actor} onChange={(e) => setActor(e.target.value)}>
          <option value="">everyone</option><option value="user">you</option><option value="agent">agent</option><option value="machine">machine</option>
        </select>
      </div>
      {msg && <div className="err">{msg}</div>}
      {error && <div className="err">{error}</div>}
      <table className="table">
        <thead><tr><th>When</th><th>Who</th><th>What</th><th>Refs</th><th>State</th></tr></thead>
        <tbody>
          {(data || []).map((o) => (
            <tr key={o.op}>
              <td className="mono" style={{ color: "var(--muted)" }}>{ago(o.ago_s)}</td>
              <td><span className={"chip " + o.actor}>{o.actor}</span></td>
              <td><span className="mono">{o.verb}</span> {o.summary && <span style={{ color: "var(--muted)" }}>· {o.summary}</span>}</td>
              <td>{o.refs.slice(0, 8).map((r: string) => <a key={r} href="#" className="mono" style={{ marginRight: 6 }} onClick={(e) => { e.preventDefault(); refGo(go, r); }}>{r}</a>)}</td>
              <td>{o.state !== "done" && <span className="chip">{o.state}</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ago(s: number) {
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function refGo(go: (v: string, a?: string | null, p?: any) => void, r: string) {
  if (/^S\d+/.test(r)) go("room", r.split(".")[0], { focus: r });
  else if (/^C\d+/.test(r)) must("cut.show", { ref: r }).then((c: any) => go("room", c.source, { focus: r }));
  else if (/^J\d+/.test(r)) go("journeys", r.split("#")[0]);
  else if (/^X\d+/.test(r)) go("exports", r);
}
