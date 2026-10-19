import { useState } from "react";
import { Copy, FolderOpen, Play, RefreshCw, Upload } from "lucide-react";
import { fileUrl, must } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { FilterBar, useFilters } from "../filters";
import Translations from "./Translations";
import { Disclosure, Empty } from "../ui";

export default function Exports() {
  const { route, go } = useApp();
  const [f, setF] = useFilters();
  const tab = f.tab || "renders";
  const { data: all, error } = useData(() => must<any[]>("export.status", { limit: 200 }));
  const { data: journeys } = useData(() => must<any[]>("journey.list"));
  const { data: profs } = useData(() => must<any[]>("profile.list"));
  const [j, setJ] = useState(route.params.get("journey") || "");
  const [chosen, setChosen] = useState<string[]>(["shorts", "landscape"]);
  const [langs, setLangs] = useState("");
  const current = route.arg;

  const target = j || journeys?.[0]?.ref || "";
  const langList = langs ? langs.split(",").map((x) => x.trim()).filter(Boolean) : [];
  const list = (all || []).filter((x) => (!f.journey || x.of === f.journey) && (!f.profile || x.profile === f.profile) &&
    (!f.lang || x.lang === f.lang) && (!f.status || (f.status === "problems" ? x.status !== "done" : x.status === f.status)) && (f.previews || !x.preview));

  return (
    <div className="page">
      <div className="pagehead">
        <div className="titles">
          <h1 className="h1">Exports</h1>
          <p className="sub">Every render with its captions, a ready-to-paste description with full credits, and the recipe. You upload them yourself.</p>
        </div>
        <Act verb="project.reveal" args={{ what: "exports" }} quiet icon={<FolderOpen size={14} />}>Exports folder</Act>
      </div>
      <div className="segmented" style={{ marginBottom: 20 }} role="tablist">
        <button className={tab === "renders" ? "on" : ""} onClick={() => setF("tab", null)}>Renders</button>
        <button className={tab === "translations" ? "on" : ""} onClick={() => setF("tab", "translations")}>Translations</button>
      </div>
      {tab === "translations" ? <Translations journeys={journeys || []} profiles={profs || []} /> : <>
      <div className="callout" style={{ marginBottom: 16 }}>
        <Upload size={14} />
        <div className="grow">To export a journey, open it: its last step, <b>Export &amp; share</b>, renders every destination and language.
          <div className="row tight" style={{ marginTop: 8 }}>
            {(journeys || []).slice(-4).map((x) => <button key={x.ref} className="btn small" onClick={() => go("journeys", x.ref, { step: "export" })}>{x.ref} · {String(x.title).slice(0, 28)}</button>)}
          </div>
        </div>
      </div>
      <div style={{ marginBottom: 16 }}>
        <Disclosure id="exports.quick" label="Quick export (advanced)">
          <div className="card row">
            <select className="input" value={j} onChange={(e) => setJ(e.target.value)} aria-label="Journey">
              {(journeys || []).map((x) => <option key={x.ref} value={x.ref}>{x.ref} · {x.title} ({String(x.duration).replace(/^00:/, "")})</option>)}
            </select>
            {(profs || []).filter((p) => p.name !== "preview").map((p) => (
              <label key={p.name} className={"btn small" + (chosen.includes(p.name) ? " on" : "")} style={{ cursor: "pointer" }} data-tip={p.description}>
                <input type="checkbox" checked={chosen.includes(p.name)} onChange={(e) => setChosen(e.target.checked ? [...chosen, p.name] : chosen.filter((x) => x !== p.name))} /> {p.name}
              </label>
            ))}
            <input className="input" style={{ width: 160 }} placeholder="langs, e.g. en,am,sw" value={langs} onChange={(e) => setLangs(e.target.value)} />
            <Act verb="preview" args={{ target, profile: chosen[0] || "landscape" }} disabled={!target}>Preview</Act>
            <Act verb="export.run" args={{ journey: target, profiles: chosen, langs: langList }} primary agent disabled={!target || !chosen.length}>Export</Act>
          </div>
        </Disclosure>
      </div>
      {error && <div className="err">{error}</div>}
      <FilterBar count={list.length} keep={["tab"]} fields={[
        { key: "journey", label: "Journey", type: "select", options: (journeys || []).map((x) => [x.ref, `${x.ref} ${x.title}`] as [string, string]) },
        { key: "profile", label: "Profile", type: "select", options: Array.from(new Set((all || []).map((x) => x.profile))) },
        { key: "lang", label: "Language", type: "select", options: Array.from(new Set((all || []).map((x) => x.lang))) },
        { key: "status", label: "Status", type: "select", options: ["done", "running", "queued", "failed", ["problems", "not done"]] },
        { key: "previews", label: "Show previews", type: "check" },
      ]} />
      <div className="jgrid" style={{ gridTemplateColumns: current ? "minmax(280px, 400px) minmax(0, 1fr)" : "minmax(0, 1fr)" }}>
        <div>
          {list.map((x) => (
            <div key={x.ref} className={"card pad-sm click" + (x.ref === current ? " sel" : "")} style={{ marginBottom: 10 }}
                 onClick={() => go("exports", x.ref)}>
              <div className="row">
                <b className="mono">{x.ref}</b><span>{x.of} · {x.title}</span><div className="spacer" />
                <span className={"chip " + (x.status === "done" ? "done" : x.status.includes("problem") || x.status === "failed" ? "failed" : "running")}>{x.status}</span>
              </div>
              <div className="muted2">{x.preview ? "preview · " : ""}{x.profile} · {x.lang}{x.seconds ? ` · rendered in ${x.seconds}s` : ""}</div>
              {x.progress != null && x.status !== "done" && <div className="bar" style={{ marginTop: 8 }}><i style={{ width: `${Math.round(x.progress * 100)}%` }} /></div>}
              {x.error && <div className="err" style={{ fontSize: 12 }}>{x.error}</div>}
              {!!x.problems.length && <div className="muted2" style={{ color: "var(--red)" }}>{x.problems.map((p: any) => p.check).join(", ")}</div>}
            </div>
          ))}
          {all && !list.length && <Empty icon={<Upload size={14} />} title={all.length ? "No exports match these filters" : "No exports yet"}>{all.length ? "Clear a filter to see more." : "Open a journey and follow it to its last step, Export & share."}</Empty>}
        </div>
        <div>{current && <ExportDetail key={current} xref={current} />}</div>
      </div>
      </>}
    </div>
  );
}

