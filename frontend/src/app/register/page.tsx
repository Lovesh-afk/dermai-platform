"use client";

import { useState, FormEvent, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiError, hospitalApi, HospitalOut } from "@/lib/api";
import { Button, Card, Field, Input, Select, Alert } from "@/components/ui";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [hospitalSlug, setHospitalSlug] = useState("");
  const [hospitals, setHospitals] = useState<HospitalOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    hospitalApi.list().then(setHospitals).catch(() => setHospitals([]));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register({
        email,
        password,
        full_name: fullName,
        hospital_slug: hospitalSlug || null,
      });
      router.push("/onboarding");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="texture-dots flex min-h-screen items-center justify-center px-6 py-10">
      <Card className="w-full max-w-sm">
        <Link href="/" className="mb-6 flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-pine-600 font-display text-xs text-porcelain">D</span>
          <span className="font-display text-base text-ink">DermAI</span>
        </Link>

        <h1 className="font-display text-2xl text-ink">Create your account</h1>
        <p className="mt-1 text-sm text-ink-soft">You&rsquo;ll choose patient or doctor next.</p>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <Field label="Full name">
            <Input required value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Jordan Lee" />
          </Field>
          <Field label="Email">
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </Field>
          <Field label="Password" hint="At least 8 characters.">
            <Input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </Field>
          <Field label="Hospital" hint="Joining an existing hospital lets you register as staff there later. Leave blank to sign up independently.">
            <Select value={hospitalSlug} onChange={(e) => setHospitalSlug(e.target.value)}>
              <option value="">No hospital (sign up independently)</option>
              {hospitals.map((h) => (
                <option key={h.id} value={h.slug}>{h.name}</option>
              ))}
            </Select>
          </Field>
          {error && <Alert>{error}</Alert>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Creating account…" : "Create account"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-soft">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-pine-600 hover:underline">
            Log in
          </Link>
        </p>
      </Card>
    </main>
  );
}
