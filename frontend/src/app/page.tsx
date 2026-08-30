"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      router.push("/dashboard");
    }
  }, [loading, user, router]);

  return (
    <main className="texture-dots flex min-h-screen flex-col items-center justify-center px-6">
      <div className="max-w-xl text-center">
        <span className="mb-6 inline-flex items-center gap-2 rounded-full bg-white px-4 py-1.5 text-xs font-medium text-pine-700 shadow-sm">
          <span className="h-1.5 w-1.5 rounded-full bg-pine-500" />
          For clinics &amp; hospital dermatology teams
        </span>
        <h1 className="font-display text-5xl leading-[1.1] tracking-tight text-ink">
          A second pair of eyes,<br />before the appointment.
        </h1>
        <p className="mx-auto mt-5 max-w-md text-ink-soft">
          Patients upload a photo, get a preliminary read, and book time
          with the right dermatologist — all in one place, built for how
          hospitals actually work.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <Link href="/register">
            <Button size="md">Create an account</Button>
          </Link>
          <Link href="/login">
            <Button variant="secondary" size="md">Log in</Button>
          </Link>
        </div>
        <p className="mt-10 text-xs text-ink-soft">
          AI-assisted, never a replacement for your dermatologist&rsquo;s judgment.
        </p>
      </div>
    </main>
  );
}
