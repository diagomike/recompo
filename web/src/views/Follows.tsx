// Follows (P17): the creators and shows we love, their new posts (the inbox), finding more, and their back catalogue.
// Studio-level: works without a project; inside a project, "Take" brings an item into that project.
import { useState } from "react";
import { BookOpen, ExternalLink, Inbox, RefreshCw, Search as SearchIcon, UserPlus, Users } from "lucide-react";
import { must } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { FilterBar, useFilters } from "../filters";
import { Empty } from "../ui";

const ROUTE_TIP: Record<string, string> = {
  lex: "Transcript page on lexfridman.com: speakers, chapters, the video's clock",
  published: "The podcast publishes its transcript (podcast timing)",
  captions: "YouTube captions (one request per video; refused while YouTube blocks this machine)",
  asr: "Audio only: transcribed locally (slow)",
  none: "No way to the words yet",
};

export const RouteChip = ({ route }: { route?: string | null }) =>
  route ? <span className={"chip" + (route === "lex" || route === "published" ? " done" : route === "asr" ? " running" : "")} data-tip={ROUTE_TIP[route]}>{route}</span> : null;

export default function Follows() {
  const { route } = useApp();
  const [f, setF] = useFilters();
  const tab = f.tab || "inbox";
  // Studio changes don't stream like a project's: every action here bumps `rev`, and each tab reloads on it.
  const [rev, setRev] = useState(0);
  const { data: follows, reload: reloadFollows } = useData(() => must<any[]>("follow.list"), [rev]);
  const reload = () => { reloadFollows(); setRev((r) => r + 1); };
  const fresh = (follows || []).reduce((n, x) => n + (x.inbox_new || 0), 0);
  return (
    <div className="page">
      <div className="pagehead">
        <div className="titles">
          <h1 className="h1">Follows</h1>
          <p className="sub">The creators and shows we follow: their new posts land in the inbox, their back catalogue in the library.
            {" "}Taking an item brings it into the project its follow feeds{route.project ? <> (or <b>{route.project}</b>)</> : ""}.</p>
        </div>
        <Act verb="follow.check" primary icon={<RefreshCw size={14} />} disabled={!follows?.length} onDone={reload}
             title="Look for new posts now (also every 2 hours while the studio runs)">Check now</Act>
      </div>
      <div className="segmented" style={{ marginBottom: 14 }} role="tablist">
        {[["inbox", `Inbox${fresh ? ` (${fresh})` : ""}`], ["following", `Following (${follows?.length ?? 0})`], ["find", "Find creators"], ["library", "Library"]].map(([k, l]) => (
          <button key={k} className={tab === k ? "on" : ""} onClick={() => setF("tab", k === "inbox" ? null : k)}>{l}</button>
        ))}
      </div>
      {tab === "inbox" && <InboxTab follows={follows || []} rev={rev} onChange={reload} />}
      {tab === "following" && <FollowingTab follows={follows} onChange={reload} />}
      {tab === "find" && <FindTab onFollowed={() => { reload(); setF("tab", "following"); }} />}
      {tab === "library" && <LibraryTab follows={follows || []} rev={rev} />}
    </div>
  );
}

