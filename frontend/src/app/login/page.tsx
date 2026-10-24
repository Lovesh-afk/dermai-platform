"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Button, Card, Field, Input, Alert } from "@/components/ui";

export default function LoginPage() {
  const { login, completeMfaLogin } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [mfaPendingToken, setMfaPendingToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await login(email, password);
      if (result.mfaRequired && result.mfaPendingToken) {
        setMfaPendingToken(result.mfaPendingToken);
      } else {
        router.push("/dashboard");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleMfaVerify(e: FormEvent) {
    e.preventDefault();
    if (!mfaPendingToken) return;
    setError(null);
    setSubmitting(true);
    try {
      await completeMfaLogin(mfaPendingToken, code);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Incorrect code. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="texture-dots flex min-h-screen items-center justify-center px-6">
      <Card className="w-full max-w-sm">
        <Link href="/" className="mb-6 flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-pine-600 font-display text-xs text-porcelain">D</span>
          <span className="font-display text-base text-ink">DermAI</span>
        </Link>

        {!mfaPendingToken ? (
          <>
            <h1 className="font-display text-2xl text-ink">Welcome back</h1>
            <p className="mt-1 text-sm text-ink-soft">Log in to your account.</p>

            <form onSubmit={handleLogin} className="mt-6 flex flex-col gap-4">
              <Field label="Email">
                <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
              </Field>
              <Field label="Password">
                <Input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
              </Field>
              {error && <Alert>{error}</Alert>}
              <Button type="submit" disabled={submitting} className="w-full">
                {submitting ? "Logging in…" : "Log in"}
              </Button>
            </form>
          </>
        ) : (
          <>
            <h1 className="font-display text-2xl text-ink">Enter your code</h1>
            <p className="mt-1 text-sm text-ink-soft">Open your authenticator app for the 6-digit code.</p>

            <form onSubmit={handleMfaVerify} className="mt-6 flex flex-col gap-4">
              <Field label="Authentication code">
                <Input
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="123456"
                  className="text-center font-mono text-lg tracking-[0.3em]"
                />
              </Field>
              {error && <Alert>{error}</Alert>}
              <Button type="submit" disabled={submitting} className="w-full">
                {submitting ? "Verifying…" : "Verify"}
              </Button>
            </form>
          </>
        )}

        <p className="mt-4 text-center text-sm">
          <Link href="/forgot-password" className="text-ink-soft hover:underline">Forgot password?</Link>
        </p>
        <p className="mt-2 text-center text-sm text-ink-soft">
          Don&rsquo;t have an account?{" "}
          <Link href="/register" className="font-medium text-pine-600 hover:underline">
            Sign up
          </Link>
        </p>
      </Card>
    </main>
  );
}
