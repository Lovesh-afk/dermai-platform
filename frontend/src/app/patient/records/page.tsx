"use client";

import { patientApi } from "@/lib/api";
import { useAuthedData } from "@/lib/useAuthedData";
import { Card, Spinner, EmptyState } from "@/components/ui";

export default function PatientRecordsPage() {
  const { data: records, loading } = useAuthedData((t) => patientApi.myMedicalRecords(t));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl text-ink">Medical records</h1>
        <p className="mt-1 text-ink-soft">Diagnoses and notes from your visits.</p>
      </div>

      {loading ? (
        <Spinner className="h-5 w-5 text-pine-600" />
      ) : !records || records.length === 0 ? (
        <EmptyState title="No records yet" body="Records appear here after a doctor writes one up following your visit." />
      ) : (
        <div className="flex flex-col gap-3">
          {records.map((r) => (
            <Card key={r.id}>
              {r.diagnosis && <p className="font-medium text-ink">{r.diagnosis}</p>}
              {r.notes && <p className="mt-1 text-sm text-ink-soft">{r.notes}</p>}
              {!r.diagnosis && !r.notes && <p className="text-sm text-ink-soft">No details recorded.</p>}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
