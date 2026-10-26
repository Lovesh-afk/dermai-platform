"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAuthedData } from "@/lib/useAuthedData";
import { analyticsApi, formatINR, Analytics } from "@/lib/api";
import { Card, Spinner, EmptyState } from "@/components/ui";
import { BarChart } from "@/components/charts/BarChart";

const PERIODS = [7, 30, 90];
const CLASS_NAMES: Record<string, string> = { acne: "Acne", eczema: "Eczema", fungal: "Fungal infection", normal: "None of these" };

const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);
const dayLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });

export default function AnalyticsPage() {
  const { user } = useAuth();
  const isSuper = user?.role === "SUPER_ADMIN";
  const [days, setDays] = useState(30);
  const { data, loading } = useAuthedData(
    (t) => (isSuper ? analyticsApi.platform(t, days) : analyticsApi.hospital(t, days)),
    [days, isSuper]
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-ink">Analytics</h1>
          <p className="mt-1 text-ink-soft">
            {isSuper ? "Across every hospital on DermAI." : "Your hospital at a glance."} Totals only; no individual patient data.
          </p>
        </div>
        <div className="flex gap-1 rounded-full bg-sage-100 p-1" role="group" aria-label="Period">
          {PERIODS.map((d) => (
            <button
              key={d}
              type="button"
              aria-pressed={days === d}
              onClick={() => setDays(d)}
              className={`rounded-full px-3 py-1 text-sm ${days === d ? "bg-white text-ink shadow-sm" : "text-ink-soft"}`}
            >
              {d} days
            </button>
          ))}
        </div>
      </div>

      {loading && !data ? <Spinner className="h-5 w-5 text-pine-600" /> : data ? <Dashboard data={data} /> : (
        <EmptyState title="No data" body="Analytics couldn't be loaded." />
      )}
    </div>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="mt-1 font-display text-2xl text-ink">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-ink-soft">{hint}</p>}
    </Card>
  );
}

function Dashboard({ data }: { data: Analytics }) {
  const { totals: t, rates: r, revenue: rev } = data;
  const aiTotal = Object.values(data.ai.by_class).reduce((a, b) => a + b, 0);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi label="Appointments" value={String(t.appointments)} hint={`${t.upcoming_7d} upcoming in the next 7 days`} />
        <Kpi label="Completed" value={String(t.completed)} hint={`${t.active_patients} patients seen or booked`} />
        <Kpi label="No-show rate" value={pct(r.no_show_rate)} hint={`${t.no_show} missed appointment${t.no_show === 1 ? "" : "s"}`} />
        <Kpi label="Cancellation rate" value={pct(r.cancellation_rate)} hint={`${t.cancelled} cancelled`} />
        <Kpi label="Net revenue" value={formatINR(rev.net_paise)} hint={`${formatINR(rev.gross_paise)} collected, ${formatINR(rev.refunded_paise)} refunded`} />
        <Kpi label="Paid consultations" value={String(rev.paid_count)} hint={`${rev.refund_count} refunded`} />
        <Kpi label="Checkout completion" value={pct(r.checkout_conversion)} hint={`${t.abandoned_checkouts} abandoned checkout${t.abandoned_checkouts === 1 ? "" : "s"}`} />
        <Kpi label="AI photo analyses" value={String(data.ai.analyzed)} hint={`${data.ai.failed} failed of ${data.ai.photos_uploaded} uploaded`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <p className="mb-2 font-display text-lg text-ink">Appointments per day</p>
          <BarChart ariaLabel="Appointments per day" points={data.daily.map((d) => ({ label: dayLabel(d.date), value: d.appointments }))} />
        </Card>
        <Card>
          <p className="mb-2 font-display text-lg text-ink">Net revenue per day</p>
          <BarChart
            ariaLabel="Net revenue per day"
            format={formatINR}
            points={data.daily.map((d) => ({ label: dayLabel(d.date), value: d.revenue_paise }))}
          />
        </Card>
      </div>
      <p className="-mt-3 text-xs text-ink-soft">Days are counted in {data.timezone}. Revenue is counted on the day money was paid or refunded.</p>

      {data.scope === "platform" ? (
        <Card>
          <p className="mb-3 font-display text-lg text-ink">Hospitals</p>
          <Table
            headers={["Hospital", "Doctors", "Appointments", "Completed", "Net revenue"]}
            rows={data.hospitals.map((h) => [h.name, h.doctors, h.appointments, h.completed, formatINR(h.net_revenue_paise)])}
          />
        </Card>
      ) : (
        <Card>
          <p className="mb-3 font-display text-lg text-ink">Doctors</p>
          <Table
            headers={["Doctor", "Appointments", "Completed", "No-shows", "No-show rate", "Net revenue"]}
            rows={data.doctors.map((d) => [d.name ? `Dr. ${d.name}` : "—", d.appointments, d.completed, d.no_show, pct(d.no_show_rate), formatINR(d.net_revenue_paise)])}
          />
        </Card>
      )}

      <Card>
        <p className="font-display text-lg text-ink">AI photo analysis results</p>
        <p className="mb-3 text-xs text-ink-soft">What the screening model suggested. These are AI outputs, not diagnoses.</p>
        {aiTotal === 0 ? (
          <p className="text-sm text-ink-soft">No analysed photos in this period.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {Object.entries(data.ai.by_class).sort((a, b) => b[1] - a[1]).map(([cls, n]) => (
              <li key={cls} className="text-sm">
                <div className="flex justify-between text-ink-soft"><span>{CLASS_NAMES[cls] ?? cls}</span><span>{n}</span></div>
                <div className="mt-0.5 h-2 rounded-full bg-sage-100">
                  <div className="h-2 rounded-full bg-pine-600" style={{ width: `${(n / aiTotal) * 100}%` }} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  if (rows.length === 0) return <p className="text-sm text-ink-soft">Nothing to show yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-sage-100 text-ink-soft">
            {headers.map((h, i) => <th key={h} className={`py-2 font-medium ${i ? "text-right" : ""}`}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r} className="border-b border-sage-100 last:border-0">
              {row.map((cell, i) => <td key={i} className={`py-2 text-ink ${i ? "text-right tabular-nums" : ""}`}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
