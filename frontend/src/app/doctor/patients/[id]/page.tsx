"use client";

import { useState, useEffect, FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { doctorApi, medicalRecordApi, PatientProfile, MedicalRecord, ApiError } from "@/lib/api";
import { Card, Field, Input, Textarea, Button, Alert, Spinner } from "@/components/ui";

export default function DoctorPatientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { accessToken } = useAuth();

  const [patient, setPatient] = useState<PatientProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const [diagnosis, setDiagnosis] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [records, setRecords] = useState<MedicalRecord[]>([]);

  useEffect(() => {
    if (!accessToken || !id) return;
    doctorApi
      .myPatient(accessToken, id)
      .then(setPatient)
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));

    doctorApi.myCreatedRecords(accessToken).then((all) => setRecords(all.filter((r) => r.patient_id === id)));
  }, [accessToken, id]);

  async function handleCreateRecord(e: FormEvent) {
    e.preventDefault();
    if (!accessToken || !id) return;
    setSaving(true);
    setSaveError(null);
    try {
      const record = await medicalRecordApi.create(accessToken, { patient_id: id, diagnosis: diagnosis || undefined, notes: notes || undefined });
      setRecords((prev) => [record, ...prev]);
      setDiagnosis("");
      setNotes("");
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Couldn't save that record.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <Spinner className="h-5 w-5 text-pine-600" />;
  if (loadError || !patient) {
    return <Alert>You don&rsquo;t have access to this patient, or they don&rsquo;t exist.</Alert>;
  }

  return (
    <div className="flex flex-col gap-6">
      <button onClick={() => router.push("/doctor/patients")} className="text-left text-sm text-ink-soft hover:text-ink">
        ← Back to my patients
      </button>

      <div className="grid grid-cols-2 gap-6">
        <Card>
          <h2 className="font-display text-xl text-ink">Patient details</h2>
          <dl className="mt-3 flex flex-col gap-2 text-sm">
            {patient.gender && <Row label="Gender" value={patient.gender} />}
            {patient.date_of_birth && <Row label="Date of birth" value={patient.date_of_birth} />}
            {patient.phone && <Row label="Phone" value={patient.phone} />}
            {patient.address && <Row label="Address" value={patient.address} />}
            {patient.emergency_contact_name && <Row label="Emergency contact" value={`${patient.emergency_contact_name}${patient.emergency_contact_phone ? " · " + patient.emergency_contact_phone : ""}`} />}
            {patient.known_allergies && <Row label="Known allergies" value={patient.known_allergies} />}
          </dl>
        </Card>

        <Card>
          <h2 className="font-display text-xl text-ink">Write a medical record</h2>
          <form onSubmit={handleCreateRecord} className="mt-3 flex flex-col gap-3">
            <Field label="Diagnosis">
              <Input value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} placeholder="e.g. Contact dermatitis" />
            </Field>
            <Field label="Notes">
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Treatment, follow-up, etc." />
            </Field>
            {saveError && <Alert>{saveError}</Alert>}
            <Button type="submit" disabled={saving} className="w-full">{saving ? "Saving…" : "Save record"}</Button>
          </form>
        </Card>
      </div>

      <section>
        <h2 className="mb-3 font-display text-xl text-ink">Past records you&rsquo;ve written</h2>
        {records.length === 0 ? (
          <p className="text-sm text-ink-soft">Nothing yet.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {records.map((r) => (
              <Card key={r.id}>
                {r.diagnosis && <p className="font-medium text-ink">{r.diagnosis}</p>}
                {r.notes && <p className="mt-1 text-sm text-ink-soft">{r.notes}</p>}
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-sage-100 py-1.5 last:border-0">
      <dt className="text-ink-soft">{label}</dt>
      <dd className="text-right font-medium text-ink">{value}</dd>
    </div>
  );
}
