"use client";

import { useState, FormEvent } from "react";
import { adminApi, ApiError, HospitalOut } from "@/lib/api";
import { useAuthedData } from "@/lib/useAuthedData";
import { Button, Card, Field, Input, Alert, Spinner, EmptyState, StatusPill } from "@/components/ui";

export default function AdminHospitalsPage() {
  const { data: hospitals, loading, refetch } = useAuthedData((t) => adminApi.platform.listHospitals(t));

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="font-display text-3xl text-ink">Hospitals</h1>
        <p className="mt-1 text-ink-soft">Every hospital on the platform. Create new ones and appoint their admins here.</p>
      </div>

      <CreateHospitalForm onCreated={refetch} />

      <section>
        <h2 className="mb-3 font-display text-xl text-ink">All hospitals</h2>
        {loading ? (
          <Spinner className="h-5 w-5 text-pine-600" />
        ) : !hospitals || hospitals.length === 0 ? (
          <EmptyState title="No hospitals yet" body="Create the first one above." />
        ) : (
          <div className="flex flex-col gap-4">
            {hospitals.map((h) => (
              <HospitalRow key={h.id} hospital={h} onChanged={refetch} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function CreateHospitalForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const token = localStorage.getItem("dermai_access_token")!;
      await adminApi.platform.createHospital(token, { name, slug });
      setName("");
      setSlug("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <h2 className="font-display text-xl text-ink">Create a hospital</h2>
      <form onSubmit={handleSubmit} className="mt-4 grid grid-cols-2 gap-4">
        <Field label="Name">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="City Derma Clinic" required />
        </Field>
        <Field label="Slug" hint="Lowercase, hyphens only — e.g. city-derma-clinic. Patients use this to join.">
          <Input
            value={slug}
            onChange={(e) => setSlug(e.target.value.toLowerCase())}
            placeholder="city-derma-clinic"
            pattern="[a-z0-9]+(-[a-z0-9]+)*"
            required
          />
        </Field>
        {error && (
          <div className="col-span-2">
            <Alert>{error}</Alert>
          </div>
        )}
        <div className="col-span-2">
          <Button type="submit" disabled={submitting}>
            {submitting ? "Creating…" : "Create hospital"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function HospitalRow({ hospital, onChanged }: { hospital: HospitalOut; onChanged: () => void }) {
  const [promoting, setPromoting] = useState(false);
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handlePromote(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      const token = localStorage.getItem("dermai_access_token")!;
      const staff = await adminApi.platform.promoteHospitalAdmin(token, hospital.id, email);
      setSuccess(`${staff.full_name} is now a hospital admin.`);
      setEmail("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="font-medium text-ink">{hospital.name}</p>
          <p className="text-sm text-ink-soft">/{hospital.slug}</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusPill status={hospital.is_active ? "active" : "inactive"} />
          <Button variant="secondary" size="sm" onClick={() => setPromoting((v) => !v)}>
            {promoting ? "Cancel" : "Appoint admin"}
          </Button>
        </div>
      </div>

      {promoting && (
        <form onSubmit={handlePromote} className="mt-4 flex items-end gap-3 border-t border-sage-100 pt-4">
          <div className="flex-1">
            <Field label="User's email" hint="They must already have an account registered under this hospital.">
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="doctor@example.com" required />
            </Field>
          </div>
          <Button type="submit" size="sm" disabled={submitting}>
            {submitting ? "Appointing…" : "Appoint"}
          </Button>
        </form>
      )}
      {error && (
        <div className="mt-3">
          <Alert>{error}</Alert>
        </div>
      )}
      {success && (
        <div className="mt-3">
          <Alert variant="success">{success}</Alert>
        </div>
      )}
    </Card>
  );
}
