"use client";

import { useState, useEffect, FormEvent } from "react";
import { useAuth } from "@/lib/auth";
import { doctorApi, ApiError, DoctorProfile } from "@/lib/api";
import { Card, Field, Input, Textarea, Button, Alert, Spinner } from "@/components/ui";

export default function DoctorProfilePage() {
  const { user, accessToken } = useAuth();
  const [profile, setProfile] = useState<DoctorProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    specialization: "",
    years_experience: "",
    consultation_fee: "",
    bio: "",
    is_accepting_appointments: true,
  });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!accessToken) return;
    doctorApi.getMyProfile(accessToken).then((p) => {
      setProfile(p);
      setForm({
        specialization: p.specialization,
        years_experience: p.years_experience?.toString() ?? "",
        consultation_fee: p.consultation_fee?.toString() ?? "",
        bio: p.bio ?? "",
        is_accepting_appointments: p.is_accepting_appointments,
      });
    }).finally(() => setLoading(false));
  }, [accessToken]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await doctorApi.updateMyProfile(accessToken, {
        specialization: form.specialization,
        years_experience: form.years_experience ? Number(form.years_experience) : undefined,
        consultation_fee: form.consultation_fee ? Number(form.consultation_fee) : undefined,
        bio: form.bio || undefined,
        is_accepting_appointments: form.is_accepting_appointments,
      });
      setProfile(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save your profile.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <Spinner className="h-5 w-5 text-pine-600" />;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl text-ink">My profile</h1>
        <p className="mt-1 text-ink-soft">{user?.email} · License {profile?.license_number}</p>
      </div>

      <Card className="max-w-lg">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Field label="Specialization">
            <Input required value={form.specialization} onChange={(e) => setForm({ ...form, specialization: e.target.value })} />
          </Field>
          <Field label="Years of experience">
            <Input type="number" min={0} value={form.years_experience} onChange={(e) => setForm({ ...form, years_experience: e.target.value })} />
          </Field>
          <Field label="Consultation fee (USD)">
            <Input type="number" min={0} step="0.01" value={form.consultation_fee} onChange={(e) => setForm({ ...form, consultation_fee: e.target.value })} />
          </Field>
          <Field label="Bio">
            <Textarea value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} />
          </Field>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={form.is_accepting_appointments}
              onChange={(e) => setForm({ ...form, is_accepting_appointments: e.target.checked })}
              className="h-4 w-4 rounded border-sage-300 text-pine-600 focus:ring-pine-200"
            />
            Currently accepting new appointments
          </label>
          {error && <Alert>{error}</Alert>}
          {saved && <Alert variant="success">Saved.</Alert>}
          <Button type="submit" disabled={saving} className="w-full">{saving ? "Saving…" : "Save changes"}</Button>
        </form>
      </Card>
    </div>
  );
}
