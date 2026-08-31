"use client";

import { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useRequireAuth } from "@/lib/useRequireAuth";
import { useAuth } from "@/lib/auth";
import { DashboardShell, icons } from "@/components/DashboardShell";
import { Spinner } from "@/components/ui";

/** Nav differs by admin type: a SUPER_ADMIN manages the whole
 * platform (hospitals across all tenants) and has no single hospital
 * of their own, so "Staff" (a hospital-scoped view) doesn't apply to
 * them — same reasoning as the backend's /admin/hospital/* endpoints
 * rejecting SUPER_ADMIN with a 400 rather than silently doing nothing. */
export default function AdminLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useRequireAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading || !user) return;
    if (user.role !== "SUPER_ADMIN" && user.role !== "HOSPITAL_ADMIN") {
      router.push("/dashboard");
    }
  }, [loading, user, router]);

  if (loading || !user || (user.role !== "SUPER_ADMIN" && user.role !== "HOSPITAL_ADMIN")) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-6 w-6 text-pine-600" />
      </div>
    );
  }

  const navItems =
    user.role === "SUPER_ADMIN"
      ? [
          { href: "/admin", label: "Overview", icon: icons.home },
          { href: "/admin/hospitals", label: "Hospitals", icon: icons.building },
        ]
      : [
          { href: "/admin", label: "Overview", icon: icons.home },
          { href: "/admin/staff", label: "Staff", icon: icons.users },
        ];

  return <DashboardShell navItems={navItems}>{children}</DashboardShell>;
}
