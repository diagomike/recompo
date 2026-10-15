// The viewer talks to the same verbs the agent uses: POST /api/verb/<name>. It acts as the user.

export type Envelope<T = any> = {
  ok: boolean;
  verb: string;
  data?: T;
  error?: { code: string; message: string; hint?: string; data?: any };
  refs?: string[];
  op?: string;
  job?: string;
  warnings?: string[];
  next?: string[];
};

let currentProject: string | null = null;
export const setProject = (p: string | null) => (currentProject = p);
export const getProject = () => currentProject;

export async function verb<T = any>(name: string, args: Record<string, any> = {}): Promise<Envelope<T>> {
  const res = await fetch(`/api/verb/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ args, project: currentProject }),
  });
  return res.json();
}

export async function must<T = any>(name: string, args: Record<string, any> = {}): Promise<T> {
  const env = await verb<T>(name, args);
  if (!env.ok) throw new VerbError(env);
  return env.data as T;
}

export class VerbError extends Error {
  env: Envelope;
  constructor(env: Envelope) {
    super(env.error ? `${env.error.message}${env.error.hint ? " — " + env.error.hint : ""}` : "failed");
    this.env = env;
  }
}

const q = () => (currentProject ? `project=${encodeURIComponent(currentProject)}` : "");

export async function room(ref: string) {
  const res = await fetch(`/api/room/${ref}?${q()}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const mediaUrl = (ref: string) => `/media/source/${ref}?${q()}`;
export const peaksUrl = (ref: string) => `/media/peaks/${ref}?${q()}`;
export const thumbUrl = (ref: string, name: string) => `/media/thumbs/${ref}/${name}?${q()}`;
export const fileUrl = (path: string) => `/media/file?path=${encodeURIComponent(path)}&${q()}`;

export type Ev = { kind: string; seq: number; data: any };

export function subscribe(onEvent: (e: Ev) => void): () => void {
  let es: EventSource | null = null;
  let closed = false;
  let last: number | null = null;
  const open = () => {
    if (closed) return;
    es = new EventSource(`/api/events?${q()}${last != null ? `&after=${last}` : ""}`);
    for (const kind of ["op", "job", "ui", "undo", "redo", "source", "hello", "export"]) {
      es.addEventListener(kind, (m: MessageEvent) => {
        const data = JSON.parse(m.data || "{}");
        if (kind === "hello") last = data.seq;
        else if (m.lastEventId) last = Number(m.lastEventId);
        onEvent({ kind, seq: last ?? 0, data });
      });
    }
    es.onerror = () => {
      es?.close();
      setTimeout(open, 1500);
    };
  };
  open();
  return () => {
    closed = true;
    es?.close();
  };
}

export function clock(s: number | null | undefined, decimals = 1): string {
  if (s == null || isNaN(s)) return "";
  const neg = s < 0;
  const f = Math.pow(10, decimals);
  s = Math.round(Math.abs(s) * f) / f;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const ss = sec.toFixed(decimals).padStart(decimals ? 3 + decimals : 2, "0");
  return `${neg ? "-" : ""}${h ? h + ":" : ""}${String(m).padStart(h ? 2 : 1, "0")}:${ss}`;
}
