"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { notificationApi, AppNotification } from "@/lib/api";

/** How often to check for new notifications. A lightweight count-only
 * request; the full list is only fetched when the panel opens. */
const POLL_INTERVAL_MS = 30_000;

function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

export function NotificationBell() {
  const { accessToken } = useAuth();
  const router = useRouter();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[] | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const refreshCount = useCallback(() => {
    if (!accessToken) return;
    notificationApi.unreadCount(accessToken).then((r) => setUnread(r.unread)).catch(() => {}); // the bell is non-critical
  }, [accessToken]);

  useEffect(() => {
    refreshCount();
    const timer = setInterval(refreshCount, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [refreshCount]);

  // Close when clicking outside the panel
  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && accessToken) {
      setItems(await notificationApi.list(accessToken).catch(() => []));
    }
  }

  async function openNotification(n: AppNotification) {
    if (!accessToken) return;
    if (!n.read_at) {
      await notificationApi.markRead(accessToken, n.id).catch(() => {});
      refreshCount();
    }
    setOpen(false);
    if (n.link) router.push(n.link);
  }

  async function markAllRead() {
    if (!accessToken) return;
    await notificationApi.markAllRead(accessToken).catch(() => {});
    setItems((prev) => prev?.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })) ?? null);
    setUnread(0);
  }

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={toggle}
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        className="relative rounded-full p-2 text-ink-soft hover:bg-sage-100 hover:text-ink"
      >
        <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5" aria-hidden>
          <path d="M10 3a4.5 4.5 0 0 0-4.5 4.5c0 2.5-.8 4.3-1.6 5.4-.3.4 0 1.1.5 1.1h11.2c.5 0 .8-.7.5-1.1-.8-1.1-1.6-2.9-1.6-5.4A4.5 4.5 0 0 0 10 3Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          <path d="M8.3 16.5a1.8 1.8 0 0 0 3.4 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-alert px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute left-full top-0 z-20 ml-3 w-80 rounded-card border border-sage-100 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-sage-100 px-4 py-3">
            <p className="font-display text-base text-ink">Notifications</p>
            {unread > 0 && (
              <button type="button" onClick={markAllRead} className="text-xs font-medium text-pine-600 hover:underline">
                Mark all read
              </button>
            )}
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {items === null ? (
              <li className="px-4 py-6 text-center text-sm text-ink-soft">Loading…</li>
            ) : items.length === 0 ? (
              <li className="px-4 py-6 text-center text-sm text-ink-soft">You&rsquo;re all caught up.</li>
            ) : (
              items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => openNotification(n)}
                    className={`flex w-full gap-3 px-4 py-3 text-left hover:bg-sage-50 ${n.read_at ? "" : "bg-pine-50/60"}`}
                  >
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.read_at ? "bg-transparent" : "bg-pine-600"}`} aria-hidden />
                    <span>
                      <span className="block text-sm font-medium text-ink">{n.title}</span>
                      <span className="block text-sm text-ink-soft">{n.body}</span>
                      <span className="mt-0.5 block text-xs text-ink-soft">{timeAgo(n.created_at)}</span>
                    </span>
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
