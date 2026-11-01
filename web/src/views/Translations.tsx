import { useEffect, useMemo, useState } from "react";
import { Clapperboard, Eraser, Image, Languages, Plus, Replace, Save, Sparkles, Wand2 } from "lucide-react";
import { fileUrl, must, verb } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { FilterBar, useFilters } from "../filters";
import { Dialog, Disclosure, Empty, Menu } from "../ui";
import { DubSettingsDialog } from "./DubSettings";

const COMMON_LANGS: [string, string][] = [["am", "Amharic"], ["om", "Oromo"], ["sw", "Swahili"], ["fr", "French"], ["es", "Spanish"], ["ar", "Arabic"],
  ["pt", "Portuguese"], ["de", "German"], ["hi", "Hindi"], ["ti", "Tigrinya"], ["so", "Somali"], ["zh", "Chinese"]];

// Translation editor: every line of a journey in one language, its length against the time it is spoken in,
// and the caption box it has to fit. Edits go through `lang edit`; the agent runs the same verbs in bulk.
// Laid out like the rest of the viewer: one command row (what you are editing, then the commands), the caption
// box folded into one line, the filters, the lines, and a status bar that saves.
export default function Translations({ journeys, profiles }: { journeys: any[]; profiles: any[] }) {
  const [f, setF] = useFilters();
  const { go } = useApp();
  const jref = f.tj || f.journey || journeys[0]?.ref || "";  // `journey` is how the studio's export step links here
  const journey = journeys.find((j) => j.ref === jref);
  const { data: status, reload: reloadStatus } = useData(() => (jref ? must<any>("lang.status", { journey: jref }) : Promise.resolve(null)), [jref]);
  const langs = Object.keys(status?.languages || {}).filter((l) => l !== (journey?.language || "en"));
  const lang = f.tl || langs[0] || "";
  const profile = f.tp || "shorts";
  const { data, error, reload } = useData(() => (jref && lang ? must<any>("lang.lines", { journey: jref, lang, profile }) : Promise.resolve(null)), [jref, lang, profile]);
  const { data: prof } = useData(() => must<any>("profile.show", { name: profile }), [profile]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [sheet, setSheet] = useState<string | null>(null);
  const [dialog, setDialog] = useState<null | "add" | "replace" | "redraft" | "dub">(null);
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
  const missing = (data?.lines || []).filter((l: any) => !l.text).length;

  if (!journeys.length) {
    return <Empty icon={<Languages size={16} />} title="No journeys yet" actions={<button className="btn primary" onClick={() => go("journeys")}>Go to journeys</button>}>
      Build a journey first, then translate it here.</Empty>;
  }
  return (
    <div>
      <div className="cmdrow boxed" role="toolbar" aria-label="Translation commands">
        <div className="cmdgroup" role="group" aria-label="What you are editing">
          <Languages size={14} className="faint" />
          <select className="input small" value={jref} onChange={(e) => setF("tj", e.target.value)} aria-label="Journey" style={{ maxWidth: 220 }} data-tip="The journey to translate">
            {journeys.map((j) => <option key={j.ref} value={j.ref}>{j.ref} · {j.title}</option>)}
          </select>
          <select className="input small" value={lang} onChange={(e) => setF("tl", e.target.value)} aria-label="Language" disabled={!langs.length} data-tip="The language you are editing (coverage)">
            {!langs.length && <option value="">no languages yet</option>}
            {langs.map((l) => <option key={l} value={l}>{l} · {status.languages[l].coverage}{status.languages[l].complete ? "" : " (incomplete)"}</option>)}
          </select>
          <button className="btn small ghost" onClick={() => setDialog("add")} data-tip="Add a language: a Google draft now, or ask the agent for a proper translation"><Plus size={13} />Language</button>
        </div>
        <div className="cmdgroup" role="group" aria-label="Caption box">
          <select className="input small" value={profile} onChange={(e) => setF("tp", e.target.value)} aria-label="Caption box format" style={{ maxWidth: 200 }}
                  data-tip="Which export's caption box the lines must fit">
            {profiles.filter((p) => p.name !== "preview").map((p) => <option key={p.name} value={p.name}>fit to {p.name} {p.size}</option>)}
          </select>
        </div>
        {lang && data && (
          <div className="cmdgroup" role="group" aria-label="Draft and fix">
            <Act verb="lang.translate" args={{ journey: jref, to: lang, engine: "google" }} small ghost icon={<Wand2 size={12} />} agent disabled={!missing}
                 title={missing ? `Draft the ${missing} line(s) that have no translation` : "Every line has a translation"}>Draft missing</Act>
            <button className="btn small ghost" onClick={() => setDialog("replace")} data-tip="Find and replace in this language"><Replace size={12} />Replace</button>
            <button className="btn small ghost" onClick={() => setDialog("dub")} data-tip="The LLM dubber: route by language, middle languages, MT and checks"><Sparkles size={12} />LLM dub</button>
          </div>
        )}
        {lang && data && (
          <div className="cmdgroup end">
            <Menu small label="More for this language" items={[
              { header: `${jref} · ${lang}` },
              { label: "Make a caption sheet", icon: <Image size={14} />, desc: "Every caption as it will look, on one image",
                onSelect: async () => { const env = await run("export.caption-sheet", { journey: jref, profile, lang }, { label: "Caption sheet" }); if (env.ok) setSheet(fileUrl(env.data.file) + "&v=" + Date.now()); } },
              { label: `Export ${jref} in ${lang} (${profile})`, icon: <Clapperboard size={14} />, disabled: !!n, desc: n ? "Save your changes first" : "A dubbed video with these captions",
                onSelect: () => run("export.run", { journey: jref, profiles: [profile], langs: [lang] }, { label: `Export ${jref} ${profile} ${lang}` }) },
              { label: "Open the journey's export step", icon: <Clapperboard size={14} />, onSelect: () => go("journeys", jref, { step: "export" }) },
              "sep",
              { label: "Redo the Google drafts…", icon: <Eraser size={14} />, desc: "Clears machine drafts; your and the agent's lines stay", onSelect: () => setDialog("redraft") },
            ]} />
          </div>
        )}
      </div>
      {error && <div className="err">{error}</div>}
      {lang && data && (
        <>
          <div className="panel" style={{ marginBottom: 8 }}>
            <div className="pbody" style={{ padding: "4px 10px" }}>
              <Disclosure id="tr.capbox" label={<span>Caption box for <b>{lang}</b> in {profile}: {box?.max_chars} characters × {box?.max_lines} rows, font ×{box?.scale}
                <span className="faint">{Object.keys(override).length ? " (set for this language)" : " (default)"}</span></span>}>
                <div className="row">
                  <label className="muted2 row tight nowrap">Row length <input className="input small" type="number" style={{ width: 64 }} value={chars}
                         onChange={(e) => setChars(e.target.value === "" ? "" : Number(e.target.value))} placeholder="auto" /></label>
                  <label className="muted2 row tight nowrap">Font scale <input className="input small" type="number" step="0.05" style={{ width: 64 }} value={scale}
                         onChange={(e) => setScale(e.target.value === "" ? "" : Number(e.target.value))} placeholder="1.0" /></label>
                  <Act verb="profile.edit" args={{ name: profile, caption_lang: capSpec }} small onDone={reload} title={`Saves this box for ${lang} in every ${profile} export`}>Set for {lang}</Act>
                  <div className="spacer" />
                  <Act verb="export.caption-sheet" args={{ journey: jref, profile, lang }} small icon={<Image size={12} />}
                       onDone={(env) => setSheet(fileUrl(env.data.file) + "&v=" + Date.now())} title="Every caption as it will look, on one image">Caption sheet</Act>
                </div>
                <p className="help" style={{ margin: "4px 0 0", fontSize: 11.5, color: "var(--faint)" }}>Make a caption sheet to see the real line breaks; change the row length or font only if lines wrap badly. Empty means automatic.</p>
              </Disclosure>
              {sheet && <a href={sheet} target="_blank" rel="noreferrer" data-tip="Open full size"><img src={sheet} alt="Caption sheet" className="sheet" style={{ marginTop: 6, maxWidth: "100%", maxHeight: 340, display: "block", border: "1px solid var(--line)" }} /></a>}
            </div>
          </div>
          <FilterBar count={rows.length} noun={rows.length === 1 ? "line" : "lines"} keep={["tj", "tl", "tp", "tab", "journey"]} primary={3} fields={[
            { key: "q", label: "Text", type: "text", placeholder: "Find in the source or the translation" },
            { key: "over", label: `Too long to speak (${data.over_budget})`, type: "check" },
            { key: "missing", label: `Missing (${missing})`, type: "check" },
          ]} extra={<span className="chip" data-tip="Lines translated, of all lines">coverage {data.coverage}</span>} />
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
                      <textarea className={"input lineedit" + (edits[l.key] != null ? " dirty" : "")} rows={Math.max(1, Math.ceil(text.length / 60))} aria-label={`Translation of ${l.key}`}
                                value={text} placeholder="(not translated)" onChange={(e) => setEdits({ ...edits, [l.key]: e.target.value })} />
                    </td>
                    <td>
                      {fit != null && (
                        <div data-tip={fit > 1.15 ? "Too long to speak in its time: shorten it" : fit > 1 ? "Tight: it may run a little long" : "Fits its time"}>
                          <div className={"fit" + (fit > 1.15 ? " bad" : fit > 1 ? " tight" : "")}><i style={{ width: `${Math.min(100, fit * 80)}%` }} /></div>
                          <div className="muted2">{text.length}/{l.budget} chars{l.screens ? ` · ${l.screens} screen${l.screens > 1 ? "s" : ""}` : ""}</div>
                        </div>
                      )}
                    </td>
                    <td><span className={"chip " + (l.by === "user" ? "user" : l.by === "agent" ? "agent" : "")}>{l.by || ""}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!rows.length && <div className="muted2" style={{ padding: 8 }}>No line matches the filters.</div>}
          <div className={"savebar" + (n ? " live" : "")}>
            <span className={n ? "" : "muted2"}>{n ? <b>{n} line{n > 1 ? "s" : ""} changed</b> : "Edit any line; the fit bar shows whether it can be spoken in its time."}</span>
            <div className="spacer" />
            {!!n && <button className="btn small ghost" onClick={() => setEdits({})}>Discard</button>}
            <Act verb="lang.edit" args={{ journey: jref, lang, lines: edits }} small primary disabled={!n} icon={<Save size={12} />}
                 onDone={() => { setEdits({}); reload(); }}>Save lines</Act>
          </div>
        </>
      )}
      {!lang && status && (
        <Empty icon={<Languages size={16} />} title={`${jref} has no translations yet`}
               actions={<button className="btn primary" onClick={() => setDialog("add")}><Plus size={14} />Add a language</button>}>
          Draft one with Google and fix it line by line here, or ask the agent: “translate {jref} into Amharic”.
        </Empty>
      )}
      {dialog === "add" && <AddLanguage jref={jref} have={langs} onClose={() => setDialog(null)} onAdded={(l) => { setDialog(null); reloadStatus(); setF("tl", l); }} />}
      {dialog === "dub" && <DubSettingsDialog target={jref} to={lang} title={`LLM dub of ${jref} into ${lang}`} onClose={() => setDialog(null)}
                                              scopes={[[jref, `this journey (${jref})`], ["project", "the project"], ["studio", "the studio (every project)"]]} />}
      {dialog === "replace" && <LangReplace lang={lang} jref={jref} onClose={() => setDialog(null)} onDone={() => { setDialog(null); reload(); }} />}
      {dialog === "redraft" && (
        <Dialog title={`Redo the Google drafts of ${jref} in ${lang}?`} sub="Clears the lines Google drafted; yours and the agent's stay. Then “Draft missing” drafts them again. Undo brings them back."
                onClose={() => setDialog(null)} footer={<><div className="spacer" /><button className="btn" onClick={() => setDialog(null)}>Keep them</button>
                  <Act verb="lang.clear" args={{ journey: jref, lang, method: "google" }} className="danger" onDone={() => { setDialog(null); reload(); }}>Clear the drafts</Act></>}>
          <p className="muted2" style={{ margin: 0 }}>Coverage now: {data?.coverage}</p>
        </Dialog>
      )}
    </div>
  );
}

