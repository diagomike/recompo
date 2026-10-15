import { useEffect, useMemo, useState } from "react";
import { Image, Languages, Replace, Save, Wand2 } from "lucide-react";
import { fileUrl, must, verb } from "../api";
import { useData } from "../App";
import { Act, useActions } from "../actions";
import { FilterBar, useFilters } from "../filters";

// Translation editor: every line of a journey in one language, its length against the time it is spoken in,
// and the caption box it has to fit. Edits go through `lang edit`; the agent runs the same verbs in bulk.
export default function Translations({ journeys, profiles }: { journeys: any[]; profiles: any[] }) {
  const [f, setF] = useFilters();
  const jref = f.tj || journeys[0]?.ref || "";
  const { data: status } = useData(() => (jref ? must<any>("lang.status", { journey: jref }) : Promise.resolve(null)), [jref]);
  const langs = Object.keys(status?.languages || {}).filter((l) => l !== (journeys.find((j) => j.ref === jref)?.language || "en"));
  const lang = f.tl || langs[0] || "";
  const profile = f.tp || "shorts";
  const { data, error, reload } = useData(() => (jref && lang ? must<any>("lang.lines", { journey: jref, lang, profile }) : Promise.resolve(null)), [jref, lang, profile]);
  const { data: prof } = useData(() => must<any>("profile.show", { name: profile }), [profile]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [sheet, setSheet] = useState<string | null>(null);
  const [newLang, setNewLang] = useState("");
  const { run } = useActions();
  useEffect(() => { setEdits({}); setSheet(null); }, [jref, lang]);

  const rows = useMemo(() => (data?.lines || []).filter((l: any) =>
    (!f.over || l.over) && (!f.missing || !l.text) && (!f.q || (l.source + " " + (l.text || "")).toLowerCase().includes(f.q.toLowerCase()))), [data, f.over, f.missing, f.q]);
  const box = data?.caption_box;
  const override = prof?.caption_lang?.[lang] || {};
  const [chars, setChars] = useState<number | "">("");
  const [scale, setScale] = useState<number | "">("");
  useEffect(() => { setChars(override.max_chars ?? ""); setScale(override.scale ?? ""); }, [profile, lang, prof]);
  const capSpec = `${lang}:max_chars=${chars === "" ? "none" : chars},scale=${scale === "" ? "none" : scale}`;
  const n = Object.keys(edits).length;

  if (!journeys.length) return <div className="empty">No journeys yet: build one first, then translate it here.</div>;
  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <Languages size={16} />
        <select className="input" value={jref} onChange={(e) => setF("tj", e.target.value)} aria-label="Journey">
          {journeys.map((j) => <option key={j.ref} value={j.ref}>{j.ref} · {j.title}</option>)}
        </select>
        <select className="input" value={lang} onChange={(e) => setF("tl", e.target.value)} aria-label="Language">
          {!langs.length && <option value="">no translations yet</option>}
          {langs.map((l) => <option key={l} value={l}>{l} · {status.languages[l].coverage}{status.languages[l].complete ? "" : " (incomplete)"}</option>)}
        </select>
        <span className="act-wrap">
          <input className="input" style={{ width: 70 }} placeholder="new: am" value={newLang} onChange={(e) => setNewLang(e.target.value.trim())} />
          <Act verb="lang.translate" args={{ journey: jref, to: newLang, engine: "google" }} small agent disabled={!newLang}
               title="Google draft for every line; then edit here or ask the agent to translate properly"
               onDone={() => { setF("tl", newLang); setNewLang(""); }}>Draft language</Act>
        </span>
        <select className="input" value={profile} onChange={(e) => setF("tp", e.target.value)} aria-label="Profile">
          {profiles.filter((p) => p.name !== "preview").map((p) => <option key={p.name} value={p.name}>caption box: {p.name} {p.size}</option>)}
        </select>
      </div>
      {error && <div className="err">{error}</div>}
      {lang && data && (
        <>
          <div className="card capbox">
            <div className="row" style={{ gap: 6 }}>
              <b>Caption box</b>
              <span className="chip">{box?.max_chars} characters × {box?.max_lines} rows · font ×{box?.scale}</span>
              <span className="muted2">{lang} in {profile}{Object.keys(override).length ? " (override)" : " (default)"}</span>
              <div className="spacer" />
              <label className="muted2">row length <input className="input small" type="number" style={{ width: 60 }} value={chars}
                     onChange={(e) => setChars(e.target.value === "" ? "" : Number(e.target.value))} placeholder="auto" /></label>
              <label className="muted2">font <input className="input small" type="number" step="0.05" style={{ width: 64 }} value={scale}
                     onChange={(e) => setScale(e.target.value === "" ? "" : Number(e.target.value))} placeholder="1.0" /></label>
              <Act verb="profile.edit" args={{ name: profile, caption_lang: capSpec }} small onDone={reload}>Set for {lang}</Act>
              <Act verb="export.caption-sheet" args={{ journey: jref, profile, lang }} small primary icon={<Image size={12} />}
                   onDone={(env) => setSheet(fileUrl(env.data.file) + "&v=" + Date.now())}>Caption sheet</Act>
            </div>
            {sheet && <a href={sheet} target="_blank" rel="noreferrer"><img src={sheet} alt="Caption sheet" className="sheet" /></a>}
          </div>
          <FilterBar count={rows.length} keep={["tj", "tl", "tp"]} fields={[
            { key: "q", label: "Text", type: "text", placeholder: "source or translation" },
            { key: "over", label: `Too long to speak (${data.over_budget})`, type: "check" },
            { key: "missing", label: "Missing", type: "check" },
          ]} extra={<>
            <span className="chip">coverage {data.coverage}</span>
            <Act verb="lang.translate" args={{ journey: jref, to: lang, engine: "google" }} small ghost icon={<Wand2 size={12} />} agent
                 title="Draft only the lines that have no translation">Draft missing</Act>
            <LangReplace lang={lang} jref={jref} onDone={reload} />
          </>} />
          <table className="table tlines">
            <thead><tr><th style={{ width: 70 }}>At</th><th style={{ width: "34%" }}>Source</th><th>Translation</th><th style={{ width: 120 }}>Fit</th><th style={{ width: 60 }}>By</th></tr></thead>
            <tbody>
              {rows.map((l: any) => {
                const text = edits[l.key] ?? l.text ?? "";
                const fit = l.budget ? text.length / Math.max(1, l.budget) : null;
                return (
                  <tr key={l.key} className={l.over && edits[l.key] == null ? "over" : ""}>
                    <td className="mono">{l.at || l.kind}</td>
                    <td className="muted2">{l.source}</td>
                    <td>
                      <textarea className={"input lineedit" + (edits[l.key] != null ? " dirty" : "")} rows={Math.max(1, Math.ceil(text.length / 60))}
                                value={text} placeholder="(not translated)" onChange={(e) => setEdits({ ...edits, [l.key]: e.target.value })} />
                    </td>
                    <td>
                      {fit != null && (
                        <>
                          <div className={"fit" + (fit > 1.15 ? " bad" : fit > 1 ? " tight" : "")}><i style={{ width: `${Math.min(100, fit * 80)}%` }} /></div>
                          <div className="muted2">{text.length}/{l.budget} chars{l.screens ? ` · ${l.screens} screen${l.screens > 1 ? "s" : ""}` : ""}</div>
                        </>
                      )}
                    </td>
                    <td><span className={"chip " + (l.by === "user" ? "user" : l.by === "agent" ? "agent" : "")}>{l.by || ""}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className={"savebar" + (n ? " live" : "")}>
            <b>{n ? `${n} line(s) changed` : "Edit any line; the fit bar shows whether it can be spoken in its time."}</b>
            <div className="spacer" />
            {!!n && <button className="btn small ghost" onClick={() => setEdits({})}>Discard</button>}
            <Act verb="lang.edit" args={{ journey: jref, lang, lines: edits }} small primary disabled={!n} icon={<Save size={12} />}
                 onDone={() => { setEdits({}); reload(); }}>Save lines</Act>
            <button className="btn small" data-verb="export.run" disabled={!!n} onClick={() => run("export.run", { journey: jref, profiles: [profile], langs: [lang] }, { label: `Export ${jref} ${profile} ${lang}` })}>Export {lang} ({profile})</button>
          </div>
        </>
      )}
      {!lang && <div className="empty">Draft a first language above (Google), or ask the agent: “translate {jref} into Amharic”.</div>}
    </div>
  );
}

function LangReplace({ lang, jref, onDone }: { lang: string; jref: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [find, setFind] = useState("");
  const [repl, setRepl] = useState("");
  const [prev, setPrev] = useState<any>(null);
  if (!open) return <button className="btn ghost small" onClick={() => setOpen(true)}><Replace size={12} />Replace</button>;
  const args = { lang, find, replace: repl, journey: jref };
  return (
    <span className="act-wrap" style={{ position: "relative" }}>
      <input className="input small" style={{ width: 110 }} placeholder="find" value={find} onChange={(e) => { setFind(e.target.value); setPrev(null); }} />
      <input className="input small" style={{ width: 110 }} placeholder="replace" value={repl} onChange={(e) => { setRepl(e.target.value); setPrev(null); }} />
      <button className="btn small" disabled={!find} onClick={async () => setPrev((await verb("lang.replace", { ...args, dry_run: true })).data)}>Preview</button>
      <Act verb="lang.replace" args={args} small primary disabled={!prev?.replaced} onDone={() => { setPrev(null); onDone(); }}>{`Replace ${prev?.replaced ?? ""}`}</Act>
      <button className="btn ghost small" onClick={() => setOpen(false)}>×</button>
    </span>
  );
}
