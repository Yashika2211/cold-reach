"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { sendingAccountsApi } from "@/lib/api-resources";
import type { SendingAccount } from "@/lib/types";

export function SendTestDialog({
  account,
  onOpenChange,
}: {
  account: SendingAccount | null;
  onOpenChange: (open: boolean) => void;
}) {
  const [toEmail, setToEmail] = useState(account?.from_address ?? "");
  const [sending, setSending] = useState(false);

  async function handleSend() {
    if (!account || !toEmail) return;
    setSending(true);
    try {
      const result = await sendingAccountsApi.sendTest(account.id, toEmail);
      toast.success(`Sent. Provider message ID: ${result.provider_message_id}`);
      onOpenChange(false);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Send failed";
      toast.error(message);
    } finally {
      setSending(false);
    }
  }

  return (
    <Dialog
      open={!!account}
      onOpenChange={(open) => {
        if (!open) onOpenChange(false);
      }}
    >
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Send test email</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Sends a plain test email from <strong>{account?.from_address}</strong> to confirm this
          account actually works. Blocked automatically if the recipient is suppressed.
        </p>
        <div className="space-y-2">
          <Label htmlFor="to-email">Send to</Label>
          <Input
            id="to-email"
            type="email"
            value={toEmail}
            onChange={(e) => setToEmail(e.target.value)}
          />
        </div>
        <DialogFooter>
          <Button onClick={handleSend} disabled={sending || !toEmail}>
            {sending ? "Sending…" : "Send test email"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
