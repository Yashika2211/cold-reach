"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { ApiError } from "@/lib/api";
import { sendingAccountsApi } from "@/lib/api-resources";
import type { SendingAccount } from "@/lib/types";
import { ApiAccountDialog, type ApiAccountFormValues } from "./api-account-dialog";
import { SendTestDialog } from "./send-test-dialog";
import { SmtpAccountDialog, type SmtpAccountFormValues } from "./smtp-account-dialog";

const PROVIDER_LABELS: Record<SendingAccount["provider_type"], string> = {
  gmail_oauth: "Gmail (OAuth)",
  smtp: "SMTP",
  api_resend: "Resend",
  api_sendgrid: "SendGrid",
};

export default function SettingsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const [smtpDialogOpen, setSmtpDialogOpen] = useState(false);
  const [apiDialogOpen, setApiDialogOpen] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [sendTestAccount, setSendTestAccount] = useState<SendingAccount | null>(null);
  const [deleting, setDeleting] = useState<SendingAccount | null>(null);

  const { data: accounts, isLoading } = useQuery({
    queryKey: ["sending-accounts"],
    queryFn: sendingAccountsApi.list,
  });

  const { data: gmailStatus } = useQuery({
    queryKey: ["sending-accounts", "gmail-oauth-status"],
    queryFn: sendingAccountsApi.gmailOAuthStatus,
  });

  useEffect(() => {
    const connected = searchParams.get("gmail_connected");
    const error = searchParams.get("gmail_error");
    if (connected) {
      toast.success("Gmail account connected");
      queryClient.invalidateQueries({ queryKey: ["sending-accounts"] });
      router.replace("/settings");
    } else if (error) {
      toast.error(`Gmail connection failed: ${error}`);
      router.replace("/settings");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["sending-accounts"] });

  const createSmtpMutation = useMutation({
    mutationFn: (values: SmtpAccountFormValues) =>
      sendingAccountsApi.createSmtp({
        display_name: values.display_name,
        from_address: values.from_address,
        daily_cap: values.daily_cap,
        smtp_credentials: {
          host: values.host,
          port: values.port,
          username: values.username,
          password: values.password,
        },
      }),
    onSuccess: () => {
      toast.success("SMTP account added");
      setSmtpDialogOpen(false);
      invalidate();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to add account"),
  });

  const createApiMutation = useMutation({
    mutationFn: (values: ApiAccountFormValues) =>
      sendingAccountsApi.createApi({
        display_name: values.display_name,
        from_address: values.from_address,
        daily_cap: values.daily_cap,
        api_credentials: { vendor: values.vendor, api_key: values.api_key },
      }),
    onSuccess: () => {
      toast.success("Account added");
      setApiDialogOpen(false);
      invalidate();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to add account"),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      sendingAccountsApi.update(id, { is_active }),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => sendingAccountsApi.remove(id),
    onSuccess: () => {
      toast.success("Account removed");
      setDeleting(null);
      invalidate();
    },
  });

  async function handleTest(account: SendingAccount) {
    setTestingId(account.id);
    try {
      const result = await sendingAccountsApi.test(account.id);
      if (result.ok) {
        toast.success(`${account.display_name}: connection OK`);
      } else if (result.needs_reauth) {
        toast.error(`${account.display_name}: needs reconnecting — ${result.detail}`);
      } else {
        toast.error(`${account.display_name}: ${result.detail}`);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Test failed");
    } finally {
      setTestingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Settings</h1>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Sending accounts</h2>
          <div className="flex gap-2">
            <Button
              variant="outline"
              disabled={!gmailStatus?.configured}
              onClick={() => {
                window.location.href = sendingAccountsApi.gmailOAuthStartUrl();
              }}
              title={
                gmailStatus?.configured
                  ? undefined
                  : "Set GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET in api/.env first"
              }
            >
              Connect Gmail
            </Button>
            <Button variant="outline" onClick={() => setSmtpDialogOpen(true)}>
              Add SMTP account
            </Button>
            <Button variant="outline" onClick={() => setApiDialogOpen(true)}>
              Add API account
            </Button>
          </div>
        </div>

        {!gmailStatus?.configured && (
          <p className="text-sm text-muted-foreground">
            Gmail OAuth isn&apos;t configured on this server yet — use SMTP with a Gmail app
            password below, or set the Google OAuth env vars to enable it.
          </p>
        )}

        {isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>From address</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Daily cap</TableHead>
                <TableHead>Active</TableHead>
                <TableHead className="w-0" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {accounts?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    No sending accounts yet.
                  </TableCell>
                </TableRow>
              )}
              {accounts?.map((account) => (
                <TableRow key={account.id}>
                  <TableCell className="font-medium">{account.display_name}</TableCell>
                  <TableCell>{account.from_address}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{PROVIDER_LABELS[account.provider_type]}</Badge>
                  </TableCell>
                  <TableCell>{account.daily_cap}/day</TableCell>
                  <TableCell>
                    <Switch
                      checked={account.is_active}
                      onCheckedChange={(checked) =>
                        toggleActiveMutation.mutate({ id: account.id, is_active: checked })
                      }
                    />
                  </TableCell>
                  <TableCell className="flex gap-2 whitespace-nowrap">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleTest(account)}
                      disabled={testingId === account.id}
                    >
                      {testingId === account.id ? "Testing…" : "Test"}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setSendTestAccount(account)}>
                      Send test
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setDeleting(account)}>
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <SmtpAccountDialog
        open={smtpDialogOpen}
        onOpenChange={setSmtpDialogOpen}
        isPending={createSmtpMutation.isPending}
        onSubmit={(values) => createSmtpMutation.mutateAsync(values)}
      />

      <ApiAccountDialog
        open={apiDialogOpen}
        onOpenChange={setApiDialogOpen}
        isPending={createApiMutation.isPending}
        onSubmit={(values) => createApiMutation.mutateAsync(values)}
      />

      <SendTestDialog
        account={sendTestAccount}
        onOpenChange={(open) => !open && setSendTestAccount(null)}
      />

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Remove ${deleting?.display_name}?`}
        description="This account will no longer be usable for sending. This can't be undone from the UI."
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
      />
    </div>
  );
}
