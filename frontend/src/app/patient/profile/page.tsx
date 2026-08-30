"use client";

import { useState, useEffect, FormEvent } from "react";
import { useAuth } from "@/lib/auth";
import { patientApi, ApiError, PatientProfile } from "@/lib/api";
import { Card, Field, Input, Textarea, Button, Alert, Spinner } from "@/components/ui";

export default function PatientProfilePage() {
  const { user, accessToken } = useAuth();
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ gender: "", phone: "", address: "", emergency_contact_name: "", emergency_contact_phone: "", known_allergies: "" });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!accessToken) return;
    patientApi.getProfile(accessToken).then((p) => {
      setProfile(p);
      setForm({
        gender: p.gender ?? "",
        phone: p.phone ?? "",
        address: p.address ?? "",
        emergency_contact_name: p.emergency_contact_name ?? "",
        emergency_contact_phone: p.emergency_contact_phone ?? "",
        known_allergies: p.known_allergies ?? "",
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
      const updated = await patientApi.updateProfile(accessToken, form);
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
        <p className="mt-1 text-ink-soft">{user?.email}</p>
      </div>

      <Card className="max-w-lg">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Field label="Gender">
            <Input value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} />
          </Field>
          <Field label="Phone">
            <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </Field>
          <Field label="Address">
            <Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </Field>
          <Field label="Emergency contact name">
            <Input value={form.emergency_contact_name} onChange={(e) => setForm({ ...form, emergency_contact_name: e.target.value })} />
          </Field>
          <Field label="Emergency contact phone">
            <Input value={form.emergency_contact_phone} onChange={(e) => setForm({ ...form, emergency_contact_phone: e.target.value })} />
          </Field>
          <Field label="Known allergies">
            <Textarea value={form.known_allergies} onChange={(e) => setForm({ ...form, known_allergies: e.target.value })} />
          </Field>
          {error && <Alert>{error}</Alert>}
          {saved && <Alert variant="success">Saved.</Alert>}
          <Button type="submit" disabled={saving} className="w-full">{saving ? "Saving…" : "Save changes"}</Button>
        </form>
      </Card>
    </div>
  );
}
