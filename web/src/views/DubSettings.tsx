import { useEffect, useState } from "react";
import { Mic, Sparkles } from "lucide-react";
import { must } from "../api";
import { useData } from "../App";
import { Act, useActions } from "../actions";
import { Dialog } from "../ui";

// The LLM dubber's settings (`recomp dub settings`). Layers, lowest first: studio → project → source → journey.
// Every value shows the layer it comes from; saving writes only what you changed, at the layer you pick.

export const ROUTES: [string, string, string][] = [
  ["auto", "Auto", "Chosen by language strength: direct, source, target or middle"],
  ["direct", "Direct", "The LLM reads the source and writes the target (both languages it knows well)"],
  ["source", "Source language (src-en)", "The LLM writes in the source language; MT carries it into the target; back-translations are checked"],
  ["target", "Target language (tgt-en)", "The LLM understands the source through MT views and writes the target itself"],
  ["middle", "Middle language (mid-en)", "Both ends MT-only: understand and write in one middle language (English)"],
  ["multi", "Several middle languages", "Both ends MT-only: understand through two or more middle languages from different MT systems (e.g. English + Spanish)"],
];
const ENGINES: [string, string][] = [["google", "Google"], ["nllb", "NLLB-200 (worker)"], ["bergamot", "Mozilla bergamot (worker)"]];

export type DubFields = {
  route?: string; middle?: string[]; budget?: string; views_mt?: string[]; mt?: string; verify?: string; conserve?: boolean; targets?: string[];
};

const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

