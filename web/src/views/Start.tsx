import { useState } from "react";
import { FolderPlus } from "lucide-react";
import { must, verb } from "../api";
import { useApp, useData } from "../App";

export default function Start() {
  const { openProject } = useApp();
  const { data, error } = useData(() => must<any>("project.list"));
  const [name, setName] = useState("");
  const [kind, setKind] = useState("mixed");
  const [msg, setMsg] = useState<string | null>(null);

  const create = async () => {
    if (!name.trim()) return;
    const env = await verb("project.init", { path: name.trim(), kind });
    if (!env.ok) setMsg(env.error!.message);
    else openProject(env.data.name);
  };

  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <h1 className="h1">Projects</h1>
      <p className="sub">A project is a folder of sources, their transcripts, chapters, cuts and journeys. Work on it here and with an agent in the same folder.</p>
      <div className="guide">
        <b>How this works.</b> Open a project, add films, podcasts or links, and let your agent (Claude Code in the project folder, or the
        <code> recomposer</code> MCP tools) read transcripts, write chapters and make cuts while you watch and correct here. Everything either of
        you does shows up live and can be undone.
      </div>
      {error && <div className="err">{error}</div>}
      <table className="table">
        <thead><tr><th>Project</th><th>Folder</th><th></th></tr></thead>
        <tbody>
          {(data?.projects || []).map((p: any) => (
            <tr key={p.name} className="click" onClick={() => p.exists && openProject(p.name)}>
              <td><b>{p.name}</b> {p.current && <span className="chip done">current</span>}</td>
              <td className="mono" style={{ color: "var(--muted)" }}>{p.path}</td>
              <td>{!p.exists && <span className="chip failed">missing</span>}</td>
            </tr>
          ))}
          {data && !data.projects.length && <tr><td colSpan={3} className="empty">No projects yet.</td></tr>}
        </tbody>
      </table>
      <div className="card" style={{ marginTop: 14 }}>
        <div className="row">
          <FolderPlus size={16} />
          <input className="input grow" placeholder="New project name (a folder under the projects root, or a full path)" value={name}
                 onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && create()} />
          <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
            {["movies", "channel", "speaker", "topic", "mixed"].map((k) => <option key={k}>{k}</option>)}
          </select>
          <button className="btn primary" onClick={create}>Create</button>
        </div>
        {msg && <div className="err">{msg}</div>}
      </div>
    </div>
  );
}
