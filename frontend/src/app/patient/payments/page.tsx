"use client";

import { useAuthedData } from "@/lib/useAuthedData";
import { paymentApi, formatINR, PaymentStatus } from "@/lib/api";
import { Card, EmptyState, Spinner } from "@/components/ui";

const STATUS_LABELS: Record<PaymentStatus, { label: string; className: string }> = {
  created: { label: "Awaiting payment", className: "bg-ochre-50 text-ochre-700" },
  paid: { label: "Paid", className: "bg-pine-50 text-pine-700" },
  failed: { label: "Failed", className: "bg-alert-soft text-alert" },
  expired: { label: "Not paid", className: "bg-sage-100 text-ink-soft" },
  refunded: { label: "Refunded", className: "bg-pine-100 text-pine-800" },
  refund_failed: { label: "Refund pending", className: "bg-alert-soft text-alert" },
};

/** Receipts: every consultation fee, with refund status and the reason. */
export default function PatientPaymentsPage() {
  const { data: payments, loading } = useAuthedData((t) => paymentApi.mine(t));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl text-ink">Payments</h1>
        <p className="mt-1 text-ink-soft">Consultation fees and refunds.</p>
      </div>

      {loading ? (
        <Spinner className="h-5 w-5 text-pine-600" />
      ) : !payments || payments.length === 0 ? (
        <EmptyState title="No payments yet" body="Fees for paid consultations will appear here." />
      ) : (
        <div className="flex flex-col gap-3">
          {payments.map((p) => {
            const status = STATUS_LABELS[p.status];
            return (
              <Card key={p.id}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-medium text-ink">
                      {p.doctor_name ? `Dr. ${p.doctor_name}` : "Consultation"}
                      {p.appointment_time && (
                        <span className="font-normal text-ink-soft">
                          {" "}· {new Date(p.appointment_time).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                        </span>
                      )}
                    </p>
                    {p.note && <p className="mt-1 text-sm text-ink-soft">{p.note}</p>}
                    {p.provider === "simulated" && <p className="mt-1 text-xs text-ochre-700">Simulated payment (no real money)</p>}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <p className="font-display text-lg text-ink">{formatINR(p.amount_paise)}</p>
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${status.className}`}>{status.label}</span>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