function InboxTab({ follows, rev, onChange }: { follows: any[]; rev: number; onChange: () => void }) {
  const { route } = useApp();
  const [f] = useFilters();
  const status = f.status || "new";
  const { data: items } = useData(() => must<any[]>("inbox.list", { status, follow: f.follow || undefined, limit: 100 }), [status, f.follow, rev]);
  const done = onChange;
  const openTaken = (t: any) => (window.location.hash = `#/p/${encodeURIComponent(t.project)}/room/${t.source}`);
  return (
    <>
      <FilterBar count={items?.length} keep={["tab"]} fields={[
        { key: "status", label: "Status", type: "select", options: [["new", "new (default)"], "taken", "dismissed", "all"] },
        { key: "follow", label: "From", type: "select", options: follows.map((x) => [x.ref, x.name] as [string, string]) },
      ]} />
      {items && !items.length && (
        <Empty icon={<Inbox size={14} />} title={status === "new" ? "Nothing new" : "Nothing here"}>
          {follows.length ? "New posts from the creators you follow land here on every check." : "Follow someone first: Find creators."}
        </Empty>
      )}
      {!!items?.length && (
        <table className="table">
          <thead><tr><th>Post</th><th>From</th><th>Date</th><th>Length</th><th>Words</th><th></th></tr></thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.ref}>
                <td><span className="mono faint">{i.ref}</span> <a href={i.url} target="_blank" rel="noreferrer">{i.title}</a>
                  {i.kind !== "video" && <span className="chip" style={{ marginLeft: 6 }}>{i.kind}</span>}</td>
                <td className="muted2">{i.follow || i.channel}</td>
                <td className="mono muted2">{i.published || "—"}</td>
                <td className="mono muted2">{i.duration || "—"}</td>
                <td><RouteChip route={i.route} /></td>
                <td className="nowrap" style={{ textAlign: "right" }}>
                  {i.status === "new" && <>
                    <Act verb="inbox.take" args={{ refs: [i.ref], project: i.project || route.project || undefined }} small primary agent
                         disabled={!route.project && !i.project} onDone={done}
                         title={i.project || route.project ? `Into ${i.project || route.project}: source, transcript, chapters, cut candidates` : "Open a project first"}>
                      {i.project && i.project !== route.project ? `Take into ${i.project}` : "Take"}</Act>
                    <Act verb="inbox.dismiss" args={{ refs: [i.ref] }} small ghost onDone={done} title="Not for us (undo in the toast)">Dismiss</Act>
                  </>}
                  {i.status === "taken" && i.taken?.source && <button className="btn small" onClick={() => openTaken(i.taken)}>{i.taken.project} · {i.taken.source}</button>}
                  {i.status === "dismissed" && <span className="muted2">dismissed</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

function FollowingTab({ follows, onChange }: { follows: any[] | null; onChange: () => void }) {
  if (follows && !follows.length) {
    return <Empty icon={<Users size={14} />} title="Nobody followed yet">Find the channels, shows and people you love in <b>Find creators</b>, or ask the agent:
      <code> recomp follow add @handle --project …</code></Empty>;
  }
  return (
    <table className="table">
      <thead><tr><th>Creator</th><th>Feeds</th><th>Words</th><th>Projects</th><th>New</th><th>Library</th><th>Checked</th><th></th></tr></thead>
      <tbody>
        {(follows || []).map((x) => (
          <tr key={x.ref}>
            <td><span className="mono faint">{x.ref}</span> <b>{x.name}</b>{x.person && x.person !== x.name && <span className="muted2"> · {x.person}</span>}
              {x.rights !== "private" && <span className="chip done" style={{ marginLeft: 6 }} data-tip="Sources it brings in can be posted (D-23)">{x.rights}</span>}
              {x.error && <div className="err" style={{ fontSize: 12 }}>{x.error}</div>}</td>
            <td className="muted2">
              {x.youtube && <a href={x.youtube} target="_blank" rel="noreferrer">YouTube</a>}{x.youtube && x.podcast && " · "}
              {x.podcast && <a href={x.podcast} target="_blank" rel="noreferrer">podcast feed</a>}
              {x.appearances && " · appearances"}{x.match && <span className="mono"> /{x.match}/</span>}
            </td>
            <td><RouteChip route={x.route} /></td>
            <td className="muted2">{(x.projects || []).join(", ") || "—"}</td>
            <td className="mono">{x.inbox_new || ""}</td>
            <td className="mono">{x.library || ""}</td>
            <td className="mono muted2">{x.checked || "never"}</td>
            <td className="nowrap" style={{ textAlign: "right" }}>
              <Act verb="follow.check" args={{ follow: [x.ref] }} small ghost icon={<RefreshCw size={12} />} onDone={onChange}>Check</Act>
              <Act verb="follow.backfill" args={{ ref: x.ref }} small ghost agent icon={<BookOpen size={12} />} onDone={onChange}
                   title="Their back catalogue's transcripts (text only) into the library; run again to continue">Backfill</Act>
              <Act verb="follow.remove" args={{ ref: x.ref }} small ghost confirm="Stop following (its inbox items go too; undo restores them)" onDone={onChange}>Unfollow</Act>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FindTab({ onFollowed }: { onFollowed: () => void }) {
  const { route } = useApp();
  const { run } = useActions();
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("all");
  const [res, setRes] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  const find = async () => {
    if (!q.trim()) return;
    setBusy(true);
    const env = await run("find.creators", { query: q.trim(), kind }, { quiet: true, label: "Find creators" });
    setBusy(false);
    if (env.ok) setRes(env.data.results);
  };
  return (
    <>
      <div className="cmdrow boxed">
        <div className="cmdgroup grow">
          <SearchIcon size={14} className="faint" />
          <input className="input grow" placeholder="A subject, a channel or show, or a person: philosophy podcast · Lex Fridman · Alex O'Connor"
                 value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && find()} data-filter />
        </div>
        <div className="cmdgroup">
          <select className="input" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="What to find">
            <option value="all">Channels, podcasts and appearances</option>
            <option value="channels">YouTube channels</option>
            <option value="podcasts">Podcasts</option>
            <option value="person">A person's appearances</option>
          </select>
          <button className="btn primary" onClick={find} disabled={busy || !q.trim()} data-tip-cmd={`recomp find creators "${q}"${kind !== "all" ? ` --kind ${kind}` : ""}`} data-tip="Runs this command">{busy ? "Finding…" : "Find"}</button>
        </div>
      </div>
      {res && !res.length && <Empty icon={<SearchIcon size={14} />} title="Nothing found">Try other words, or one kind at a time.</Empty>}
      {!!res?.length && (
        <table className="table">
          <thead><tr><th>#</th><th>Found</th><th>Size</th><th>Words</th><th></th></tr></thead>
          <tbody>
            {res.map((r) => (
              <tr key={r.n}>
                <td className="mono faint">{r.n}</td>
                <td><span className="chip">{r.kind}</span> <b>{r.name}</b>{r.author && <span className="muted2"> · {r.author}</span>}
                  {r.url && <a href={r.url} target="_blank" rel="noreferrer" className="faint" style={{ marginLeft: 6 }}><ExternalLink size={12} /></a>}
                  {r.description && <div className="muted2 ellipsis" style={{ maxWidth: 620 }}>{r.description}</div>}
                  {r.examples && <div className="muted2 ellipsis" style={{ maxWidth: 620 }}>{r.examples.join(" · ")}</div>}</td>
                <td className="mono muted2">{r.subscribers ? `${Math.round(r.subscribers / 1000)}k subs` : r.episodes ? `${r.episodes} episodes` : r.videos ? `${r.videos} videos` : ""}</td>
                <td><RouteChip route={r.route} /></td>
                <td style={{ textAlign: "right" }}>
                  <Act verb="follow.add" args={{ target: String(r.n), project: route.project ? [route.project] : [] }} small primary icon={<UserPlus size={12} />}
                       onDone={onFollowed} title={route.project ? `Follow, feeding ${route.project}` : "Follow (no project yet: items wait in the inbox)"}>Follow</Act>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

function LibraryTab({ follows, rev }: { follows: any[]; rev: number }) {
  const { run } = useActions();
  const [f, setF] = useFilters();
  const [q, setQ] = useState(f.lq || "");
  const [hits, setHits] = useState<any | null>(null);
  const { data: docs } = useData(() => must<any[]>("library.list", { limit: 200 }), [rev]);
  const search = async (text = q) => {
    if (!text.trim()) return;
    setF("lq", text.trim());
    const env = await run("library.search", { query: text.trim(), limit: 40 }, { quiet: true, label: "Search the library" });
    if (env.ok) setHits(env.data);
  };
  return (
    <>
      <div className="cmdrow boxed">
        <div className="cmdgroup grow">
          <SearchIcon size={14} className="faint" />
          <input className="input grow" placeholder={`What did they say about… (${docs?.length ?? 0} transcripts from ${follows.length} creators)`}
                 value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} data-filter />
          <button className="btn" onClick={() => search()} disabled={!q.trim()} data-tip="Runs this command" data-tip-cmd={`recomp library search "${q}"`}>Search</button>
        </div>
      </div>
      {hits && (
        <div className="stack" style={{ marginBottom: 16 }}>
          <div className="muted2">{hits.hits.length} hit(s) {Object.entries(hits.by_creator).map(([k, v]) => `· ${k} ${v}`).join(" ")}</div>
          {hits.hits.map((h: any, k: number) => (
            <div key={k} className="hit">
              <div className="row tight">
                <b>{h.creator}</b><span className="muted2 ellipsis grow">{h.title} {h.published && `(${h.published})`}</span>
                <a className="btn small" href={h.link} target="_blank" rel="noreferrer" data-tip={h.timing === "video" ? "Watch at this moment" : "The episode (podcast timing)"}>
                  {h.at.replace(/\.\d$/, "")}{h.speaker ? ` · ${h.speaker}` : ""}</a>
              </div>
              <div className="muted2">{h.context}</div>
            </div>
          ))}
        </div>
      )}
      <table className="table">
        <thead><tr><th>Transcript</th><th>Creator</th><th>Date</th><th>Words</th><th>Length</th></tr></thead>
        <tbody>
          {(docs || []).map((d) => (
            <tr key={d.ref}>
              <td><span className="mono faint">{d.ref}</span> {d.title}</td>
              <td className="muted2">{d.creator}</td>
              <td className="mono muted2">{d.published || "—"}</td>
              <td><RouteChip route={d.route} /></td>
              <td className="mono muted2">{d.length}</td>
            </tr>
          ))}
          {docs && !docs.length && <tr><td colSpan={5} className="empty">The library is empty: Backfill a follow (Following tab) or scan a topic.</td></tr>}
        </tbody>
      </table>
    </>
  );
}