function DubFix({ x }: { x: any }) {
  const [edits, setEdits] = useState<Record<string, string>>({});
  const { run } = useActions();
  const lines = x.dub.to_fix as any[];
  const save = async (rerender: boolean) => {
    const env = await run("lang.edit", { journey: x.of, lang: x.lang, lines: edits }, { label: `Save ${Object.keys(edits).length} ${x.lang} line(s)` });
    if (!env.ok) return;
    if (rerender) await run("export.run", { journey: x.of, profiles: [x.profile], langs: [x.lang] }, { label: `Re-export ${x.lang}` });
    setEdits({});
  };
  return (
    <div style={{ marginTop: 10 }}>
      <div className="row"><b>Dub</b><span className="chip">{x.dub.backend} {x.dub.voice}</span>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>{x.dub.lines} lines · {x.dub.sped_up} sped up</span></div>
      {!lines.length && <div style={{ color: "var(--accent)", fontSize: 12 }}>Every line fits.</div>}
      {!!lines.length && <div style={{ fontSize: 12, color: "var(--muted)" }}>Lines that don't fit their time: shorten them, then re-export this language. Kept lines play in the original voice.</div>}
      {lines.map((l) => (
        <div key={l.key} style={{ borderTop: "1px solid var(--line)", padding: "4px 0" }}>
          <div className="row" style={{ fontSize: 12 }}>
            <span className="mono">{l.at.toFixed(1)}s</span>
            <span className={"chip " + (l.kind === "overflow" ? "failed" : "")}>{l.kind === "overflow" ? `+${l.over_s}s` : "original voice"}</span>
            <span style={{ color: "var(--muted)" }}>{l.source_text}</span>
          </div>
          <input className="input" style={{ width: "100%" }} defaultValue={l.text} onChange={(e) => setEdits({ ...edits, [l.key]: e.target.value })} />
        </div>
      ))}
      {!!Object.keys(edits).length && (
        <div className="row" style={{ marginTop: 6 }}>
          <button className="btn small" onClick={() => save(false)}>Save lines</button>
          <button className="btn small primary" onClick={() => save(true)}>Save and re-export {x.lang}</button>
        </div>
      )}
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
      <div className="row" style={{ marginBottom: 12 }}>
        <b className="h3" style={{ margin: 0 }}>{x.ref} · {x.title}</b><span className="chip">{x.profile} · {x.lang}</span><div className="spacer" />
        <Act verb="project.reveal" args={{ what: xref }} small ghost quiet icon={<FolderOpen size={12} />}>Folder</Act>
        <Act verb="export.check" args={{ ref: xref }} small icon={<RefreshCw size={12} />}>Re-check</Act>
      </div>
      {x.video ? (
        <video controls src={fileUrl(x.video)} style={vertical ? { height: "min(64vh, 560px)", maxWidth: "100%", display: "block", margin: "0 auto", background: "#000", borderRadius: 12 } : { width: "100%", maxHeight: 440, background: "#000", borderRadius: 12 }} />
      ) : <div className="empty"><Play size={14} /> Not rendered yet ({x.status}).</div>}
      <div className="row tight" style={{ marginTop: 12 }}>
        {(x.checks || []).map((c: any) => <span key={c.check} className={"chip " + (c.ok ? "done" : "failed")} title={c.detail}>{c.check}: {c.detail}</span>)}
      </div>
      {x.dub && <DubFix x={x} />}
      {x.description && (
        <div style={{ marginTop: 10 }}>
          <div className="row"><b>Description</b><div className="spacer" />
            <button className="btn small" onClick={() => { navigator.clipboard.writeText(x.description); setCopied(true); setTimeout(() => setCopied(false), 1500); }}><Copy size={12} />{copied ? "Copied" : "Copy"}</button>
          </div>
          <pre className="desc">{x.description}</pre>
        </div>
      )}
      <Disclosure id="exports.files" label="Files"><div className="muted2">Folder: <code>{x.folder}</code><br />{x.files?.join(", ")}</div></Disclosure>
    </div>
  );
}
