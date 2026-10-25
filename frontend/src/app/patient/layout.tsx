"use client";

import { useEffect, useState, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { patientApi, ApiError } from "@/lib/api";
import { DashboardShell, icons } from "@/components/DashboardShell";
import { Spinner } from "@/components/ui";

const navItems = [
  { href: "/patient", label: "Overview", icon: icons.home },
  { href: "/patient/doctors", label: "Find a doctor", icon: icons.users },
  { href: "/patient/appointments", label: "Appointments", icon: icons.calendar },
  { href: "/patient/images", label: "Skin photos", icon: icons.image },
  { href: "/patient/chat", label: "Ask DermAI", icon: icons.chat },
  { href: "/patient/payments", label: "Payments", icon: icons.wallet },
  { href: "/patient/records", label: "Medical records", icon: icons.file },
  { href: "/patient/profile", label: "My profile", icon: icons.user },
];

export default function PatientLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useRequireAuth();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (loading || !user) return;
    const token = localStorage.getItem("dermai_access_token")!;
    patientApi
      .getProfile(token)
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
