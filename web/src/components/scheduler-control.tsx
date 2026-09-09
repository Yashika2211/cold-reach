"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { schedulerApi } from "@/lib/api-resources";

const STATUS_QUERY_KEY = ["scheduler", "status"];

export function SchedulerControl() {
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: STATUS_QUERY_KEY,
    queryFn: schedulerApi.status,
    // Sending happens in the background via Celery Beat, not from an action on this
    // page, so poll to stay accurate if another tab (or the operator) toggles it.
    refetchInterval: 15_000,
  });

  const pause = useMutation({
    mutationFn: schedulerApi.pause,
    onSuccess: (status) => queryClient.setQueryData(STATUS_QUERY_KEY, status),
  });
  const resume = useMutation({
    mutationFn: schedulerApi.resume,
    onSuccess: (status) => queryClient.setQueryData(STATUS_QUERY_KEY, status),
  });

  if (!data) {
    return null;
  }

  const isPaused = data.paused;
  const isMutating = pause.isPending || resume.isPending;

  return (
    <div className="flex shrink-0 items-center gap-2">
      <Badge variant={isPaused ? "destructive" : "default"} className="whitespace-nowrap">
        {isPaused ? "Sending paused" : "Sending on"}
      </Badge>
      <Button
        variant="outline"
        size="sm"
        className="whitespace-nowrap"
        disabled={isMutating}
        onClick={() => (isPaused ? resume.mutate() : pause.mutate())}
      >
        {isPaused ? "Resume sending" : "Pause sending"}
      </Button>
    </div>
  );
}
