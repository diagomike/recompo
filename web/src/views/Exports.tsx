import { useState } from "react";
import { Copy, Play, RefreshCw } from "lucide-react";
import { fileUrl, must, verb } from "../api";
import { useApp, useData } from "../App";

export default function Exports() {
  const { route, go } = useApp();
  const { data: list, error } = useData(() => must<any[]>("export.status", { limit: 60 }));
  const { data: journeys } = useData(() => must<any[]>("journey.list"));
  const { data: profs } = useData(() => must<any[]>("profile.list"));
  const [j, setJ] = useState(route.params.get("journey") || "");
  const [chosen, setChosen] = useState<string[]>(["shorts", "landscape"]);
  const [langs, setLangs] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const current = route.arg;

  const run = async (preview: boolean) => {
    const target = j || journeys?.[0]?.ref;
    if (!target) return;
    const env = preview
      ? await verb("preview", { target, profile: chosen[0] || "landscape" })
      : await verb("export.run", { journey: target, profiles: chosen, langs: langs ? langs.split(",").map((x) => x.trim()) : [] });
    setMsg(env.ok ? null : env.error!.message + (env.error!.hint ? " — " + env.error!.hint : ""));
  };

  return (
    <div className="page" style={{ maxWidth: "none" }}>
      <h1 className="h1">Exports</h1>
      <p className="sub">Render a journey in any formats and languages. Each export comes with captions, a ready-to-paste description with full credits, and the recipe. You upload it yourself.</p>
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="row">
          <select className="input" value={j} onChange={(e) => setJ(e.target.value)}>
            {(journeys || []).map((x) => <option key={x.ref} value={x.ref}>{x.ref} · {x.title} ({x.duration})</option>)}
          </select>
          {(profs || []).filter((p) => p.name !== "preview").map((p) => (
            <label key={p.name} className="chip" style={{ cursor: "pointer" }} title={p.description}>
              <input type="checkbox" checked={chosen.includes(p.name)} onChange={(e) => setChosen(e.target.checked ? [...chosen, p.name] : chosen.filter((x) => x !== p.name))} /> {p.name} {p.size}
            </label>
          ))}
          <input className="input" style={{ width: 140 }} placeholder="langs e.g. en,am,sw" value={langs} onChange={(e) => setLangs(e.target.value)} />
          <button className="btn" onClick={() => run(true)}>Preview</button>
          <button className="btn primary" onClick={() => run(false)}>Export</button>
        </div>
        {msg && <div className="err">{msg}</div>}
      </div>
      {error && <div className="err">{error}</div>}
      <div className="jgrid" style={{ gridTemplateColumns: "minmax(300px, 420px) minmax(0, 1fr)" }}>
        <div>
          {(list || []).map((x) => (
            <div key={x.ref} className="card" style={{ marginBottom: 6, cursor: "pointer", borderColor: x.ref === current ? "var(--accent)" : undefined }}
                 onClick={() => go("exports", x.ref)}>
              <div className="row">
                <b className="mono">{x.ref}</b><span>{x.of} · {x.title}</span><div className="spacer" />
                <span className={"chip " + (x.status === "done" ? "done" : x.status.includes("problem") || x.status === "failed" ? "failed" : "running")}>{x.status}</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--muted)" }}>{x.preview ? "preview · " : ""}{x.profile} · {x.lang}{x.seconds ? ` · rendered in ${x.seconds}s` : ""}</div>
              {x.progress != null && x.status !== "done" && <div className="bar" style={{ marginTop: 4 }}><i style={{ width: `${Math.round(x.progress * 100)}%` }} /></div>}
              {x.error && <div className="err" style={{ fontSize: 12 }}>{x.error}</div>}
              {!!x.problems.length && <div style={{ fontSize: 12, color: "var(--red)" }}>{x.problems.map((p: any) => p.check).join(", ")}</div>}
            </div>
          ))}
          {list && !list.length && <div className="empty">No exports yet.</div>}
        </div>
        <div>{current && <ExportDetail key={current} xref={current} />}</div>
      </div>
    </div>
  );
}

function ExportDetail({ xref }: { xref: string }) {
  const { data: x, error } = useData(() => must<any>("export.show", { ref: xref }), [xref]);
  const [copied, setCopied] = useState(false);
  if (error) return <div className="err">{error}</div>;
  if (!x) return null;
  const vertical = (x.checks || []).some((c: any) => c.check === "frame size" && /^(\d+)x(\d+)$/.test(c.detail) && +c.detail.split("x")[1] > +c.detail.split("x")[0]);
  return (
    <div className="card">
      <div className="row" style={{ marginBottom: 8 }}>
        <b>{x.ref} · {x.title}</b><span className="chip">{x.profile} · {x.lang}</span><div className="spacer" />
        <button className="btn small" onClick={() => verb("export.check", { ref: xref })}><RefreshCw size={12} />Re-check</button>
      </div>
      {x.video ? (
        <video controls src={fileUrl(x.video)} style={{ width: "100%", maxHeight: vertical ? 560 : 420, background: "#000", borderRadius: 4 }} />
      ) : <div className="empty"><Play size={14} /> Not rendered yet ({x.status}).</div>}
      <div className="row" style={{ marginTop: 8, flexWrap: "wrap", gap: 4 }}>
        {(x.checks || []).map((c: any) => <span key={c.check} className={"chip " + (c.ok ? "done" : "failed")} title={c.detail}>{c.check}: {c.detail}</span>)}
      </div>
      {x.description && (
        <div style={{ marginTop: 10 }}>
          <div className="row"><b>Description</b><div className="spacer" />
            <button className="btn small" onClick={() => { navigator.clipboard.writeText(x.description); setCopied(true); setTimeout(() => setCopied(false), 1500); }}><Copy size={12} />{copied ? "Copied" : "Copy"}</button>
          </div>
          <pre style={{ whiteSpace: "pre-wrap", background: "var(--panel-2)", padding: 8, borderRadius: 4, fontSize: 12 }}>{x.description}</pre>
        </div>
      )}
      <div style={{ fontSize: 12, color: "var(--muted)" }}>Folder: <code>{x.folder}</code> · {x.files?.join(", ")}</div>
    </div>
  );
}
