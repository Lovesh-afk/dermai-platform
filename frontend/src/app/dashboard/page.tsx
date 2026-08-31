"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { patientApi, doctorApi, ApiError } from "@/lib/api";
import { Spinner } from "@/components/ui";

/** Figures out where a logged-in user actually belongs — the admin
 * dashboard (SUPER_ADMIN/HOSPITAL_ADMIN never have patient or doctor
 * profiles, so they're routed first and skip those lookups entirely),
 * the patient dashboard, the doctor dashboard, or onboarding if
 * they haven't set up either profile yet. This is the one place this
 * logic lives, so /login and /register don't need to duplicate it. */
export default function DashboardDispatcher() {
  const { user, loading } = useRequireAuth();
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (loading || !user) return;

    if (user.role === "SUPER_ADMIN" || user.role === "HOSPITAL_ADMIN") {
      router.push("/admin");
      return;
    }

    async function route() {
      const token = localStorage.getItem("dermai_access_token")!;
      try {
        await patientApi.getProfile(token);
        router.push("/patient");
        return;
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 404) throw err;
      }
      try {
        await doctorApi.getMyProfile(token);
        router.push("/doctor");
        return;
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 404) throw err;
      }
      router.push("/onboarding");
    }

    route().catch(() => setChecking(false));
  }, [loading, user, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner className="h-6 w-6 text-pine-600" />
    </div>
  );
}
