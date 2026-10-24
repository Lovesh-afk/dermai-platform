"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { authApi, ApiError } from "@/lib/api";
import { Alert, Button, Card, Field, Input } from "@/components/ui";

const MIN_PASSWORD_LENGTH = 8; // mirrors the backend rule

export default function ResetPasswordPage() {
  const [token, setToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Read ?token= directly (avoids Next's Suspense requirement for useSearchParams)
  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token"));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) return setError("The two passwords don't match.");
    if (password.length < MIN_PASSWORD_LENGTH) return setError(`Use at least ${MIN_PASSWORD_LENGTH} characters.`);
    if (!token) return;
    setSubmitting(true);
    setError(null);
    try {
      await authApi.passwordResetConfirm(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reset your password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <Card className="w-full max-w-sm">
        <h1 className="font-display text-2xl text-ink">Choose a new password</h1>
        {done ? (
          <div className="mt-3 flex flex-col gap-4">
            <p className="text-sm text-ink-soft">Your password has been changed, and you&rsquo;ve been signed out of other devices.</p>
            <Link href="/login" className="font-medium text-pine-600 hover:underline">Log in</Link>
          </div>
        ) : token === null ? (
          <p className="mt-3 text-sm text-ink-soft">Checking your link…</p>
        ) : !token ? (
          <div className="mt-3 flex flex-col gap-4">
            <Alert>This reset link is incomplete. Please request a new one.</Alert>
            <Link href="/forgot-password" className="text-sm font-medium text-pine-600 hover:underline">Request a new link</Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
            <Field label="New password">
              <Input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
            </Field>
            <Field label="Confirm new password">
              <Input type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
            </Field>
            {error && (
              <Alert>
                {error}{" "}
                {error.toLowerCase().includes("expired") || error.toLowerCase().includes("invalid") ? (
                  <Link href="/forgot-password" className="underline">Request a new link</Link>
                ) : null}
              </Alert>
            )}
            <Button type="submit" disabled={submitting} className="w-full">{submitting ? "Saving…" : "Set new password"}</Button>
          </form>
        )}
      </Card>
    </main>
  );
}