function AddLanguage({ jref, have, onClose, onAdded }: { jref: string; have: string[]; onClose: () => void; onAdded: (lang: string) => void }) {
  const [code, setCode] = useState("");
  const { ask } = useActions();
  const name = COMMON_LANGS.find(([c]) => c === code)?.[1];
  return (
    <Dialog title={`Add a language to ${jref}`} sub="A Google draft is quick and rough; the agent writes a proper translation that fits the time each line is spoken in."
            icon={<Languages size={16} />} onClose={onClose}
            footer={<>
              <div className="spacer" />
              <button className="btn" onClick={onClose}>Cancel</button>
              <button className="btn" disabled={!code} onClick={async () => { await ask(`Translate ${jref} into ${name || code} (${code}): write the translations yourself, fitting each line's time budget.`, [jref]); onClose(); }}
                      data-tip="Leave the request for the agent: it sees it in `recomp ui notes`"><Sparkles size={13} />Ask the agent</button>
              <Act verb="lang.translate" args={{ journey: jref, to: code, engine: "google" }} primary disabled={!code || have.includes(code)} onDone={() => onAdded(code)}
                   title="Drafts every line now; then fix them here">Draft with Google</Act>
            </>}>
      <div className="stack">
        <div className="field"><label htmlFor="al-code">Language code</label>
          <input id="al-code" className="input" style={{ width: 120 }} list="lang-codes" value={code} placeholder="am" onChange={(e) => setCode(e.target.value.trim().toLowerCase())} />
          <datalist id="lang-codes">{COMMON_LANGS.map(([c, l]) => <option key={c} value={c}>{l}</option>)}</datalist>
          <span className="help">{have.includes(code) ? `${jref} already has ${code}.` : name ? name : "Two letters, e.g. am, om, sw, fr."}</span>
        </div>
        <div className="row tight">
          {COMMON_LANGS.slice(0, 6).filter(([c]) => !have.includes(c)).map(([c, l]) => (
            <button key={c} type="button" className={"btn small" + (code === c ? " on" : "")} onClick={() => setCode(c)}>{l}</button>
          ))}
        </div>
      </div>
    </Dialog>
  );
}

