// The posting queue (D-10, D-23): exports you will upload yourself to your channel. Only campaign and permitted
// sources can be queued; every post credits its creators. Open one for the file and the text; link it once posted.
import { useState } from "react";
import { Copy, ExternalLink, Link2, Send, Tv } from "lucide-react";
import { must, verb } from "../api";
import { useData } from "../App";
import { Act, useActions } from "../actions";
import { useFilters } from "../filters";
import { Dialog, Empty } from "../ui";

export default function PostQueue() {
  const [f, setF] = useFilters();
  const status = f.pst || "open";
  const { data: posts, reload } = useData(() => must<any[]>("post.queue", { status }), [status]);
  const { data: ch, reload: reloadCh } = useData(() => must<any>("channel.show"));
  const [opened, setOpened] = useState<any | null>(null);
  const { toast } = useActions();
  const open = async (ref: string) => {
    const env = await verb("post.open", { ref });
    if (env.ok) { setOpened(env.data); reload(); } else toast({ ok: false, title: "Open post", detail: env.error!.message });
  };
  return (
    <>
      <ChannelRow ch={ch} onChange={reloadCh} />
      <div className="segmented" style={{ margin: "12px 0" }}>
        {[["open", "To post"], ["posted", "Posted"], ["cancelled", "Cancelled"], ["all", "All"]].map(([k, l]) => (
          <button key={k} className={status === k ? "on" : ""} onClick={() => setF("pst", k === "open" ? null : k)}>{l}</button>
        ))}
      </div>
      {posts && !posts.length && (
        <Empty icon={<Send size={14} />} title={status === "open" ? "Nothing waiting to be posted" : "None"}>
          Plan a post from a finished export (Renders tab › an export › <b>Plan a post</b>). Only sources marked campaign or permitted can be posted.
        </Empty>
      )}
      {!!posts?.length && (
        <table className="table">
          <thead><tr><th>Post</th><th>When</th><th>Format</th><th>Credits</th><th></th></tr></thead>
          <tbody>
            {posts.map((p) => (
              <tr key={p.ref}>
                <td><span className="mono faint">{p.ref}</span> <b>{p.title}</b> <span className="muted2">{p.project} · {p.export}</span>
                  {p.url && <div><a href={p.url} target="_blank" rel="noreferrer">{p.url}</a></div>}</td>
                <td className="mono muted2">{p.at || "—"}</td>
                <td className="muted2">{p.profile} · {p.lang}</td>
                <td className="muted2">{p.credits.join("; ")}</td>
                <td className="nowrap" style={{ textAlign: "right" }}>
                  {p.status !== "posted" && p.status !== "cancelled" && <>
                    <button className="btn small primary" onClick={() => open(p.ref)} data-tip="The file, title and description, ready to upload yourself"
                            data-tip-cmd={`recomp post open ${p.ref}`}><Send size={12} />Open</button>
                    <LinkPost pref={p.ref} onDone={reload} />
                    <Act verb="post.cancel" args={{ ref: p.ref }} small ghost confirm="Take it out of the queue" onDone={reload}>Cancel</Act>
                  </>}
                  {p.status === "posted" && <span className="chip done">posted</span>}
                  {p.status === "cancelled" && <span className="muted2">cancelled</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {opened && <OpenedDialog p={opened} onClose={() => setOpened(null)} />}
    </>
  );
}

function ChannelRow({ ch, onChange }: { ch: any; onChange: () => void }) {
  const [name, setName] = useState("");
  const [handle, setHandle] = useState("");
  const named = ch && ch.ref && !ch.placeholder;
  return (
    <div className="cmdrow boxed">
      <div className="cmdgroup grow">
        <Tv size={14} className="faint" />
        {named ? <><b>{ch.name}</b>{ch.url && <a href={ch.url} target="_blank" rel="noreferrer" className="muted2">{ch.handle}</a>}
          {ch.totals && <span className="muted2">{Object.entries(ch.totals).map(([k, v]) => `${v} ${k}`).join(" · ")}</span>}</>
          : <>
            <span className="muted2">{ch?.ref ? "Posting to a placeholder channel." : "Your channel:"}</span>
            <input className="input" style={{ width: 200 }} placeholder="Channel name" value={name} onChange={(e) => setName(e.target.value)} />
            <input className="input" style={{ width: 160 }} placeholder="@handle" value={handle} onChange={(e) => setHandle(e.target.value)} />
            <Act verb="channel.set" args={{ name: name.trim(), handle: handle.trim() || undefined, platform: "youtube" }} small disabled={!name.trim()} onDone={onChange}>Save</Act>
          </>}
      </div>
    </div>
  );
}

function LinkPost({ pref, onDone }: { pref: string; onDone: () => void }) {
  const [url, setUrl] = useState("");
  const [open, setOpen] = useState(false);
  if (!open) return <button className="btn small" onClick={() => setOpen(true)} data-tip="Record where you posted it (on the journey and its hub recipe too)"><Link2 size={12} />Posted…</button>;
  return (
    <span className="row tight" style={{ display: "inline-flex" }}>
      <input className="input" style={{ width: 240 }} autoFocus placeholder="The post's URL" value={url} onChange={(e) => setUrl(e.target.value)} />
      <Act verb="post.link" args={{ ref: pref, url: url.trim() }} small primary disabled={!/^https?:\/\//.test(url.trim())} onDone={() => { setOpen(false); onDone(); }}>Save</Act>
    </span>
  );
}

function OpenedDialog({ p, onClose }: { p: any; onClose: () => void }) {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = (k: string, text: string) => { navigator.clipboard.writeText(text); setCopied(k); setTimeout(() => setCopied(null), 1500); };
  return (
    <Dialog title={`Post ${p.ref}: ${p.title}`} sub={`To ${p.channel || "your channel"}. You upload it; then record the link with "Posted…".`} wide onClose={onClose}
            footer={<>
              <Act verb="post.open" args={{ ref: p.ref, reveal: true }} quiet>Show the file</Act>
              <a className="btn primary" href={p.upload_page} target="_blank" rel="noreferrer"><ExternalLink size={14} />Open the upload page</a>
            </>}>
      <div className="stack">
        <div className="row"><b className="grow">Title</b><button className="btn small" onClick={() => copy("t", p.title)}><Copy size={12} />{copied === "t" ? "Copied" : "Copy"}</button></div>
        <div className="mono">{p.title}</div>
        <div className="row"><b className="grow">Description (with credits)</b><button className="btn small" onClick={() => copy("d", p.description)}><Copy size={12} />{copied === "d" ? "Copied" : "Copy"}</button></div>
        <pre className="desc">{p.description}</pre>
        <div className="muted2">File: <code>{p.file}</code></div>
      </div>
    </Dialog>
  );
}
