"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

const FUNNEL_ORDER = [
  "pending",
  "queued",
  "sent",
  "replied",
  "bounced",
  "opted_out",
  "suppressed",
  "completed",
  "skipped",
];

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  const campaignId = params.id;
  const queryClient = useQueryClient();

  const { data: campaign, isLoading } = useQuery({
    queryKey: ["campaigns", campaignId],
    queryFn: () => campaignsApi.get(campaignId),
  });

  const setStatus = useMutation({
    mutationFn: (status: CampaignStatus) => campaignsApi.update(campaignId, { status }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["campaigns", campaignId], updated);
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    },
  });
  const { data: funnel } = useQuery({
    queryKey: ["campaigns", campaignId, "funnel"],
    queryFn: () => campaignsApi.funnel(campaignId),
  });
  const { data: contacts, isLoading: contactsLoading } = useQuery({
    queryKey: ["campaigns", campaignId, "contacts"],
    queryFn: () => campaignsApi.listContacts(campaignId),
  });

  if (isLoading || !campaign) {
    return <Skeleton className="h-64 w-full" />;
  }

  const pendingCount = funnel?.by_status["pending"] ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{campaign.name}</h1>
          <p className="text-sm text-muted-foreground">{campaign.target_description}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">{campaign.mode === "auto" ? "auto" : "review required"}</Badge>
          <Badge>{campaign.status}</Badge>
          {campaign.status === "draft" && (
            <Button
              size="sm"
              disabled={setStatus.isPending}
              onClick={() => setStatus.mutate("active")}
            >
              Activate campaign
            </Button>
          )}
          {campaign.status === "active" && (
            <Button
              size="sm"
              variant="outline"
              disabled={setStatus.isPending}
              onClick={() => setStatus.mutate("paused")}
            >
              Pause campaign
            </Button>
          )}
          {campaign.status === "paused" && (
            <Button
              size="sm"
              disabled={setStatus.isPending}
              onClick={() => setStatus.mutate("active")}
            >
              Resume campaign
            </Button>
          )}
        </div>
      </div>

      {campaign.status === "active" && (
        <p className="text-sm text-muted-foreground">
          Active — approved contacts due for sending will go out automatically inside the
          configured send window, subject to the daily cap and the global sending toggle in
          the top bar.
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Funnel</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {FUNNEL_ORDER.map((status) => (
              <div key={status} className="rounded border px-3 py-2 text-center">
                <div className="text-2xl font-semibold">{funnel?.by_status[status] ?? 0}</div>
                <div className="text-xs text-muted-foreground">{status}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {pendingCount > 0 && (
        <Button asChild>
          <Link href={`/campaigns/${campaignId}/review`}>
            Start reviewing ({pendingCount} pending)
          </Link>
        </Button>
      )}

      {contactsLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Contact</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Subject (current draft)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {contacts?.map((cc) => (
              <TableRow key={cc.id}>
                <TableCell>{cc.contact_name}</TableCell>
                <TableCell>{cc.contact_email}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{cc.status}</Badge>
                </TableCell>
                <TableCell className="max-w-xs truncate text-muted-foreground">
                  {cc.current_draft?.subject ?? "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
