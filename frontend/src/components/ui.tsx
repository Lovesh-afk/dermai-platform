"use client";

import { ButtonHTMLAttributes, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes, ReactNode } from "react";

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
}

export function Button({ variant = "primary", size = "md", className = "", children, ...props }: ButtonProps) {
  const base = "inline-flex items-center justify-center gap-2 rounded-full font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const sizes = { sm: "px-3.5 py-1.5 text-sm", md: "px-5 py-2.5 text-sm" };
  const variants = {
    primary: "bg-pine-600 text-porcelain hover:bg-pine-700",
    secondary: "bg-sage-100 text-ink hover:bg-sage-200",
    ghost: "text-pine-600 hover:bg-pine-50",
    danger: "bg-alert text-porcelain hover:bg-alert/90",
  };
  return (
    <button className={`${base} ${sizes[size]} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Form fields
// ---------------------------------------------------------------------------

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-soft">{hint}</span>}
    </label>
  );
}

const fieldClass =
  "w-full rounded-lg border border-sage-200 bg-white px-3.5 py-2.5 text-sm text-ink placeholder:text-ink-soft/60 outline-none transition-shadow focus:border-pine-400 focus:ring-2 focus:ring-pine-100";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={fieldClass} {...props} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`${fieldClass} min-h-[90px] resize-y`} {...props} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={fieldClass} {...props} />;
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-card border border-sage-100 bg-white p-6 shadow-sm ${className}`}>{children}</div>;
}

// ---------------------------------------------------------------------------
// Status pill — the signature element: a left-edge color bar +
// pill badge encoding appointment/image status at a glance.
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<string, { bar: string; badge: string; label: string }> = {
  awaiting_payment: { bar: "bg-ochre-300", badge: "bg-ochre-50 text-ochre-700", label: "Awaiting payment" },
  pending: { bar: "bg-ochre-400", badge: "bg-ochre-50 text-ochre-700", label: "Pending" },
  confirmed: { bar: "bg-pine-500", badge: "bg-pine-50 text-pine-700", label: "Confirmed" },
  completed: { bar: "bg-pine-700", badge: "bg-pine-100 text-pine-800", label: "Completed" },
  cancelled: { bar: "bg-alert", badge: "bg-alert-soft text-alert", label: "Cancelled" },
  no_show: { bar: "bg-alert", badge: "bg-alert-soft text-alert", label: "No-show" },
  uploaded: { bar: "bg-ochre-400", badge: "bg-ochre-50 text-ochre-700", label: "Uploaded" },
  queued_for_analysis: { bar: "bg-pine-400", badge: "bg-pine-50 text-pine-700", label: "Analyzing…" },
  analyzed: { bar: "bg-pine-700", badge: "bg-pine-100 text-pine-800", label: "Analyzed" },
  failed: { bar: "bg-alert", badge: "bg-alert-soft text-alert", label: "Analysis failed" },
};

export function StatusPill({ status }: { status: string }) {
  const s = STATUS_STYLES[status] ?? { bar: "bg-sage-300", badge: "bg-sage-100 text-ink-soft", label: status };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${s.badge}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.bar}`} />
      {s.label}
    </span>
  );
}

export function VitalCard({ status, children }: { status: string; children: ReactNode }) {
  const s = STATUS_STYLES[status] ?? { bar: "bg-sage-300", badge: "", label: status };
  return (
    <div className="flex overflow-hidden rounded-card border border-sage-100 bg-white shadow-sm">
      <div className={`w-1.5 shrink-0 ${s.bar}`} />
      <div className="flex-1 p-5">{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Misc
// ---------------------------------------------------------------------------

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="rounded-card border border-dashed border-sage-200 bg-sage-50/40 px-6 py-12 text-center">
      <p className="font-display text-lg text-ink">{title}</p>
      <p className="mx-auto mt-1.5 max-w-sm text-sm text-ink-soft">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Alert({ variant = "error", children }: { variant?: "error" | "success"; children: ReactNode }) {
  const styles = variant === "error" ? "bg-alert-soft text-alert" : "bg-pine-50 text-pine-700";
  return <div className={`rounded-lg px-4 py-3 text-sm ${styles}`}>{children}</div>;
}
