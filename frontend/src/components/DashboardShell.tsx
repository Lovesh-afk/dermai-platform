"use client";

import Link from "next/link";
import { NotificationBell } from "@/components/NotificationBell";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { useAuth } from "@/lib/auth";

interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
}

const icons = {
  home: (
    <svg viewBox="0 0 20 20" fill="none" className="h-4.5 w-4.5">
      <path d="M3 9.5 10 3l7 6.5M5 8v8h10V8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  calendar: (
    <svg viewBox="0 0 20 20" fill="none" className="h-4.5 w-4.5">
      <rect x="3" y="4.5" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3 8.5h14M7 3v3M13 3v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  users: (
    <svg viewBox="0 0 20 20" fill="none" className="h-4.5 w-4.5">
      <circle cx="7" cy="7" r="2.6" stroke="currentColor" strokeWidth="1.6" />
      <path d="M2.5 16c.6-2.8 2.4-4.3 4.5-4.3s3.9 1.5 4.5 4.3M13 8.2A2.4 2.4 0 1 0 13 3.4M14.5 11.9c1.8.4 3 1.7 3.5 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  file: (
    <svg viewBox="0 0 20 20" fill="none" className="h-4.5 w-4.5">
      <path d="M6 2.5h6l3 3V16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M7.5 9h5M7.5 12h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  image: (
    <svg viewBox="0 0 20 20" fill="none" className="h-4.5 w-4.5">
      <rect x="2.5" y="4" width="15" height="12" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="7" cy="8.5" r="1.4" stroke="currentColor" strokeWidth="1.6" />
      <path d="M4 15l4-4 2.5 2.5L14 10l3 3" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  ),
  user: (
    <svg viewBox="0 0 20 20" fill="none" className="h-4.5 w-4.5">
      <circle cx="10" cy="7" r="3" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3.5 17c.9-3.6 3.3-5.5 6.5-5.5s5.6 1.9 6.5 5.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  chat: (
    <svg viewBox="0 0 20 20" fill="none" className="h-4.5 w-4.5">
      <path d="M4 4.5h12a1 1 0 0 1 1 1v7.5a1 1 0 0 1-1 1H8.5L5 17v-3H4a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M6.5 8.5h7M6.5 11h4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  building: (
    <svg viewBox="0 0 20 20" fill="none" className="h-4.5 w-4.5">
      <rect x="4" y="2.5" width="9" height="15" rx="1" stroke="currentColor" strokeWidth="1.6" />
      <path d="M13 8h2.5a1 1 0 0 1 1 1v7.5H13M6.5 5.5h1M9.5 5.5h1M6.5 8.5h1M9.5 8.5h1M6.5 11.5h1M9.5 11.5h1M7 17.5v-3h2v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
};

export function DashboardShell({ navItems, children }: { navItems: NavItem[]; children: ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen">
      <aside className="texture-dots flex w-64 shrink-0 flex-col border-r border-sage-100 bg-sage-50/60 px-5 py-6">
        <div className="mb-8 flex items-center justify-between px-1">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-pine-600 font-display text-sm text-porcelain">D</span>
            <span className="font-display text-lg tracking-tight text-ink">DermAI</span>
          </Link>
          <NotificationBell />
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  active ? "bg-pine-600 text-porcelain" : "text-ink-soft hover:bg-sage-100 hover:text-ink"
                }`}
              >
                {item.icon}
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-6 border-t border-sage-100 pt-4">
          <p className="truncate px-1 text-sm font-medium text-ink">{user?.full_name}</p>
          <p className="truncate px-1 text-xs text-ink-soft">{user?.email}</p>
          <button
            onClick={() => logout()}
            className="mt-3 w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-ink-soft transition-colors hover:bg-sage-100 hover:text-alert"
          >
            Log out
          </button>
        </div>
      </aside>

      <main className="flex-1 px-10 py-8">
        <div className="mx-auto max-w-4xl">{children}</div>
      </main>
    </div>
  );
}

export { icons };
