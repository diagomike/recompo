import { must, verb } from "../api";
import { useData } from "../App";

export default function Jobs() {
  const { data, error } = useData(() => must<any>("job.list", { limit: 60 }));
  return (
    <div className="page">
      <h1 className="h1">Jobs</h1>
      <p className="sub">Machine work: audio, shots, ASR, downloads, renders, dubs. One heavy job runs at a time; downloads run alongside. {data && (data.runner ? "Runner active." : "Runner idle.")}</p>
      {error && <div className="err">{error}</div>}
      <table className="table">
        <thead><tr><th>Job</th><th>Type</th><th>Target</th><th>Status</th><th style={{ width: 220 }}>Progress</th><th>Time</th><th></th></tr></thead>
        <tbody>
          {(data?.jobs || []).map((j: any) => (
            <tr key={j.ref}>
              <td className="mono">{j.ref}</td><td>{j.type}</td><td className="mono">{j.target}</td>
              <td><span className={"chip " + j.status}>{j.status}</span></td>
              <td>
                <div className="bar"><i style={{ width: `${Math.round((j.progress || 0) * 100)}%` }} /></div>
                <div style={{ fontSize: 11, color: j.error ? "var(--red)" : "var(--muted)" }}>{j.error || j.message}</div>
              </td>
              <td className="mono">{j.elapsed_s != null ? `${Math.round(j.elapsed_s)}s` : ""}</td>
              <td>
                {(j.status === "running" || j.status === "queued") && <button className="btn small" onClick={() => verb("job.cancel", { ref: j.ref })}>Cancel</button>}
                {(j.status === "failed" || j.status === "cancelled") && <button className="btn small" onClick={() => verb("job.retry", { ref: j.ref })}>Retry</button>}
              </td>
            </tr>
          ))}
          {data && !data.jobs.length && <tr><td colSpan={7} className="empty">No recent jobs.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
