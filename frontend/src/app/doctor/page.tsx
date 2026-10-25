"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAuthedData } from "@/lib/useAuthedData";
import { doctorApi, appointmentApi, AppointmentStatus, ApiError, Appointment, formatINR } from "@/lib/api";
import { VitalCard, StatusPill, Spinner, EmptyState, Button, Alert, Input } from "@/components/ui";

const NEXT_ACTIONS: Partial<Record<AppointmentStatus, { label: string; next: AppointmentStatus }[]>> = {
  pending: [{ label: "Confirm", next: "confirmed" }],
  confirmed: [{ label: "Mark completed", next: "completed" }, { label: "Mark no-show", next: "no_show" }],
};

export default function DoctorQueuePage() {
  const { user, accessToken } = useAuth();
  const { data: appointments, loading, refetch } = useAuthedData((t) => doctorApi.myQueue(t));
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null); // confirmation open for this appointment
  const [cancelReason, setCancelReason] = useState("");

  async function handleCancel(id: string) {
    if (!accessToken) return;
    setUpdatingId(id);
    setError(null);
    try {
      // The server refunds a paid booking in full when the doctor cancels
      await appointmentApi.cancel(accessToken, id, cancelReason.trim() || "Cancelled by the doctor");
      setCancellingId(null);
      setCancelReason("");
      refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't cancel that appointment.");
    } finally {
      setUpdatingId(null);
    }
  }

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
                  {isPaid(a) && <p className="mt-0.5 text-xs font-medium text-pine-700">Paid {formatINR(a.payment!.amount_paise)}</p>}
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
                  {cancellingId !== a.id && (
                    <Button size="sm" variant="ghost" disabled={updatingId === a.id} onClick={() => { setCancellingId(a.id); setCancelReason(""); }}>
                      Cancel
                    </Button>
                  )}
                </div>
              </div>

              {cancellingId === a.id && (
                <div className="mt-3 flex flex-col gap-2 border-t border-sage-100 pt-3">
                  <p className="text-sm text-ink">
                    Cancel this appointment? The patient will be notified
                    {isPaid(a) ? ` and refunded ${formatINR(a.payment!.amount_paise)} in full.` : "."}
                  </p>
                  <Input
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    placeholder="Reason for the patient (optional), e.g. unwell today"
                    maxLength={500}
                    aria-label="Cancellation reason"
                  />
                  <div className="flex gap-2">
                    <Button size="sm" variant="danger" disabled={updatingId === a.id} onClick={() => handleCancel(a.id)}>
                      {updatingId === a.id ? "Cancelling…" : "Yes, cancel appointment"}
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setCancellingId(null)}>Keep it</Button>
                  </div>
                </div>
              )}
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

function isPaid(a: Appointment): boolean {
  return a.payment?.status === "paid";
}
