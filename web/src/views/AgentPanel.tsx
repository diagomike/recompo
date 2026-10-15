import { useState } from "react";
import { Send, Undo2 } from "lucide-react";
import { must, verb } from "../api";
import { useApp, useData } from "../App";
import { ago, refGo } from "./Activity";

// The right-hand panel: what the agent asked you, a note box back to it, live activity and jobs.
export default function AgentPanel() {
  const { go } = useApp();
  const { data: notes } = useData(() => must<any>("ui.notes", { mark_seen: false }));
  const { data: ops } = useData(() => must<any[]>("op.log", { limit: 14 }));
  const { data: jobs } = useData(() => must<any>("job.list", { limit: 6 }));
  const [text, setText] = useState("");
  const send = async () => {
    if (!text.trim()) return;
    await verb("ui.note", { text });
    setText("");
  };
  const open = (notes?.open_asks || []) as any[];
  const running = (jobs?.jobs || []).filter((j: any) => j.status === "running" || j.status === "queued");
  return (
    <>
      <div className="sidesec">
        <h3>Agent asks</h3>
        {!open.length && <div style={{ color: "var(--faint)", fontSize: 12 }}>Nothing pending.</div>}
        {open.map((a) => (
          <div key={a.id} className="ask">
            <div>{a.text}</div>
            {!!a.refs?.length && <div>{a.refs.map((r: string) => <a key={r} href="#" className="mono" style={{ marginRight: 6 }} onClick={(e) => { e.preventDefault(); refGo(go, r); }}>{r}</a>)}</div>}
            <div className="row" style={{ marginTop: 4 }}>
              {(a.options?.length ? a.options : ["yes", "no"]).map((o: string) => (
                <button key={o} className="btn small" onClick={() => verb("ui.answer", { id: a.id, answer: o })}>{o}</button>
              ))}
            </div>
          </div>
        ))}
        <div className="row" style={{ marginTop: 6 }}>
          <input className="input grow" placeholder="Note to the agent…" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
          <button className="btn small" onClick={send}><Send size={13} /></button>
        </div>
      </div>
      {!!running.length && (
        <div className="sidesec">
          <h3>Running</h3>
          {running.map((j: any) => (
            <div key={j.ref} style={{ marginBottom: 6, fontSize: 12 }}>
              <div className="row"><span className="mono">{j.ref}</span>{j.type} {j.target}<div className="spacer" />{Math.round(j.progress * 100)}%</div>
              <div className="bar"><i style={{ width: `${Math.round(j.progress * 100)}%` }} /></div>
            </div>
          ))}
        </div>
      )}
      <div className="sidesec">
        <h3 className="row">Activity <span className="spacer" /><button className="btn ghost small" title="Undo" onClick={() => verb("op.undo")}><Undo2 size={13} /></button></h3>
        {(ops || []).map((o) => (
          <div key={o.op} className="act">
            <span className={"who chip " + o.actor}>{o.actor}</span>
            <span>
              <span className="mono">{o.verb}</span> {o.refs.slice(0, 4).map((r: string) => <a key={r} href="#" className="mono" onClick={(e) => { e.preventDefault(); refGo(go, r); }}> {r}</a>)}
              <span style={{ color: "var(--faint)" }}> · {ago(o.ago_s)}</span>
            </span>
          </div>
        ))}
      </div>
    </>
  );
}
