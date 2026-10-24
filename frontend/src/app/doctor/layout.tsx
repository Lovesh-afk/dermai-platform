"use client";

import { useEffect, useState, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { doctorApi, ApiError } from "@/lib/api";
import { DashboardShell, icons } from "@/components/DashboardShell";
import { Spinner } from "@/components/ui";

const navItems = [
  { href: "/doctor", label: "Queue", icon: icons.home },
  { href: "/doctor/patients", label: "My patients", icon: icons.users },
  { href: "/doctor/schedule", label: "My hours", icon: icons.calendar },
  { href: "/doctor/profile", label: "My profile", icon: icons.user },
];

export default function DoctorLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useRequireAuth();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (loading || !user) return;
    const token = localStorage.getItem("dermai_access_token")!;
    doctorApi
      .getMyProfile(token)
      .then(() => setReady(true))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          router.push("/onboarding");
        } else {
          setReady(true);
        }
      });
  }, [loading, user, router]);

  if (loading || !ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-6 w-6 text-pine-600" />
      </div>
    );
  }

  return <DashboardShell navItems={navItems}>{children}</DashboardShell>;
}
