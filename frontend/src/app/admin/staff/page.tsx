"use client";

import { adminApi } from "@/lib/api";
import { useAuthedData } from "@/lib/useAuthedData";
import { Card, Spinner, EmptyState, StatusPill } from "@/components/ui";

export default function AdminStaffPage() {
  const { data: staff, loading } = useAuthedData((t) => adminApi.hospital.staff(t));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl text-ink">Staff</h1>
        <p className="mt-1 text-ink-soft">Everyone registered under your hospital.</p>
      </div>

      {loading ? (
        <Spinner className="h-5 w-5 text-pine-600" />
      ) : !staff || staff.length === 0 ? (
        <EmptyState title="No staff yet" body="Once people register under your hospital, they'll show up here." />
      ) : (
        <div className="flex flex-col gap-3">
          {staff.map((s) => (
            <Card key={s.id}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-ink">{s.full_name}</p>
                  <p className="text-sm text-ink-soft">{s.email}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="rounded-full bg-sage-100 px-2.5 py-1 text-xs font-medium text-ink-soft">{s.role}</span>
                  <StatusPill status={s.is_active ? "active" : "inactive"} />
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
