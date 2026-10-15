// Hub client. When the page is served by the hub, its origin is the hub; inside the studio the hub URL
// comes from the studio's config. The session token is a per-browser convenience (localStorage).

declare global {
  interface Window { __HUB__?: string }
}

let hubBase: string | null = window.__HUB__ || null;

export async function hubUrl(): Promise<string> {
  if (hubBase) return hubBase;
  try {
    const r = await fetch("/api/verb/config.get", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ args: { key: "hub.url" } }) });
    const env = await r.json();
    hubBase = (env.ok && env.data) || "http://127.0.0.1:8790";
  } catch {
    hubBase = "http://127.0.0.1:8790";
  }
  return hubBase!;
}

export const inStudio = () => !window.__HUB__;

function tokenKey(base: string) { return `recomp.hub.token:${base}`; }
export function getToken(base: string): string | null { try { return localStorage.getItem(tokenKey(base)); } catch { return null; } }
export function setToken(base: string, t: string | null) {
  try { t ? localStorage.setItem(tokenKey(base), t) : localStorage.removeItem(tokenKey(base)); } catch { /* ignore */ }
}

export async function hub<T = any>(method: string, path: string, body?: any): Promise<T> {
  const base = await hubUrl();
  const tok = getToken(base);
  const r = await fetch(base + path, {
    method, headers: { "Content-Type": "application/json", ...(tok ? { Authorization: `Bearer ${tok}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `hub ${r.status}`);
  return data as T;
}
