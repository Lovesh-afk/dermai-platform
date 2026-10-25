"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { useAuthedData } from "@/lib/useAuthedData";
import { patientApi, appointmentApi, ApiError, formatINR } from "@/lib/api";
import { VitalCard, StatusPill, Spinner, EmptyState, Button, Alert, Card } from "@/components/ui";
import { PaymentCheckout } from "@/components/PaymentCheckout";

export default function PatientAppointmentsPage() {
  const { accessToken } = useAuth();
  const { data: appointments, loading, refetch } = useAuthedData((t) => patientApi.myAppointments(t));
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [payingId, setPayingId] = useState<string | null>(null); // payment being completed

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
                  {a.status === "awaiting_payment" && a.hold_expires_at && (
                    <p className="mt-0.5 text-sm text-ochre-700">
                      Pay {a.payment ? formatINR(a.payment.amount_paise) : ""} by{" "}
                      {new Date(a.hold_expires_at).toLocaleTimeString(undefined, { timeStyle: "short" })} to keep this slot.
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <StatusPill status={a.status} />
                  {a.status === "awaiting_payment" && a.payment && (
                    <Button size="sm" onClick={() => setPayingId(a.payment!.id)}>Complete payment</Button>
                  )}
                  {(a.status === "awaiting_payment" || a.status === "pending" || a.status === "confirmed") && (
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

      {payingId && (
        <div className="fixed inset-0 z-10 flex items-center justify-center bg-ink/30 px-6" onClick={() => setPayingId(null)}>
          <Card className="w-full max-w-md">
            <div onClick={(e) => e.stopPropagation()} className="flex flex-col gap-4">
              <p className="font-display text-xl text-ink">Complete payment</p>
              <PaymentCheckout paymentId={payingId} onPaid={() => { setPayingId(null); refetch(); }} />
              <Button variant="secondary" onClick={() => setPayingId(null)}>Close</Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
