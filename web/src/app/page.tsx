"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type HealthResponse = { status: string };

export default function Home() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiFetch<HealthResponse>("/health"),
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">ColdReach</h1>
      <p className="text-muted-foreground text-center">
        Personal cold outreach platform &mdash; foundation is running.
      </p>
      <Card className="w-full">
        <CardHeader>
          <CardTitle>API connection</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          {isLoading && <Badge variant="secondary">Checking&hellip;</Badge>}
          {isError && (
            <>
              <Badge variant="destructive">Unreachable</Badge>
              <span className="text-muted-foreground text-sm">{String(error)}</span>
            </>
          )}
          {data && (
            <>
              <Badge>{data.status}</Badge>
              <span className="text-muted-foreground text-sm">
                Connected to the FastAPI backend.
              </span>
            </>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
