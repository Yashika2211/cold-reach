"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { isUnauthorized, useMe } from "@/hooks/use-auth";
import { Nav } from "@/components/nav";
import { Skeleton } from "@/components/ui/skeleton";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: me, isLoading, isError, error } = useMe();

  useEffect(() => {
    if (isError && isUnauthorized(error)) {
      router.replace("/login");
    }
  }, [isError, error, router]);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!me) {
    return null;
  }

  return (
    <div className="min-h-screen">
      <Nav />
      <div className="mx-auto max-w-6xl p-6">{children}</div>
    </div>
  );
}
