import { ArrowRight, Layers, Plus } from "lucide-react";
import { must } from "../api";
import { useApp, useData } from "../App";
import { DESTINATIONS, STEP_HELP } from "../journeyMeta";
import { Empty, SrcBadge, mmss } from "../ui";
import Studio from "./Studio";

// Journeys: every journey with where it stands in the guided flow; a journey opens in its studio.
export default function Journeys() {
  const { route } = useApp();
  if (route.arg) return <Studio key={route.arg} jref={route.arg} />;
  return <JourneyIndex />;
}

export function JourneyCards({ journeys, limit }: { journeys: any[]; limit?: number }) {
  const { go, newJourney } = useApp();
  return (
    <div className="jcards">
      {journeys.slice(0, limit ?? journeys.length).map((j) => (
        <div key={j.ref} className="card click jcard" role="link" tabIndex={0} onClick={() => go("journeys", j.ref)}
             onKeyDown={(e) => e.key === "Enter" && go("journeys", j.ref)}>
          <div className="row nowrap tight">
            <span className="faint mono">{j.ref}</span>
            <span className="grow" />
            {j.formats.map((f: string) => <span key={f} className="chip">{DESTINATIONS.find((d) => d.key === f)?.label.split(",")[0] || f}</span>)}
          </div>
          <div>
            <div className="jt">{j.title}</div>
            {j.intent && <div className="ji">{j.intent}</div>}
          </div>
          <div className="pips" aria-label={`${j.done} of ${j.of} steps done`}>{j.states.map((s: string, k: number) => <i key={k} className={s} />)}</div>
          <div className="row nowrap tight">
            <span className="muted2 grow">{j.slots} cut{j.slots === 1 ? "" : "s"} · {mmss(j.duration_s)}</span>
            {j.sources.slice(0, 5).map((s: string) => <SrcBadge key={s} ref_={s} />)}
          </div>
          <div className="row nowrap">
            {j.next ? <span className="muted2 grow">Next: <b style={{ color: "var(--text)" }}>{STEP_HELP[j.next]?.title || j.next_title}</b></span>
              : <span className="chip ok grow" style={{ justifyContent: "center" }}>Exported</span>}
            <button className="btn small" onClick={(e) => { e.stopPropagation(); go("journeys", j.ref, j.next ? { step: j.next } : {}); }}>
              {j.next ? "Continue" : "Open"}<ArrowRight size={15} /></button>
          </div>
        </div>
      ))}
      <button className="newcard" onClick={newJourney}><Plus size={22} />New journey</button>
    </div>
  );
}

function JourneyIndex() {
  const { newJourney } = useApp();
  const { data, error } = useData(() => must<any>("project.checklist"));
  const journeys = data?.journeys || [];
  return (
    <div className="page wide">
      <div className="pagehead">
        <div className="titles">
          <h1 className="h1">Journeys</h1>
          <p className="sub">A journey strings moments from any of your sources into one piece for Shorts, YouTube or the community hub.
            Each one walks you through purpose, cuts, order, look, check and export.</p>
        </div>
        <button className="btn primary lg" onClick={newJourney}><Plus size={18} />New journey</button>
      </div>
      {error && <div className="err">{error}</div>}
      {!data && <div className="muted2">Loading…</div>}
      {data && !journeys.length && (
        <Empty icon={<Layers size={24} />} title="No journeys yet"
               actions={<button className="btn primary lg" onClick={newJourney}><Plus size={18} />Start your first journey</button>}>
          Name it, say what it is for and where people will see it. Then gather moments from your sources: the studio guides you to an export.
        </Empty>
      )}
      {!!journeys.length && <JourneyCards journeys={journeys} />}
    </div>
  );
}
