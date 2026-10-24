"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { authApi, ApiError } from "@/lib/api";
import { Alert, Button, Card, Field, Input } from "@/components/ui";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [devToken, setDevToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await authApi.passwordResetRequest(email);
      setSent(true);
      // Only returned outside production, when emails may just be logged
      setDevToken(res.dev_reset_token ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <Card className="w-full max-w-sm">
        <h1 className="font-display text-2xl text-ink">Reset your password</h1>
        {sent ? (
          <div className="mt-3 flex flex-col gap-4">
            {/* Same message whether or not the account exists, so emails can't be probed */}
            <p className="text-sm text-ink-soft">
              If an account exists for {email}, we&rsquo;ve sent a link to reset your password. It expires in 30 minutes.
            </p>
            {devToken && (
              <Alert variant="success">
                Development mode: emails may only be logged, so here&rsquo;s your link.{" "}
                <Link href={`/reset-password?token=${encodeURIComponent(devToken)}`} className="font-medium underline">
                  Reset password
                </Link>
              </Alert>
            )}
            <Link href="/login" className="text-sm font-medium text-pine-600 hover:underline">Back to log in</Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
            <p className="text-sm text-ink-soft">Enter your account email and we&rsquo;ll send you a reset link.</p>
            <Field label="Email">
              <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </Field>
            {error && <Alert>{error}</Alert>}
            <Button type="submit" disabled={submitting} className="w-full">{submitting ? "Sending…" : "Send reset link"}</Button>
            <Link href="/login" className="text-center text-sm text-ink-soft hover:underline">Back to log in</Link>
          </form>
        )}
      </Card>
    </main>
  );
}
