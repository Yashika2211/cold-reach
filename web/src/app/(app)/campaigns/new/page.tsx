"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import {
  campaignsApi,
  contactsApi,
  emailTemplatesApi,
  resumeVariantsApi,
  sendingAccountsApi,
} from "@/lib/api-resources";

const STEPS = [
  "Target",
  "Resume variant",
  "Template",
  "Sending account",
  "Contacts",
  "Schedule",
  "Review",
] as const;

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function NewCampaignPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [creating, setCreating] = useState(false);

  const [name, setName] = useState("");
  const [targetDescription, setTargetDescription] = useState("");
  const [resumeVariantId, setResumeVariantId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [sendingAccountId, setSendingAccountId] = useState("");
  const [selectedContactIds, setSelectedContactIds] = useState<Set<string>>(new Set());
  const [contactSearch, setContactSearch] = useState("");
  const [mode, setMode] = useState<"review_required" | "auto">("review_required");
  const [dailyCap, setDailyCap] = useState(40);
  const [sendWindowStart, setSendWindowStart] = useState("09:00");
  const [sendWindowEnd, setSendWindowEnd] = useState("11:30");
  const [sendWindowDays, setSendWindowDays] = useState<Set<number>>(new Set([1, 2, 3]));
  const [followUpDays, setFollowUpDays] = useState("4, 9");

  const { data: resumeVariants } = useQuery({
    queryKey: ["resume-variants"],
    queryFn: resumeVariantsApi.list,
  });
  const { data: templates } = useQuery({
    queryKey: ["email-templates"],
    queryFn: emailTemplatesApi.list,
  });
  const { data: sendingAccounts } = useQuery({
    queryKey: ["sending-accounts"],
    queryFn: sendingAccountsApi.list,
  });
  const { data: contactsPage } = useQuery({
    queryKey: ["contacts", "for-campaign", contactSearch],
    queryFn: () => contactsApi.list({ search: contactSearch, limit: 100 }),
    enabled: step === 4,
  });

  const selectedResume = resumeVariants?.find((r) => r.id === resumeVariantId);
  const selectedTemplate = templates?.find((t) => t.id === templateId);
  const selectedAccount = sendingAccounts?.find((a) => a.id === sendingAccountId);

  const canProceed = [
    name.trim().length > 0,
    !!resumeVariantId,
    !!templateId,
    !!sendingAccountId,
    selectedContactIds.size > 0,
    dailyCap >= 1 && dailyCap <= 150 && sendWindowDays.size > 0,
    true,
  ][step];

  function toggleDay(day: number) {
    setSendWindowDays((prev) => {
      const next = new Set(prev);
      if (next.has(day)) next.delete(day);
      else next.add(day);
      return next;
    });
  }

  function toggleContact(id: string) {
    setSelectedContactIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleCreate() {
    setCreating(true);
    try {
      const campaign = await campaignsApi.create({
        name,
        target_description: targetDescription || undefined,
        resume_variant_id: resumeVariantId,
        email_template_id: templateId,
        sending_account_id: sendingAccountId,
        mode,
        daily_cap: dailyCap,
        send_window_start_local: `${sendWindowStart}:00`,
        send_window_end_local: `${sendWindowEnd}:00`,
        send_window_days: Array.from(sendWindowDays).sort(),
        follow_up_schedule_days: followUpDays
          .split(",")
          .map((d) => parseInt(d.trim(), 10))
          .filter((d) => !isNaN(d)),
      });

      await campaignsApi.addContacts(campaign.id, Array.from(selectedContactIds));

      toast.success("Campaign created");
      router.push(`/campaigns/${campaign.id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to create campaign");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">New campaign</h1>

      <div className="flex flex-wrap gap-2">
        {STEPS.map((label, i) => (
          <Badge key={label} variant={i === step ? "default" : i < step ? "secondary" : "outline"}>
            {i + 1}. {label}
          </Badge>
        ))}
      </div>

      <div className="min-h-[320px] space-y-4 rounded border p-6">
        {step === 0 && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Campaign name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Q1 backend outreach" />
            </div>
            <div className="space-y-2">
              <Label>Target (free text — job opening discovery lands in a later phase)</Label>
              <Textarea
                rows={4}
                value={targetDescription}
                onChange={(e) => setTargetDescription(e.target.value)}
                placeholder="e.g. Backend SDE roles at seed-to-Series-B startups, remote-friendly or Bangalore/Hyderabad"
              />
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-3">
            <Label>Resume variant</Label>
            {resumeVariants?.length === 0 && (
              <p className="text-sm text-muted-foreground">No resume variants yet — add one first.</p>
            )}
            <div className="space-y-2">
              {resumeVariants?.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setResumeVariantId(r.id)}
                  className={`block w-full rounded border p-3 text-left ${resumeVariantId === r.id ? "border-primary bg-muted" : ""}`}
                >
                  <div className="font-medium">{r.name}</div>
                  <div className="text-sm text-muted-foreground">
                    {r.positioning_summary || "No positioning summary"}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <Label>Email template</Label>
            {templates?.length === 0 && (
              <p className="text-sm text-muted-foreground">No templates yet — add one first.</p>
            )}
            <div className="space-y-2">
              {templates?.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTemplateId(t.id)}
                  className={`block w-full rounded border p-3 text-left ${templateId === t.id ? "border-primary bg-muted" : ""}`}
                >
                  <div className="font-medium">{t.name}</div>
                  <div className="text-sm text-muted-foreground">{t.subject_skeleton}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3">
            <Label>Sending account</Label>
            {sendingAccounts?.length === 0 && (
              <p className="text-sm text-muted-foreground">No sending accounts yet — add one in Settings.</p>
            )}
            <div className="space-y-2">
              {sendingAccounts?.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => setSendingAccountId(a.id)}
                  className={`block w-full rounded border p-3 text-left ${sendingAccountId === a.id ? "border-primary bg-muted" : ""}`}
                >
                  <div className="font-medium">{a.display_name}</div>
                  <div className="text-sm text-muted-foreground">{a.from_address}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Contacts ({selectedContactIds.size} selected)</Label>
              <Input
                placeholder="Search…"
                value={contactSearch}
                onChange={(e) => setContactSearch(e.target.value)}
                className="max-w-xs"
              />
            </div>
            <div className="max-h-72 overflow-auto rounded border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10" />
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Company</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {contactsPage?.items.map((c) => (
                    <TableRow key={c.id} className="cursor-pointer" onClick={() => toggleContact(c.id)}>
                      <TableCell>
                        <Checkbox checked={selectedContactIds.has(c.id)} onCheckedChange={() => toggleContact(c.id)} />
                      </TableCell>
                      <TableCell>{[c.first_name, c.last_name].filter(Boolean).join(" ") || "—"}</TableCell>
                      <TableCell>{c.email}</TableCell>
                      <TableCell>{c.company_name ?? "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}

        {step === 5 && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Mode</Label>
              <Select value={mode} onValueChange={(v) => setMode(v as typeof mode)}>
                <SelectTrigger className="w-64">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="review_required">Review required (default)</SelectItem>
                  <SelectItem value="auto">Auto-send</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Daily send cap (max 150)</Label>
              <Input
                type="number"
                max={150}
                min={1}
                value={dailyCap}
                onChange={(e) => setDailyCap(Number(e.target.value))}
                className="w-32"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Send window start (local time)</Label>
                <Input type="time" value={sendWindowStart} onChange={(e) => setSendWindowStart(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Send window end</Label>
                <Input type="time" value={sendWindowEnd} onChange={(e) => setSendWindowEnd(e.target.value)} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Send window days</Label>
              <div className="flex gap-2">
                {DAY_LABELS.map((label, i) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => toggleDay(i)}
                    className={`rounded border px-3 py-1 text-sm ${sendWindowDays.has(i) ? "border-primary bg-primary text-primary-foreground" : ""}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label>Follow-up schedule (days after previous message, comma-separated)</Label>
              <Input value={followUpDays} onChange={(e) => setFollowUpDays(e.target.value)} className="w-48" />
            </div>
          </div>
        )}

        {step === 6 && (
          <div className="space-y-2 text-sm">
            <p><strong>Name:</strong> {name}</p>
            <p><strong>Target:</strong> {targetDescription || "—"}</p>
            <p><strong>Resume variant:</strong> {selectedResume?.name}</p>
            <p><strong>Template:</strong> {selectedTemplate?.name}</p>
            <p><strong>Sending account:</strong> {selectedAccount?.from_address}</p>
            <p><strong>Contacts:</strong> {selectedContactIds.size}</p>
            <p><strong>Mode:</strong> {mode}</p>
            <p><strong>Daily cap:</strong> {dailyCap}/day</p>
            <p>
              <strong>Send window:</strong> {sendWindowStart}–{sendWindowEnd},{" "}
              {Array.from(sendWindowDays).sort().map((d) => DAY_LABELS[d]).join("/")}
            </p>
            <p><strong>Follow-ups:</strong> day(s) {followUpDays}</p>
          </div>
        )}
      </div>

      <div className="flex justify-between">
        <Button variant="outline" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
          Back
        </Button>
        {step < STEPS.length - 1 ? (
          <Button disabled={!canProceed} onClick={() => setStep((s) => s + 1)}>
            Next
          </Button>
        ) : (
          <Button disabled={creating} onClick={handleCreate}>
            {creating ? "Creating…" : "Create campaign"}
          </Button>
        )}
      </div>
    </div>
  );
}
