"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { patientApi, doctorApi, hospitalApi, HospitalOut, ApiError } from "@/lib/api";
import { Button, Card, Field, Input, Select, Textarea, Alert } from "@/components/ui";

type Choice = "patient" | "doctor" | null;

export default function OnboardingPage() {
  const { user, loading } = useRequireAuth();
  const router = useRouter();
  const [choice, setChoice] = useState<Choice>(null);

  if (loading || !user) {
    return <div className="flex min-h-screen items-center justify-center text-ink-soft">Loading…</div>;
  }

  return (
    <main className="texture-dots flex min-h-screen items-center justify-center px-6 py-10">
      {!choice ? (
        <Card className="w-full max-w-md text-center">
          <h1 className="font-display text-2xl text-ink">One more step, {user.full_name.split(" ")[0]}</h1>
          <p className="mt-1 text-sm text-ink-soft">How will you be using DermAI?</p>
          <div className="mt-6 grid gap-3">
            <button
              onClick={() => setChoice("patient")}
              className="rounded-card border border-sage-200 p-5 text-left transition-colors hover:border-pine-300 hover:bg-pine-50/50"
            >
              <p className="font-medium text-ink">I&rsquo;m a patient</p>
              <p className="mt-0.5 text-sm text-ink-soft">Track my skin health, book appointments, message my doctor.</p>
            </button>
            <button
              onClick={() => setChoice("doctor")}
              className="rounded-card border border-sage-200 p-5 text-left transition-colors hover:border-pine-300 hover:bg-pine-50/50"
            >
              <p className="font-medium text-ink">I&rsquo;m a doctor</p>
              <p className="mt-0.5 text-sm text-ink-soft">Manage my appointment queue and patients.</p>
            </button>
          </div>
        </Card>
      ) : choice === "patient" ? (
        <PatientOnboardingForm onBack={() => setChoice(null)} />
      ) : (
        <DoctorOnboardingForm onBack={() => setChoice(null)} />
      )}
    </main>
  );
}

function PatientOnboardingForm({ onBack }: { onBack: () => void }) {
  const router = useRouter();
  const [gender, setGender] = useState("");
  const [phone, setPhone] = useState("");
  const [allergies, setAllergies] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const token = localStorage.getItem("dermai_access_token")!;
      await patientApi.createProfile(token, { gender: gender || null, phone: phone || null, known_allergies: allergies || null });
      router.push("/patient");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="w-full max-w-md">
      <button onClick={onBack} className="mb-3 text-sm text-ink-soft hover:text-ink">← Back</button>
      <h1 className="font-display text-2xl text-ink">Set up your patient profile</h1>
      <p className="mt-1 text-sm text-ink-soft">You can fill in more, or update this later.</p>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <Field label="Gender (optional)">
          <Input value={gender} onChange={(e) => setGender(e.target.value)} placeholder="e.g. female, male, non-binary" />
        </Field>
        <Field label="Phone (optional)">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="555-123-4567" />
        </Field>
        <Field label="Known allergies (optional)">
          <Textarea value={allergies} onChange={(e) => setAllergies(e.target.value)} placeholder="e.g. penicillin, peanuts" />
        </Field>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" disabled={submitting} className="w-full">
          {submitting ? "Setting up…" : "Continue to my dashboard"}
        </Button>
      </form>
    </Card>
  );
}

function DoctorOnboardingForm({ onBack }: { onBack: () => void }) {
  const router = useRouter();
  const [hospitals, setHospitals] = useState<HospitalOut[]>([]);
  const [hospitalId, setHospitalId] = useState("");
  const [specialization, setSpecialization] = useState("Dermatology");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [bio, setBio] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    hospitalApi.list().then((list) => {
      setHospitals(list);
      if (list.length) setHospitalId(list[0].id);
    });
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const token = localStorage.getItem("dermai_access_token")!;
      await doctorApi.createProfile(token, { hospital_id: hospitalId, specialization, license_number: licenseNumber, bio: bio || undefined });
      router.push("/doctor");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="w-full max-w-md">
      <button onClick={onBack} className="mb-3 text-sm text-ink-soft hover:text-ink">← Back</button>
      <h1 className="font-display text-2xl text-ink">Set up your doctor profile</h1>
      <p className="mt-1 text-sm text-ink-soft">This is what patients will see when booking.</p>

      {hospitals.length === 0 ? (
        <Alert>
          No hospitals exist yet. Ask an admin to create one, or use the API directly (<code>POST /api/v1/hospitals</code>) to add one for testing.
        </Alert>
      ) : (
        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <Field label="Hospital">
            <Select value={hospitalId} onChange={(e) => setHospitalId(e.target.value)}>
              {hospitals.map((h) => (
                <option key={h.id} value={h.id}>{h.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Specialization">
            <Input required value={specialization} onChange={(e) => setSpecialization(e.target.value)} />
          </Field>
          <Field label="License number">
            <Input required value={licenseNumber} onChange={(e) => setLicenseNumber(e.target.value)} placeholder="e.g. LIC-10293" />
          </Field>
          <Field label="Bio (optional)">
            <Textarea value={bio} onChange={(e) => setBio(e.target.value)} placeholder="A line about your practice." />
          </Field>
          {error && <Alert>{error}</Alert>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Setting up…" : "Continue to my dashboard"}
          </Button>
        </form>
      )}
    </Card>
  );
}
