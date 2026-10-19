// Publishing a recipe on the hub (D-23): private by default. Making it public or unlisted with private sources first
// shows what changes for each of them and asks the user — only the user — "Do you have permission to share this?".
import { useState } from "react";
import { ShieldQuestion, Share2 } from "lucide-react";
import { verb } from "../api";
import { useActions, cliFor } from "../actions";
import { Dialog } from "../ui";

export default function PublishButton({ journey, label, primary, onDone }: { journey: string; label: string; primary?: boolean; onDone?: () => void }) {
  const { run, toast } = useActions();
  const [visibility, setVisibility] = useState("private");
  const [ask, setAsk] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const [tip, setTip] = useState("");

  const publish = async (vis: string, confirm = false) => {
    setBusy(true);
    const args = { journey, visibility: vis, ...(confirm ? { confirm: true } : {}) };
    // First try without an answer: a private-source question comes back as E_CONFIRM, not as a failure.
    const env = confirm ? await run("hub.publish", args, { label: `Publish ${journey} (${vis})` }) : await verb("hub.publish", args);
    setBusy(false);
    if (!confirm) {
      if (!env.ok && env.error?.code === "E_CONFIRM") { setAsk({ vis, ...env.error.data }); return; }
      toast(env.ok ? { ok: true, title: `Published ${journey} (${vis})`, cli: (env as any).cli, detail: env.data?.url }
                   : { ok: false, title: "Publish", cli: (env as any).cli, detail: `${env.error!.message}${env.error!.hint ? " — " + env.error!.hint : ""}` });
    }
    if (env.ok) { setAsk(null); onDone?.(); }
  };

  return (
    <span className="row tight">
      <select className="input" value={visibility} onChange={(e) => setVisibility(e.target.value)} aria-label="Who can see it"
              data-tip="Private: only you. Unlisted: anyone with the link. Public: listed on the hub.">
        <option value="private">Private</option><option value="unlisted">Unlisted</option><option value="public">Public</option>
      </select>
      <button className={"btn small" + (primary ? " primary" : "")} disabled={busy} onClick={() => publish(visibility)}
              onMouseEnter={() => !tip && cliFor("hub.publish", { journey, visibility }).then(setTip)}
              data-tip="Publish the recipe to the configured hub" data-tip-cmd={tip || `recomp hub publish ${journey}`}>
        <Share2 size={13} />{label}{busy ? "…" : ""}
      </button>
      {ask && (
        <Dialog title={ask.question} icon={<ShieldQuestion size={18} />} onClose={() => setAsk(null)}
                sub={`Making ${journey} ${ask.vis} shares recipes of sources whose rights are private.`}
                footer={<>
                  <button className="btn" onClick={() => setAsk(null)}>Cancel</button>
                  <button className="btn" onClick={() => publish("private")}>Publish it private instead</button>
                  <button className="btn primary" onClick={() => publish(ask.vis, true)}>Yes, I have permission: publish {ask.vis}</button>
                </>}>
          <p className="muted2" style={{ marginTop: 0 }}>What changes for each private source:</p>
          <ul className="plain stack">
            {(ask.consequences as string[]).map((c, k) => <li key={k}>{c}</li>)}
          </ul>
          <p className="muted2">Your answer and the time are saved with this version of the recipe. If you have the creator's permission or the
            source is in a clipping program, record it on the source (<code>recomp source rights S… --status permitted --evidence &lt;link&gt;</code>) and this
            question goes away.</p>
        </Dialog>
      )}
    </span>
  );
}
