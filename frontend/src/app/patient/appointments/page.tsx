"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { useAuthedData } from "@/lib/useAuthedData";
import { patientApi, appointmentApi, ApiError } from "@/lib/api";
import { VitalCard, StatusPill, Spinner, EmptyState, Button, Alert } from "@/components/ui";

export default function PatientAppointmentsPage() {
  const { accessToken } = useAuth();
  const { data: appointments, loading, refetch } = useAuthedData((t) => patientApi.myAppointments(t));
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleCancel(id: string) {
    if (!accessToken) return;
    setCancellingId(id);
    setError(null);
    try {
      await appointmentApi.cancel(accessToken, id, "Cancelled by patient");
      refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't cancel that appointment.");
    } finally {
      setCancellingId(null);
    }
  }

  const sorted = appointments?.slice().sort((a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime());

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl text-ink">Appointments</h1>
        <p className="mt-1 text-ink-soft">Everything you&rsquo;ve booked, past and upcoming.</p>
      </div>

      {error && <Alert>{error}</Alert>}

      {loading ? (
        <Spinner className="h-5 w-5 text-pine-600" />
      ) : !sorted || sorted.length === 0 ? (
        <EmptyState
          title="No appointments yet"
          body="Book time with a dermatologist to get started."
          action={<Link href="/patient/doctors"><Button size="sm">Find a doctor</Button></Link>}
        />
      ) : (
        <div className="flex flex-col gap-3">
          {sorted.map((a) => (
            <VitalCard key={a.id} status={a.status}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-ink">{new Date(a.scheduled_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</p>
                  {a.reason && <p className="mt-0.5 text-sm text-ink-soft">{a.reason}</p>}
                  {a.cancellation_reason && <p className="mt-0.5 text-sm text-alert">Cancelled: {a.cancellation_reason}</p>}
                </div>
                <div className="flex items-center gap-3">
                  <StatusPill status={a.status} />
                  {(a.status === "pending" || a.status === "confirmed") && (
                    <Button variant="ghost" size="sm" disabled={cancellingId === a.id} onClick={() => handleCancel(a.id)}>
                      {cancellingId === a.id ? "Cancelling…" : "Cancel"}
                    </Button>
                  )}
                </div>
              </div>
            </VitalCard>
          ))}
        </div>
      )}
    </div>
  );
}
