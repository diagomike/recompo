// Shared building blocks for progressive disclosure: tooltips that explain (and show the command), popover menus for
// secondary actions, dialogs for focused tasks, "advanced" sections that remember being opened, and empty states
// that say exactly what to do next.
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, ChevronRight, MoreHorizontal, X } from "lucide-react";

// ── Tooltips: any element with data-tip (and optionally data-tip-cmd, data-tip-key) gets one. ──
export function TooltipLayer() {
  const [tip, setTip] = useState<{ text: string; cmd?: string; key?: string; x: number; y: number; below: boolean } | null>(null);
  const timer = useRef<number>();
  useEffect(() => {
    let current: HTMLElement | null = null;
    const show = (el: HTMLElement) => {
      const r = el.getBoundingClientRect();
      const below = r.top < 90;
      setTip({ text: el.dataset.tip || "", cmd: el.dataset.tipCmd, key: el.dataset.tipKey, x: r.left + r.width / 2, y: below ? r.bottom + 8 : r.top - 8, below });
    };
    const over = (e: Event) => {
      const el = (e.target as HTMLElement)?.closest?.("[data-tip]") as HTMLElement | null;
      if (el === current) return;
      current = el;
      window.clearTimeout(timer.current);
      if (!el || !el.dataset.tip) { setTip(null); return; }
      timer.current = window.setTimeout(() => show(el), e.type === "focusin" ? 0 : 380);
    };
    const hide = () => { current = null; window.clearTimeout(timer.current); setTip(null); };
    document.addEventListener("mouseover", over);
    document.addEventListener("focusin", over);
    document.addEventListener("mousedown", hide);
    document.addEventListener("scroll", hide, true);
    window.addEventListener("blur", hide);
    return () => {
      document.removeEventListener("mouseover", over);
      document.removeEventListener("focusin", over);
      document.removeEventListener("mousedown", hide);
      document.removeEventListener("scroll", hide, true);
      window.removeEventListener("blur", hide);
    };
  }, []);
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  useLayoutEffect(() => {
    if (!tip || !ref.current) { setPos(null); return; }
    const w = ref.current.offsetWidth, h = ref.current.offsetHeight;
    setPos({ left: Math.max(8, Math.min(window.innerWidth - w - 8, tip.x - w / 2)), top: tip.below ? tip.y : tip.y - h });
  }, [tip]);
  if (!tip) return null;
  return createPortal(
    <div ref={ref} className="tip" role="tooltip" style={pos ? pos : { left: -9999, top: -9999 }}>
      {tip.text}{tip.key && <span className="tk">{tip.key}</span>}
      {tip.cmd && <code>{tip.cmd}</code>}
    </div>, document.body);
}

// ── Popover menu ──
export type MenuItem =
  | { label: ReactNode; desc?: ReactNode; icon?: ReactNode; onSelect: () => void; danger?: boolean; disabled?: boolean; tip?: string }
  | { header: string } | "sep";

export function Menu({ items, label = "More actions", trigger, small, align = "end" }: {
  items: MenuItem[]; label?: string; trigger?: ReactNode; small?: boolean; align?: "start" | "end";
}) {
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number }>({ left: 0, top: 0 });
  useLayoutEffect(() => {
    if (!open || !btn.current || !box.current) return;
    const r = btn.current.getBoundingClientRect();
    const w = box.current.offsetWidth, h = box.current.offsetHeight;
    const left = align === "end" ? r.right - w : r.left;
    const top = r.bottom + 6 + h > window.innerHeight - 8 ? Math.max(8, r.top - 6 - h) : r.bottom + 6;
    setPos({ left: Math.max(8, Math.min(window.innerWidth - w - 8, left)), top });
    (box.current.querySelector(".mi:not(:disabled)") as HTMLElement | null)?.focus();
  }, [open, align]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node) && !btn.current?.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setOpen(false); btn.current?.focus(); }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const els = Array.from(box.current?.querySelectorAll(".mi:not(:disabled)") || []) as HTMLElement[];
        const k = els.indexOf(document.activeElement as HTMLElement);
        els[(k + (e.key === "ArrowDown" ? 1 : -1) + els.length) % els.length]?.focus();
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", key); };
  }, [open]);
  return (
    <>
      <button ref={btn} className={trigger ? "btn" + (small ? " small" : "") : "btn ghost icon" + (small ? " small" : "")} aria-haspopup="menu" aria-expanded={open}
              data-tip={trigger ? undefined : label} aria-label={label} onClick={() => setOpen(!open)}>
        {trigger ?? <MoreHorizontal size={18} />}
      </button>
      {open && createPortal(
        <div ref={box} className="menu" role="menu" style={pos}>
          {items.map((it, k) => it === "sep" ? <hr key={k} /> : "header" in it ? <div key={k} className="mh">{it.header}</div> : (
            <button key={k} className={"mi" + (it.danger ? " danger" : "")} role="menuitem" disabled={it.disabled} data-tip={it.tip}
                    onClick={() => { setOpen(false); it.onSelect(); }}>
              {it.icon}<span className="grow">{it.label}{it.desc && <span className="md">{it.desc}</span>}</span>
            </button>
          ))}
        </div>, document.body)}
    </>
  );
}

