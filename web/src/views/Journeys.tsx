import { ArrowRight, Layers, Plus } from "lucide-react";
import { must } from "../api";
import { useApp, useData } from "../App";
import { DESTINATIONS, STEP_HELP } from "../journeyMeta";
import { Empty, SrcBadge, mmss, useWidth } from "../ui";
import Studio from "./Studio";

// Journeys: every journey with where it stands in the guided flow; a journey opens in its studio.
export default function Journeys() {
  const { route } = useApp();
  if (route.arg) return <Studio key={route.arg} jref={route.arg} />;
  return <JourneyIndex />;
}

const STEP_NAMES = ["Purpose", "Gather", "Order", "Look", "Check", "Export"];

export function JourneyTable({ journeys, limit }: { journeys: any[]; limit?: number }) {
  const { go } = useApp();
  const narrow = useWidth() < 760;
  if (narrow) return (
    <div className="reslist">
      {journeys.slice(0, limit ?? journeys.length).map((j) => (
        <div key={j.ref} className="res" style={{ cursor: "pointer" }} onClick={() => go("journeys", j.ref, j.next ? { step: j.next } : {})}>
          <div style={{ minWidth: 0 }}>
            <div className="row nowrap tight"><span className="mono faint">{j.ref}</span><b className="ellipsis">{j.title}</b></div>
            <div className="row nowrap tight" style={{ marginTop: 3 }}>
              <span className="pips">{j.states.map((s: string, k: number) => <i key={k} className={s} />)}</span>
              <span className="muted2 ellipsis">{j.next ? <>next: <b style={{ color: "var(--text)" }}>{STEP_HELP[j.next]?.title || j.next_title}</b></> : "exported"} · {mmss(j.duration_s)}</span>
            </div>
          </div>
          <ArrowRight size={14} className="faint" />
        </div>
      ))}
    </div>
  );
  return (
    <table className="table">
      <thead><tr><th style={{ width: 40 }}></th><th>Journey</th>{!narrow && <th>Goes to</th>}<th>Steps</th>{!narrow && <th>Length</th>}{!narrow && <th>Sources</th>}<th></th></tr></thead>
      <tbody>
        {journeys.slice(0, limit ?? journeys.length).map((j) => (
          <tr key={j.ref} className="click" onClick={() => go("journeys", j.ref)}>
            <td className="mono faint">{j.ref}</td>
            <td style={{ minWidth: 0 }}>
              <b>{j.title}</b>
              {j.intent && <div className="muted2 ellipsis" style={{ maxWidth: 460 }}>{j.intent}</div>}
            </td>
            {!narrow && <td><div className="row tight">{j.formats.length ? j.formats.map((f: string) => <span key={f} className="chip">{DESTINATIONS.find((d) => d.key === f)?.label.split(",")[0] || f}</span>)
              : <span className="faint">—</span>}</div></td>}
            <td>
              <div className="row nowrap tight">
                <span className="pips" data-tip={j.states.map((s: string, k: number) => `${STEP_NAMES[k]}: ${s}`).join(" · ")}>{j.states.map((s: string, k: number) => <i key={k} className={s} />)}</span>
                <span className="muted2 nowrap">{j.next ? <>next: <b style={{ color: "var(--text)" }}>{STEP_HELP[j.next]?.title || j.next_title}</b></> : "exported"}</span>
              </div>
            </td>
            {!narrow && <td className="mono nowrap">{mmss(j.duration_s)} <span className="faint">· {j.slots}</span></td>}
            {!narrow && <td><div className="row tight">{j.sources.slice(0, 6).map((s: string) => <SrcBadge key={s} ref_={s} />)}</div></td>}
            <td style={{ textAlign: "right" }}>
              <button className="btn small" onClick={(e) => { e.stopPropagation(); go("journeys", j.ref, j.next ? { step: j.next } : {}); }}>
                {j.next ? "Continue" : "Open"}<ArrowRight size={12} /></button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function JourneyIndex() {
  const { newJourney } = useApp();
  const { data, error } = useData(() => must<any>("project.checklist"));
  const journeys = data?.journeys || [];
  return (
    <div className="page">
      <div className="pagehead">
        <div className="titles">
          <h1 className="h1">Journeys</h1>
          <p className="sub">Moments from any of your sources, strung into one piece for Shorts, YouTube or the community hub. Each walks you through
            purpose → gather → order → look → check → export.</p>
        </div>
        <button className="btn primary" onClick={newJourney} data-tip="Start a guided journey" data-tip-key="n"><Plus size={14} />New journey</button>
      </div>
      {error && <div className="err">{error}</div>}
      {!data && <div className="muted2">Loading…</div>}
      {data && !journeys.length && (
        <Empty icon={<Layers size={14} />} title="No journeys yet"
               actions={<button className="btn primary" onClick={newJourney}><Plus size={14} />Start your first journey</button>}>
          Name it, say what it is for and where people will see it. Then gather moments from your sources: the studio guides you to an export.
        </Empty>
      )}
      {!!journeys.length && <JourneyTable journeys={journeys} />}
    </div>
  );
}
