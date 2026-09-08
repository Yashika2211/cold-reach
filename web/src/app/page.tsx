"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { isUnauthorized, useMe } from "@/hooks/use-auth";

export default function Home() {
  const router = useRouter();
  const { data: me, isError, error, isLoading } = useMe();

  useEffect(() => {
    if (isLoading) return;
    if (me) {
      router.replace("/contacts");
    } else if (isError && isUnauthorized(error)) {
      router.replace("/login");
    }
  }, [me, isLoading, isError, error, router]);

  return null;
}