// ── Dialog ──
export function Dialog({ title, sub, children, footer, onClose, wide, icon }: {
  title: ReactNode; sub?: ReactNode; children: ReactNode; footer?: ReactNode; onClose: () => void; wide?: boolean; icon?: ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", key);
    const first = box.current?.querySelector("input, textarea, select, button.primary") as HTMLElement | null;
    first?.focus();
    return () => document.removeEventListener("keydown", key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return createPortal(
    <div className="modal" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={box} className={"dialog" + (wide ? " wide" : "")} role="dialog" aria-modal="true">
        <div className="dhead">
          {icon}
          <div className="grow"><h2>{title}</h2>{sub && <p>{sub}</p>}</div>
          <button className="btn ghost icon" onClick={onClose} aria-label="Close" data-tip="Close (Esc)"><X size={18} /></button>
        </div>
        <div className="dbody">{children}</div>
        {footer && <div className="dfoot">{footer}</div>}
      </div>
    </div>, document.body);
}

// ── "Advanced" sections: closed by default, remembered per id ──
export function Disclosure({ id, label, children, defaultOpen = false, count }: {
  id: string; label: ReactNode; children: ReactNode; defaultOpen?: boolean; count?: number;
}) {
  const key = "recomp.open." + id;
  const [open, setOpen] = useState<boolean>(() => {
    try { const v = localStorage.getItem(key); return v == null ? defaultOpen : v === "1"; } catch { return defaultOpen; }
  });
  const toggle = () => { setOpen(!open); try { localStorage.setItem(key, open ? "0" : "1"); } catch { /* ignore */ } };
  return (
    <div className="disclosure">
      <button className="dtoggle" onClick={toggle} aria-expanded={open}>
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}{label}{count ? <span className="chip">{count}</span> : null}
      </button>
      {open && <div className="dcontent">{children}</div>}
    </div>
  );
}

export function Empty({ icon, title, children, actions }: { icon?: ReactNode; title: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="empty">
      {icon && <div className="eicon">{icon}</div>}
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {actions && <div className="row" style={{ justifyContent: "center", marginTop: 6 }}>{actions}</div>}
    </div>
  );
}

export function useWidth(): number {
  const [w, setW] = useState(window.innerWidth);
  useEffect(() => {
    const on = () => setW(window.innerWidth);
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return w;
}

// A stable colour per source, so cuts from different sources read apart at a glance.
const SRC_COLORS = ["#2a7f6f", "#3b63b8", "#9a5b12", "#7a4bb8", "#b0413e", "#2f7d99", "#6b7a1f", "#a3477f"];
export const srcColor = (ref: string) => SRC_COLORS[(parseInt(ref.replace(/\D/g, ""), 10) - 1 + SRC_COLORS.length * 10) % SRC_COLORS.length];
export const SrcBadge = ({ ref_ }: { ref_: string }) => <span className="srcbadge" style={{ background: srcColor(ref_) }}>{ref_}</span>;

export function mmss(s: number | null | undefined): string {
  if (s == null || isNaN(s)) return "";
  const t = Math.round(s);
  return t >= 3600 ? `${Math.floor(t / 3600)}:${String(Math.floor((t % 3600) / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`
    : `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}
