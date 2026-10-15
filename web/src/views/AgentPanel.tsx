import { useState } from "react";
import { Bot, MessageCircleQuestion, Send, Undo2, X } from "lucide-react";
import { must, verb } from "../api";
import { useApp, useData } from "../App";
import { ago, refGo } from "./Activity";

// The agent drawer: what the agent asks you, a note box back to it, what is running, and live activity.
export default function AgentPanel({ onClose }: { onClose: () => void }) {
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
  const waiting = ((notes?.notes || []) as any[]).filter((n) => n.by === "user");
  const running = (jobs?.jobs || []).filter((j: any) => j.status === "running" || j.status === "queued");
  return (
    <>
      <div className="drawerhead">
        <Bot size={20} style={{ color: "var(--agent)" }} />
        <h2 className="grow">Agent</h2>
        <button className="btn ghost icon" onClick={onClose} aria-label="Close" data-tip="Hide the panel" data-tip-key="."><X size={18} /></button>
      </div>
      <div className="sidesec">
        <h3><MessageCircleQuestion size={14} />Questions for you</h3>
        {!open.length && <div className="muted2">Nothing pending. When the agent needs a decision, it shows up here.</div>}
        {open.map((a) => (
          <div key={a.id} className="ask">
            <div>{a.text}</div>
            {!!a.refs?.length && <div className="row tight" style={{ marginTop: 6 }}>{a.refs.map((r: string) => <a key={r} href="#" className="chip mono" onClick={(e) => { e.preventDefault(); refGo(go, r); }}>{r}</a>)}</div>}
            <div className="row tight" style={{ marginTop: 10 }}>
              {(a.options?.length ? a.options : ["yes", "no"]).map((o: string, k: number) => (
                <button key={o} className={"btn small" + (k === 0 ? " primary" : "")} onClick={() => verb("ui.answer", { id: a.id, answer: o })}>{o}</button>
              ))}
            </div>
          </div>
        ))}
        <div className="row nowrap" style={{ marginTop: 10, gap: 8 }}>
          <input className="input grow" placeholder="Leave a note for the agent…" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
          <button className="btn icon" onClick={send} disabled={!text.trim()} aria-label="Send" data-tip="Send: the agent reads it with `recomp ui notes`"><Send size={16} /></button>
        </div>
        {!!waiting.length && (
          <div style={{ marginTop: 12 }}>
            <div className="muted2">Waiting for the agent to read ({waiting.length})</div>
            {waiting.slice(-4).map((n) => <div key={n.id} className="handed">{n.request ? <code>{n.request.cli}</code> : n.text}</div>)}
          </div>
        )}
      </div>
      {!!running.length && (
        <div className="sidesec">
          <h3>Running now</h3>
          {running.map((j: any) => (
            <div key={j.ref} style={{ marginBottom: 10, fontSize: 14 }}>
              <div className="row nowrap"><span className="ellipsis grow">{j.type} {j.target}</span><span className="faint mono">{Math.round(j.progress * 100)}%</span></div>
              <div className="bar" style={{ marginTop: 4 }}><i style={{ width: `${Math.round(j.progress * 100)}%` }} /></div>
            </div>
          ))}
        </div>
      )}
      <div className="sidesec" style={{ borderBottom: 0 }}>
        <h3><span className="grow">Activity</span><button className="btn ghost small icon" aria-label="Undo" data-tip="Undo your last change" data-tip-key="Ctrl+Z" onClick={() => verb("op.undo")}><Undo2 size={15} /></button></h3>
        {(ops || []).map((o) => (
          <div key={o.op} className="act">
            <span className={"who chip " + o.actor}>{o.actor === "user" ? "you" : o.actor}</span>
            <span>
              <span className="mono">{o.verb}</span> {o.refs.slice(0, 4).map((r: string) => <a key={r} href="#" className="mono" onClick={(e) => { e.preventDefault(); refGo(go, r); }}> {r}</a>)}
              <span className="faint"> · {ago(o.ago_s)}</span>
            </span>
          </div>
        ))}
      </div>
    </>
  );
}
