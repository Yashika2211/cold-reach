"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { campaignsApi } from "@/lib/api-resources";
import type { CampaignStatus } from "@/lib/types";

const STATUS_VARIANT: Record<CampaignStatus, "default" | "secondary" | "destructive"> = {
  draft: "secondary",
  active: "default",
  paused: "destructive",
  completed: "secondary",
};

export default function CampaignsPage() {
  const { data: campaigns, isLoading } = useQuery({
    queryKey: ["campaigns"],
    queryFn: campaignsApi.list,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Campaigns</h1>
        <Button asChild>
          <Link href="/campaigns/new">New campaign</Link>
        </Button>
      </div>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Mode</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Daily cap</TableHead>
              <TableHead>Sent</TableHead>
              <TableHead>Replies</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {campaigns?.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground">
                  No campaigns yet.
                </TableCell>
              </TableRow>
            )}
            {campaigns?.map((c) => (
              <TableRow key={c.id} className="cursor-pointer">
                <TableCell className="font-medium">
                  <Link href={`/campaigns/${c.id}`} className="hover:underline">
                    {c.name}
                  </Link>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{c.mode === "auto" ? "auto" : "review required"}</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANT[c.status]}>{c.status}</Badge>
                </TableCell>
                <TableCell>{c.daily_cap}/day</TableCell>
                <TableCell>{c.sent_count}</TableCell>
                <TableCell>{c.reply_count}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
