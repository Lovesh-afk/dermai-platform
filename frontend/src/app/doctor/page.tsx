"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAuthedData } from "@/lib/useAuthedData";
import { doctorApi, appointmentApi, AppointmentStatus, ApiError } from "@/lib/api";
import { VitalCard, StatusPill, Spinner, EmptyState, Button, Alert } from "@/components/ui";

const NEXT_ACTIONS: Partial<Record<AppointmentStatus, { label: string; next: AppointmentStatus }[]>> = {
  pending: [{ label: "Confirm", next: "confirmed" }],
  confirmed: [{ label: "Mark completed", next: "completed" }, { label: "Mark no-show", next: "no_show" }],
};

export default function DoctorQueuePage() {
  const { user, accessToken } = useAuth();
  const { data: appointments, loading, refetch } = useAuthedData((t) => doctorApi.myQueue(t));
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpdate(id: string, status: AppointmentStatus) {
    if (!accessToken) return;
    setUpdatingId(id);
    setError(null);
    try {
      await appointmentApi.updateStatus(accessToken, id, status);
      refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update that appointment.");
    } finally {
      setUpdatingId(null);
    }
  }

  const sorted = appointments?.slice().sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime());
  const active = sorted?.filter((a) => a.status === "pending" || a.status === "confirmed");
  const past = sorted?.filter((a) => a.status === "completed" || a.status === "cancelled" || a.status === "no_show");

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="font-display text-3xl text-ink">Your queue</h1>
        <p className="mt-1 text-ink-soft">Good to see you, Dr. {user?.full_name.split(" ").slice(-1)[0]}.</p>
      </div>

      {error && <Alert>{error}</Alert>}

      {loading ? (
        <Spinner className="h-5 w-5 text-pine-600" />
      ) : !active || active.length === 0 ? (
        <EmptyState title="Queue is clear" body="No pending or confirmed appointments right now." />
      ) : (
        <div className="flex flex-col gap-3">
          {active.map((a) => (
            <VitalCard key={a.id} status={a.status}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-ink">{new Date(a.scheduled_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</p>
                  {a.reason && <p className="mt-0.5 text-sm text-ink-soft">{a.reason}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <StatusPill status={a.status} />
                  {NEXT_ACTIONS[a.status]?.map((action) => (
                    <Button
                      key={action.next}
                      size="sm"
                      variant={action.next === "no_show" ? "danger" : "secondary"}
                      disabled={updatingId === a.id}
                      onClick={() => handleUpdate(a.id, action.next)}
                    >
                      {action.label}
                    </Button>
                  ))}
                </div>
              </div>
            </VitalCard>
          ))}
        </div>
      )}

      {past && past.length > 0 && (
        <section>
          <h2 className="mb-3 font-display text-xl text-ink">History</h2>
          <div className="flex flex-col gap-3">
            {past.map((a) => (
              <VitalCard key={a.id} status={a.status}>
                <div className="flex items-center justify-between">
                  <p className="text-sm text-ink-soft">{new Date(a.scheduled_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</p>
                  <StatusPill status={a.status} />
                </div>
              </VitalCard>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
