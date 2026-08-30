"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { useAuthedData } from "@/lib/useAuthedData";
import { patientApi } from "@/lib/api";
import { Card, VitalCard, StatusPill, Spinner, EmptyState, Button } from "@/components/ui";

export default function PatientOverviewPage() {
  const { user } = useAuth();
  const { data: appointments, loading: apptsLoading } = useAuthedData((t) => patientApi.myAppointments(t));
  const { data: images, loading: imagesLoading } = useAuthedData((t) => patientApi.myImages(t));

  const upcoming = appointments
    ?.filter((a) => a.status === "pending" || a.status === "confirmed")
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    .slice(0, 3);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="font-display text-3xl text-ink">Hi, {user?.full_name.split(" ")[0]}</h1>
        <p className="mt-1 text-ink-soft">Here&rsquo;s where things stand.</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <p className="text-sm text-ink-soft">Skin photos uploaded</p>
          <p className="mt-1 font-display text-3xl text-ink">{imagesLoading ? "—" : images?.length ?? 0}</p>
        </Card>
        <Card>
          <p className="text-sm text-ink-soft">Upcoming appointments</p>
          <p className="mt-1 font-display text-3xl text-ink">{apptsLoading ? "—" : upcoming?.length ?? 0}</p>
        </Card>
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-xl text-ink">Upcoming appointments</h2>
          <Link href="/patient/appointments" className="text-sm font-medium text-pine-600 hover:underline">View all</Link>
        </div>

        {apptsLoading ? (
          <Spinner className="h-5 w-5 text-pine-600" />
        ) : !upcoming || upcoming.length === 0 ? (
          <EmptyState
            title="Nothing booked yet"
            body="Find a dermatologist and book your first appointment."
            action={<Link href="/patient/doctors"><Button size="sm">Find a doctor</Button></Link>}
          />
        ) : (
          <div className="flex flex-col gap-3">
            {upcoming.map((a) => (
              <VitalCard key={a.id} status={a.status}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-ink">{new Date(a.scheduled_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</p>
                    {a.reason && <p className="mt-0.5 text-sm text-ink-soft">{a.reason}</p>}
                  </div>
                  <StatusPill status={a.status} />
                </div>
              </VitalCard>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
