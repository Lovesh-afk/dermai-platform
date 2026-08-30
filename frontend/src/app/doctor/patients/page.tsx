"use client";

import Link from "next/link";
import { doctorApi } from "@/lib/api";
import { useAuthedData } from "@/lib/useAuthedData";
import { Card, Spinner, EmptyState } from "@/components/ui";

export default function DoctorPatientsPage() {
  const { data: patients, loading } = useAuthedData((t) => doctorApi.myPatients(t));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl text-ink">My patients</h1>
        <p className="mt-1 text-ink-soft">Everyone you&rsquo;ve had an appointment with.</p>
      </div>

      {loading ? (
        <Spinner className="h-5 w-5 text-pine-600" />
      ) : !patients || patients.length === 0 ? (
        <EmptyState title="No patients yet" body="Once someone books an appointment with you, they'll show up here." />
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {patients.map((p) => (
            <Link key={p.id} href={`/doctor/patients/${p.id}`}>
              <Card className="transition-shadow hover:shadow-md">
                <p className="font-medium text-ink">{p.gender ? `${p.gender[0].toUpperCase()}${p.gender.slice(1)} patient` : "Patient"}</p>
                {p.phone && <p className="mt-0.5 text-sm text-ink-soft">{p.phone}</p>}
                {p.known_allergies && <p className="mt-1 text-xs text-alert">Allergies: {p.known_allergies}</p>}
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
