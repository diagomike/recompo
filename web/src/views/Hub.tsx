import { useEffect, useState } from "react";
import { ArrowBigDown, ArrowBigUp, GitFork, Link2, LogIn, LogOut, MessageSquare, UserPlus } from "lucide-react";
import { clock, verb } from "../api";
import { getToken, hub, hubUrl, inStudio, setToken } from "../hub";
import RecipePlayer from "./RecipePlayer";

function useHash() {
  const [h, setH] = useState(window.location.hash);
  useEffect(() => { const on = () => setH(window.location.hash); window.addEventListener("hashchange", on); return () => window.removeEventListener("hashchange", on); }, []);
  return h.replace(/^#\/hub\/?/, "").split("?")[0].split("/").filter(Boolean).map(decodeURIComponent);
}
const go = (path: string) => (window.location.hash = "#/hub" + (path ? "/" + path : ""));

export default function Hub() {
  const parts = useHash();
  const [me, setMe] = useState<any>(null);
  const [base, setBase] = useState("");
  const [n, setN] = useState(0);
  useEffect(() => { hubUrl().then(setBase); hub("GET", "/api/hub/me").then(setMe).catch(() => setMe(null)); }, [n]);
  const [view, a] = parts;
  return (
    <div className="page" style={{ maxWidth: 1200 }}>
      <div className="row" style={{ marginBottom: 10 }}>
        <h1 className="h1" style={{ margin: 0, cursor: "pointer" }} onClick={() => go("")}>Hub</h1>
        <span className="sub" style={{ margin: 0 }}>recipes, not media · {base}</span>
        <div className="spacer" />
        {me ? (
          <>
            <a href={`#/hub/u/${me.handle}`} className="chip">@{me.handle}</a>
            <button className="btn small" onClick={async () => { await hub("POST", "/api/hub/auth/logout").catch(() => {}); setToken(base, null); setN(n + 1); }}><LogOut size={13} />Sign out</button>
          </>
        ) : <button className="btn small" onClick={() => go("login")}><LogIn size={13} />Sign in</button>}
      </div>
      {!view && <Explore />}
      {view === "login" && <Login onDone={() => { setN(n + 1); go(""); }} />}
      {view === "r" && a && <RecipePage key={a} id={a} me={me} />}
      {view === "u" && a && <Profile key={a} handle={a} me={me} />}
      {view === "s" && a && <SourcePage key={a} sourceKey={parts.slice(1).join("/")} />}
      {view === "t" && a && <Explore tag={a} />}
    </div>
  );
}

function Card({ c }: { c: any }) {
  return (
    <div className="card" style={{ cursor: "pointer", display: "grid", gridTemplateColumns: "120px 1fr", gap: 10 }} onClick={() => go(`r/${c.id}`)}>
      {c.thumbnail ? <HubImg src={c.thumbnail} /> : <div style={{ background: "var(--panel-2)", borderRadius: 3, height: 68 }} />}
      <div style={{ minWidth: 0 }}>
        <b>{c.title}</b>
        <div style={{ fontSize: 12, color: "var(--muted)" }}>@{c.owner} · {c.slots} moments · {clock(c.duration, 0)} · ▲ {c.score} · {c.comments} comments</div>
        <div style={{ fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.intent}</div>
        <div className="row" style={{ gap: 3, marginTop: 3 }}>{c.tags.slice(0, 5).map((t: string) => <span key={t} className="chip">{t}</span>)}</div>
      </div>
    </div>
  );
}

function HubImg({ src }: { src: string }) {
  const [base, setBase] = useState("");
  useEffect(() => { hubUrl().then(setBase); }, []);
  return base ? <img src={base + src} alt="" style={{ width: 120, height: 68, objectFit: "cover", borderRadius: 3 }} /> : null;
}

function Explore({ tag }: { tag?: string }) {
  const [kind, setKind] = useState("trending");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<any[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tags, setTags] = useState<any[]>([]);
  useEffect(() => {
    const p = new URLSearchParams({ kind, limit: "40", ...(tag ? { tag } : {}), ...(q ? { q } : {}) });
    hub("GET", `/api/hub/feed?${p}`).then((d) => { setItems(d.items); setErr(null); }).catch((e) => setErr(e.message));
  }, [kind, tag, q]);
  useEffect(() => { hub("GET", "/api/hub/tags").then(setTags).catch(() => {}); }, []);
  return (
    <div className="jgrid" style={{ gridTemplateColumns: "minmax(0,1fr) 220px" }}>
      <div>
        <div className="row" style={{ marginBottom: 8 }}>
          {["trending", "new", "top", "following"].map((k) => <button key={k} className={"tab" + (kind === k ? " on" : "")} onClick={() => setKind(k)}>{k}</button>)}
          {tag && <span className="chip">#{tag}</span>}
          <div className="spacer" />
          <input className="input" placeholder="Search recipes" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {err && <div className="err">{err}</div>}
        <div style={{ display: "grid", gap: 6 }}>{(items || []).map((c) => <Card key={c.id} c={c} />)}</div>
        {items && !items.length && <div className="empty">Nothing here yet. Publish a journey: <code>recomp hub publish J1</code></div>}
      </div>
      <div>
        <div className="sub">Tags</div>
        <div className="row" style={{ gap: 4 }}>{tags.map((t) => <a key={t.tag} className="chip" href={`#/hub/t/${t.tag}`}>#{t.tag} {t.recipes}</a>)}</div>
      </div>
    </div>
  );
}

function RecipePage({ id, me }: { id: string; me: any }) {
  const [r, setR] = useState<any>(null);
  const [comments, setComments] = useState<any[]>([]);
  const [text, setText] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    hub("GET", `/api/hub/recipes/${id}`).then(setR).catch((e) => setMsg(e.message));
    hub("GET", `/api/hub/recipes/${id}/comments`).then(setComments).catch(() => {});
  }, [id, n]);
  if (msg && !r) return <div className="err">{msg}</div>;
  if (!r) return <div>Loading…</div>;
  const rec = r.recipe;
  const allLinks = Object.values(rec.sources).every((s: any) => s.kind === "link");
  const act = async (fn: () => Promise<any>) => { try { await fn(); setMsg(null); setN(n + 1); } catch (e: any) { setMsg(e.message); } };
  const pull = async () => {
    const env = await verb("hub.pull", { recipe: id });
    setMsg(env.ok ? `Pulled into the current project as ${env.data.journey}.` : env.error!.message);
  };
  const top = comments.filter((c) => !c.parent);
  return (
    <div>
      <div className="row" style={{ marginBottom: 6 }}>
        <h2 className="h1" style={{ margin: 0 }}>{r.title}</h2>
        <a className="chip" href={`#/hub/u/${r.owner}`}>@{r.owner}</a>
        <span className="chip">v{r.version}</span>
        {r.forked_from && <a className="chip" href={`#/hub/r/${r.forked_from}`}>forked</a>}
        <div className="spacer" />
        <button className={"btn small" + (r.my_vote === 1 ? " primary" : "")} disabled={!me} onClick={() => act(() => hub("POST", `/api/hub/recipes/${id}/vote`, { value: r.my_vote === 1 ? 0 : 1 }))}><ArrowBigUp size={14} /></button>
        <b>{r.score}</b>
        <button className={"btn small" + (r.my_vote === -1 ? " primary" : "")} disabled={!me} onClick={() => act(() => hub("POST", `/api/hub/recipes/${id}/vote`, { value: r.my_vote === -1 ? 0 : -1 }))}><ArrowBigDown size={14} /></button>
        <button className="btn small" disabled={!me} onClick={() => act(async () => { const f = await hub("POST", `/api/hub/recipes/${id}/fork`); go(`r/${f.id}`); })}><GitFork size={13} />Fork</button>
        {inStudio() && <button className="btn small primary" onClick={pull}>Pull into studio</button>}
      </div>
      <p className="sub">{r.intent}</p>
      {msg && <div className="warn">{msg}</div>}
      <div className="jgrid" style={{ gridTemplateColumns: "minmax(0, 1.2fr) minmax(0, 1fr)" }}>
        <div>
          {allLinks ? <RecipePlayer recipe={rec} /> : (
            <div className="card">
              This recipe cuts from works you play from your own copies:
              <ul>{Object.values(rec.sources).filter((s: any) => s.kind === "file").map((s: any, k) => <li key={k}>{s.title}{s.year ? ` (${s.year})` : ""}</li>)}</ul>
              {inStudio() ? "Pull it into a project; files are matched by fingerprint or title, or you relink them." : <>In the studio: <code>recomp hub pull {id}</code></>}
            </div>
          )}
          <div className="card" style={{ marginTop: 8 }}>
            <b>Moments</b>
            {rec.slots.map((s: any, k: number) => (
              <div key={k} style={{ fontSize: 12, borderTop: "1px solid var(--line)", padding: "4px 0" }}>
                {s.section && <div className="section">{s.section}</div>}
                <span className="mono">{k + 1}</span> <b>{s.title}</b> <span className="mono" style={{ color: "var(--muted)" }}>{rec.sources[s.source].title} {clock(s.in, 0)}–{clock(s.out, 0)}</span>
                <div style={{ color: "var(--muted)" }}>{s.why}</div>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="card">
            <b>Credits</b>
            {rec.credits.map((c: any, k: number) => <div key={k} style={{ fontSize: 12 }}>{c.text} {c.url && <a href={c.url} target="_blank">source</a>}</div>)}
            {!!r.links.length && <><b style={{ display: "block", marginTop: 6 }}><Link2 size={12} /> Posted at</b>{r.links.map((l: any, k: number) => <div key={k}><a href={l.url} target="_blank">{l.platform}</a> {l.lang}</div>)}</>}
            <div style={{ marginTop: 6 }}>{r.sources.map((s: any) => <a key={s.key} className="chip" href={`#/hub/s/${s.key}`} style={{ marginRight: 4 }}>{s.title}</a>)}</div>
          </div>
          <div className="card" style={{ marginTop: 8 }}>
            <b><MessageSquare size={13} /> Comments ({comments.length})</b>
            {top.map((c) => (
              <div key={c.id} style={{ borderTop: "1px solid var(--line)", padding: "6px 0" }}>
                <div><a href={`#/hub/u/${c.by}`}>@{c.by}</a> {c.body}</div>
                {comments.filter((x) => x.parent === c.id).map((x) => <div key={x.id} style={{ marginLeft: 16, fontSize: 12 }}><a href={`#/hub/u/${x.by}`}>@{x.by}</a> {x.body}</div>)}
                {me && <button className="btn ghost small" onClick={() => setReply(c.id)}>reply</button>}
              </div>
            ))}
            {me ? (
              <div className="row" style={{ marginTop: 6 }}>
                {reply && <span className="chip">replying <button className="btn ghost small" onClick={() => setReply(null)}>×</button></span>}
                <input className="input grow" value={text} placeholder="Say something about this journey" onChange={(e) => setText(e.target.value)}
                       onKeyDown={(e) => e.key === "Enter" && text.trim() && act(async () => { await hub("POST", `/api/hub/recipes/${id}/comments`, { body: text, parent: reply }); setText(""); setReply(null); })} />
              </div>
            ) : <div className="sub"><a href="#/hub/login">Sign in</a> to vote and comment.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Profile({ handle, me }: { handle: string; me: any }) {
  const [p, setP] = useState<any>(null);
  const [n, setN] = useState(0);
  useEffect(() => { hub("GET", `/api/hub/users/${handle}`).then(setP).catch(() => setP(null)); }, [handle, n]);
  if (!p) return <div>Loading…</div>;
  return (
    <div>
      <div className="row"><h2 className="h1" style={{ margin: 0 }}>@{p.handle}</h2><span className="sub" style={{ margin: 0 }}>{p.display} · {p.followers} followers · {p.following} following</span>
        <div className="spacer" />
        {me && me.handle !== p.handle && <button className="btn small" onClick={async () => { await hub(p.is_following ? "DELETE" : "POST", `/api/hub/users/${handle}/follow`); setN(n + 1); }}><UserPlus size={13} />{p.is_following ? "Following" : "Follow"}</button>}
      </div>
      <p className="sub">{p.bio}</p>
      <div style={{ display: "grid", gap: 6 }}>{p.recipes.map((c: any) => <Card key={c.id} c={c} />)}</div>
    </div>
  );
}

function SourcePage({ sourceKey }: { sourceKey: string }) {
  const [s, setS] = useState<any>(null);
  useEffect(() => { hub("GET", `/api/hub/sources/${sourceKey}`).then(setS).catch(() => setS(null)); }, [sourceKey]);
  if (!s) return <div>Loading…</div>;
  const max = Math.max(1, ...s.heat);
  return (
    <div>
      <h2 className="h1">{s.title}</h2>
      <p className="sub">{s.creator} {s.url && <a href={s.url} target="_blank">source</a>} · {s.recipes.length} recipes cut from it</p>
      <div className="card" style={{ marginBottom: 10 }}>
        <div className="sub" style={{ margin: 0 }}>Most-cut moments</div>
        <div style={{ display: "flex", alignItems: "flex-end", height: 60, gap: 1 }}>
          {s.heat.map((v: number, k: number) => <div key={k} title={`${clock((k / s.heat.length) * s.duration, 0)}: ${v}`} style={{ flex: 1, height: `${(v / max) * 100}%`, background: "var(--accent)", minHeight: 1, opacity: v ? 1 : 0.2 }} />)}
        </div>
        <div className="row" style={{ fontSize: 11, color: "var(--faint)" }}><span>0:00</span><div className="spacer" /><span>{clock(s.duration, 0)}</span></div>
      </div>
      <div style={{ display: "grid", gap: 6 }}>{s.recipes.map((c: any) => <Card key={c.id} c={c} />)}</div>
    </div>
  );
}

function Login({ onDone }: { onDone: () => void }) {
  const [handle, setHandle] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    try {
      const base = await hubUrl();
      const r = await hub("POST", `/api/hub/auth/${mode}`, { handle, password });
      setToken(base, r.token);
      onDone();
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <div className="card" style={{ maxWidth: 380 }}>
      <div className="row" style={{ marginBottom: 6 }}>
        <button className={"tab" + (mode === "login" ? " on" : "")} onClick={() => setMode("login")}>Sign in</button>
        <button className={"tab" + (mode === "register" ? " on" : "")} onClick={() => setMode("register")}>Create account</button>
      </div>
      <input className="input" style={{ width: "100%", marginBottom: 6 }} placeholder="handle" value={handle} onChange={(e) => setHandle(e.target.value)} />
      <input className="input" style={{ width: "100%", marginBottom: 6 }} type="password" placeholder="password (8+ characters)" value={password}
             onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
      <button className="btn primary" onClick={submit}>{mode === "login" ? "Sign in" : "Create account"}</button>
      {err && <div className="err">{err}</div>}
      {getToken("") && null}
    </div>
  );
}