// The controls alone: used when adding sources (passed to `source add --dub-…`) and inside the settings dialog.
export function DubFieldsForm({ value, onChange, from, withTargets }: {
  value: DubFields; onChange: (v: DubFields) => void; from?: Record<string, string>; withTargets?: boolean;
}) {
  const set = (k: keyof DubFields, v: any) => onChange({ ...value, [k]: v });
  const route = value.route || "auto";
  const origin = (k: string) => (from?.[k] ? <span className="help">from {from[k]}</span> : null);
  return (
    <div className="stack">
      {withTargets && (
        <div className="field"><label htmlFor="dub-targets">Dub into</label>
          <input id="dub-targets" className="input" style={{ width: 220 }} placeholder="om, am" value={(value.targets || []).join(", ")}
                 onChange={(e) => set("targets", list(e.target.value))} />
          <span className="help">Languages this media is for (a note the agent sees with the settings)</span>
        </div>
      )}
      <div className="field"><label htmlFor="dub-route">Route</label>
        <select id="dub-route" className="input" value={route} onChange={(e) => set("route", e.target.value)}>
          {ROUTES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <span className="help">{ROUTES.find(([k]) => k === route)?.[2]}</span>{origin("route")}
      </div>
      <div className="row">
        <div className="field"><label htmlFor="dub-middle">Middle language(s)</label>
          <input id="dub-middle" className="input" style={{ width: 140 }} placeholder="en" value={(value.middle || []).join(", ")}
                 onChange={(e) => set("middle", list(e.target.value))} />
          <span className="help">{route === "multi" ? "Two or more, e.g. en, es" : "Used by target, middle and multi routes"}</span>{origin("middle")}
        </div>
        <div className="field"><label htmlFor="dub-views">MT for the views</label>
          <input id="dub-views" className="input" style={{ width: 170 }} placeholder="google" value={(value.views_mt || []).join(", ")}
                 onChange={(e) => set("views_mt", list(e.target.value))} />
          <span className="help">One per middle language: google, nllb, bergamot</span>{origin("views_mt")}
        </div>
      </div>
      <div className="row">
        <div className="field"><label htmlFor="dub-budget">Budget</label>
          <select id="dub-budget" className="input" value={value.budget || "economy"} onChange={(e) => set("budget", e.target.value)}>
            <option value="economy">Economy: one writing language</option>
            <option value="quality">Quality: two writing languages, pooled</option>
          </select>{origin("budget")}
        </div>
        <div className="field"><label htmlFor="dub-mt">MT into the target</label>
          <select id="dub-mt" className="input" value={value.mt || "google"} onChange={(e) => set("mt", e.target.value)}>
            {ENGINES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>{origin("mt")}
        </div>
        <div className="field"><label htmlFor="dub-verify">Back-translation checks</label>
          <select id="dub-verify" className="input" value={value.verify || "auto"} onChange={(e) => set("verify", e.target.value)}>
            <option value="auto">When MT crosses into a weak language</option>
            <option value="always">Always</option>
            <option value="never">Never</option>
          </select>{origin("verify")}
        </div>
      </div>
      <label className="row tight"><input type="checkbox" checked={!!value.conserve} onChange={(e) => set("conserve", e.target.checked)} />
        Meaning-conserving mode <span className="muted2">(adds nothing to fill time; a short silence instead)</span>{origin("conserve")}</label>
    </div>
  );
}

// Only what changed against the effective settings, ready for `dub settings --at …` or `source add --dub-…`.
export function changedFields(v: DubFields, base: Record<string, any> = {}): DubFields {
  const out: any = {};
  (Object.keys(v) as (keyof DubFields)[]).forEach((k) => {
    if (JSON.stringify(v[k]) !== JSON.stringify(base[k]) && v[k] !== undefined) out[k] = v[k];
  });
  return out;
}

export const asSourceAddArgs = (v: DubFields) => {
  const out: Record<string, any> = {};
  if (v.route && v.route !== "auto") out.dub_route = v.route;
  if (v.middle?.length) out.dub_middle = v.middle;
  if (v.budget && v.budget !== "economy") out.dub_budget = v.budget;
  if (v.views_mt?.length) out.dub_views_mt = v.views_mt;
  if (v.mt && v.mt !== "google") out.dub_mt = v.mt;
  if (v.targets?.length) out.dub_to = v.targets;
  return out;
};

// The dialog: pick the layer, see where each value comes from and the route it gives for a language.
export function DubSettingsDialog({ target, to, scopes, onClose, title }: {
  target?: string; to?: string; scopes: [string, string][]; onClose: () => void; title?: string;
}) {
  const [at, setAt] = useState(scopes[0][0]);
  const [lang, setLang] = useState(to || "");
  const { ask } = useActions();
  const { data, reload } = useData(() => must<any>("dub.settings", { target: target || undefined, to: lang || undefined }), [target, lang]);
  const eff = data?.sources ? data.sources[0] : data;
  const [v, setV] = useState<DubFields>({});
  useEffect(() => { if (eff?.settings) setV({ ...eff.settings }); }, [JSON.stringify(eff?.settings)]);
  const changes = changedFields(v, eff?.settings || {});
  const plan = eff?.plan;
  return (
    <Dialog title={title || "LLM dub settings"} icon={<Mic size={16} />} onClose={onClose} wide
            sub="How the LLM dubber works for this media: which languages it reads and writes in, and where machine translation crosses."
            footer={<>
              {target && lang && <button className="btn" onClick={async () => { await ask(`Dub ${target} into ${lang} with the LLM dubber (recomp-dub skill), using these dub settings.`, [target]); onClose(); }}
                                         data-tip="Leave the request for the agent: it sees it in `recomp ui notes`"><Sparkles size={13} />Ask the agent to dub</button>}
              <div className="spacer" />
              <Act verb="dub.settings" args={{ at, clear: ["route", "middle", "budget", "views_mt", "mt", "verify", "conserve"] }} ghost
                   confirm="Removes this layer's dub settings (they fall back to the layer below)" onDone={reload}>Reset this layer</Act>
              <Act verb="dub.settings" args={{ at, ...changes }} primary disabled={!Object.keys(changes).length} onDone={reload}>Save at {scopes.find(([k]) => k === at)?.[1]}</Act>
            </>}>
      <div className="stack">
        <div className="row">
          <div className="field"><label htmlFor="dub-at">Save at</label>
            <select id="dub-at" className="input" value={at} onChange={(e) => setAt(e.target.value)}>
              {scopes.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
            <span className="help">Lower layers apply unless a higher one sets the value: studio → project → source → journey</span>
          </div>
          <div className="field"><label htmlFor="dub-lang">Show the route for</label>
            <input id="dub-lang" className="input" style={{ width: 90 }} placeholder="om" value={lang} onChange={(e) => setLang(e.target.value.trim().toLowerCase())} />
          </div>
        </div>
        {data?.sources && data.sources.length > 1 && <div className="muted2">This journey uses {data.sources.length} sources; showing {data.sources[0].source}. Each source keeps its own route.</div>}
        <DubFieldsForm value={v} onChange={setV} from={eff?.from} />
        {plan && (
          <div className="card stack">
            <div className="row tight"><b>Route for {plan.src} → {plan.tgt}: {plan.route}</b>
              <span className="chip">reads {plan.reads.join(" + ")}</span><span className="chip">writes {plan.writes.join(" + ")}</span>
              {!!plan.back_translate.length && <span className="chip partial">checks via {plan.back_translate.map((b: any) => b.lang).join(" + ")}</span>}</div>
            <ol className="muted2" style={{ margin: 0, paddingLeft: 18 }}>{plan.steps.map((s: string, i: number) => <li key={i}>{s}</li>)}</ol>
          </div>
        )}
      </div>
    </Dialog>
  );
}
