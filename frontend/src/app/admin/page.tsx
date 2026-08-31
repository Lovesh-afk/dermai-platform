"use client";

import { useAuth } from "@/lib/auth";
import { useAuthedData } from "@/lib/useAuthedData";
import { adminApi } from "@/lib/api";
import { Card, Spinner } from "@/components/ui";

export default function AdminOverviewPage() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "SUPER_ADMIN";

  const { data: platformStats, loading: platformLoading } = useAuthedData(
    (t) => adminApi.platform.stats(t),
    [isSuperAdmin]
  );
  const { data: hospitalStats, loading: hospitalLoading } = useAuthedData(
    (t) => adminApi.hospital.stats(t),
    [isSuperAdmin]
  );

  const loading = isSuperAdmin ? platformLoading : hospitalLoading;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="font-display text-3xl text-ink">
          {isSuperAdmin ? "Platform overview" : "Hospital overview"}
        </h1>
        <p className="mt-1 text-ink-soft">
          {isSuperAdmin
            ? "Numbers across every hospital on DermAI."
            : "How your hospital is doing right now."}
        </p>
      </div>

      {loading ? (
        <Spinner className="h-5 w-5 text-pine-600" />
      ) : isSuperAdmin && platformStats ? (
        <div className="grid grid-cols-3 gap-4">
          <StatCard label="Hospitals" value={platformStats.total_hospitals} />
          <StatCard label="Total users" value={platformStats.total_users} />
          <StatCard label="Appointments" value={platformStats.total_appointments} />
          <StatCard label="Patients" value={platformStats.total_patients} />
          <StatCard label="Doctors" value={platformStats.total_doctors} />
        </div>
      ) : hospitalStats ? (
        <div className="grid grid-cols-3 gap-4">
          <StatCard label="Doctors" value={hospitalStats.total_doctors} />
          <StatCard label="Patients" value={hospitalStats.total_patients} />
          <StatCard label="Appointments" value={hospitalStats.total_appointments} />
          <StatCard label="Completed appointments" value={hospitalStats.total_completed_appointments} />
        </div>
      ) : null}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="mt-1 font-display text-3xl text-ink">{value}</p>
    </Card>
  );
}