function LangReplace({ lang, jref, onClose, onDone }: { lang: string; jref: string; onClose: () => void; onDone: () => void }) {
  const [find, setFind] = useState("");
  const [repl, setRepl] = useState("");
  const [prev, setPrev] = useState<any>(null);
  const args = { lang, find, replace: repl, journey: jref };
  const dry = async () => setPrev((await verb("lang.replace", { ...args, dry_run: true })).data);
  return (
    <Dialog title={`Find and replace in ${lang}`} sub={`In ${jref}'s ${lang} lines. Preview, then replace; one undo takes it back.`} icon={<Replace size={16} />} onClose={onClose}
            footer={<>
              <span className="muted2">{prev ? `${prev.replaced || 0} line(s) would change` : "Preview first"}</span>
              <div className="spacer" />
              <button className="btn" onClick={onClose}>Close</button>
              <button className={"btn" + (prev ? "" : " primary")} disabled={!find} onClick={dry}>Preview</button>
              <Act verb="lang.replace" args={args} primary disabled={!prev?.replaced} onDone={onDone}>{`Replace ${prev?.replaced ?? ""}`}</Act>
            </>}>
      <form className="grid2" onSubmit={(e) => { e.preventDefault(); if (find) dry(); }}>
        <div className="field"><label htmlFor="lr-find">Find</label><input id="lr-find" className="input" value={find} onChange={(e) => { setFind(e.target.value); setPrev(null); }} /></div>
        <div className="field"><label htmlFor="lr-repl">Replace with</label><input id="lr-repl" className="input" value={repl} onChange={(e) => { setRepl(e.target.value); setPrev(null); }} /></div>
        <button type="submit" hidden />
      </form>
      {prev?.changes && (
        <div className="previewlist" style={{ marginTop: 8 }}>
          {prev.changes.slice(0, 12).map((c: any) => <div key={c.key || c.line}><span className="mono faint">{c.key || c.line}</span> <s>{c.before}</s><br />→ {c.after}</div>)}
        </div>
      )}
    </Dialog>
  );
}
