"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { ApiError } from "@/lib/api";
import { campaignContactActionsApi, campaignsApi } from "@/lib/api-resources";
import type { CampaignContact } from "@/lib/types";

export default function ReviewQueuePage() {
  const params = useParams<{ id: string }>();
  const campaignId = params.id;

  const [current, setCurrent] = useState<CampaignContact | null>(null);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [confirmSuppress, setConfirmSuppress] = useState(false);
  const [approvedCount, setApprovedCount] = useState(0);

  const bodyTextareaRef = useRef<HTMLTextAreaElement>(null);

  const fetchNext = useCallback(async () => {
    setLoading(true);
    setEditMode(false);
    try {
      const response = await campaignsApi.reviewQueueNext(campaignId);
      setCurrent(response.campaign_contact);
      setRemaining(response.remaining);
      setLoadError(null);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to load next contact";
      // Deliberately don't touch `current` here — a failed fetch must never be
      // confused with the empty-queue state, which also has current === null.
      setLoadError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    fetchNext();
  }, [fetchNext]);

  async function handleApprove() {
    if (!current || busy) return;
    setBusy(true);
    try {
      await campaignContactActionsApi.approve(current.id);
      setApprovedCount((n) => n + 1);
      toast.success("Approved");
      await fetchNext();
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        toast.error("This draft fails the quality gate — regenerate or edit it first");
      } else {
        toast.error(err instanceof ApiError ? err.message : "Approve failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerate(steeringNote?: string) {
    if (!current || busy) return;
    setBusy(true);
    try {
      const updated = await campaignContactActionsApi.regenerate(current.id, steeringNote);
      setCurrent(updated);
      toast.success("Regenerated");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Regenerate failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleSkip() {
    if (!current || busy) return;
    setBusy(true);
    try {
      await campaignContactActionsApi.skip(current.id);
      await fetchNext();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Skip failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleSuppress() {
    if (!current) return;
    setBusy(true);
    try {
      await campaignContactActionsApi.suppress(current.id);
      toast.success(`${current.contact_email} suppressed`);
      setConfirmSuppress(false);
      await fetchNext();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Suppress failed");
    } finally {
      setBusy(false);
    }
  }

  function enterEditMode() {
    if (!current?.current_draft) return;
    setEditSubject(current.current_draft.subject);
    setEditBody(current.current_draft.body);
    setEditMode(true);
    setTimeout(() => bodyTextareaRef.current?.focus(), 0);
  }

  async function handleSaveEdit() {
    if (!current || busy) return;
    setBusy(true);
    try {
      const updated = await campaignContactActionsApi.edit(current.id, editSubject, editBody);
      setCurrent(updated);
      setEditMode(false);
      toast.success("Saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    function handleKeydown(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      const isTyping = target.tagName === "INPUT" || target.tagName === "TEXTAREA";
      if (isTyping || editMode || busy || !current) return;

      switch (e.key.toLowerCase()) {
        case "a":
          e.preventDefault();
          handleApprove();
          break;
        case "r":
          e.preventDefault();
          handleRegenerate();
          break;
        case "e":
          e.preventDefault();
          enterEditMode();
          break;
        case "s":
          e.preventDefault();
          handleSkip();
          break;
        case "x":
          e.preventDefault();
          setConfirmSuppress(true);
          break;
      }
    }

    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, editMode, busy]);

  if (loading && !current) {
    return <Skeleton className="h-96 w-full" />;
  }

  if (loadError) {
    return (
      <div className="space-y-4 text-center">
        <h1 className="text-2xl font-semibold">Couldn&apos;t load the next contact</h1>
        <p className="text-destructive">{loadError}</p>
        <p className="text-sm text-muted-foreground">
          This is usually a temporary LLM provider error (e.g. a rate limit) — safe to retry.
        </p>
        <div className="flex justify-center gap-2">
          <Button onClick={fetchNext}>Retry</Button>
          <Button variant="outline" asChild>
            <Link href={`/campaigns/${campaignId}`}>Back to campaign</Link>
          </Button>
        </div>
      </div>
    );
  }

  if (!current) {
    return (
      <div className="space-y-4 text-center">
        <h1 className="text-2xl font-semibold">Review queue clear 🎉</h1>
        <p className="text-muted-foreground">
          {approvedCount > 0 && `Approved ${approvedCount} this session. `}
          Nothing left pending in this campaign.
        </p>
        <Button asChild>
          <Link href={`/campaigns/${campaignId}`}>Back to campaign</Link>
        </Button>
      </div>
    );
  }

  const draft = current.current_draft;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Link href={`/campaigns/${campaignId}`} className="text-sm text-muted-foreground hover:underline">
          ← Back to campaign
        </Link>
        <div className="text-sm text-muted-foreground">
          {remaining} remaining · {approvedCount} approved this session
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-[280px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{current.contact_name}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {current.contact_title && <p>{current.contact_title}</p>}
            {current.contact_company_name && (
              <p className="font-medium">{current.contact_company_name}</p>
            )}
            <p className="text-muted-foreground">{current.contact_email}</p>
            {current.contact_linkedin_url && (
              <a
                href={current.contact_linkedin_url}
                target="_blank"
                rel="noreferrer"
                className="text-primary hover:underline"
              >
                LinkedIn
              </a>
            )}
            <p className="pt-2 text-xs text-muted-foreground">
              Step {current.current_step === 0 ? "initial" : `follow-up ${current.current_step}`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-4 pt-6">
            {!draft ? (
              <Skeleton className="h-48 w-full" />
            ) : editMode ? (
              <div className="space-y-3">
                <div className="space-y-1">
                  <Label>Subject</Label>
                  <Input value={editSubject} onChange={(e) => setEditSubject(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Body</Label>
                  <Textarea
                    ref={bodyTextareaRef}
                    rows={12}
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                  />
                </div>
                <div className="flex gap-2">
                  <Button onClick={handleSaveEdit} disabled={busy}>
                    Save
                  </Button>
                  <Button variant="outline" onClick={() => setEditMode(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  {draft.quality_gate.passed ? (
                    <Badge>quality gate: passed</Badge>
                  ) : (
                    <Badge variant="destructive">quality gate: failed</Badge>
                  )}
                  <Badge variant="outline">{draft.source}</Badge>
                </div>
                {!draft.quality_gate.passed && (
                  <ul className="list-disc pl-5 text-sm text-destructive">
                    {draft.quality_gate.failures.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                )}
                <div>
                  <Label className="text-xs text-muted-foreground">Subject</Label>
                  <p className="font-medium">{draft.subject}</p>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Body</Label>
                  <p className="whitespace-pre-wrap text-sm">{draft.body}</p>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Why this hook</Label>
                  <p className="text-sm text-muted-foreground">{draft.personalization_rationale}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {!editMode && (
        <div className="flex items-center gap-2">
          <Button onClick={handleApprove} disabled={busy}>
            <kbd className="mr-1.5 rounded bg-black/20 px-1 text-xs">A</kbd>Approve
          </Button>
          <Button variant="outline" onClick={() => handleRegenerate()} disabled={busy}>
            <kbd className="mr-1.5 rounded bg-black/10 px-1 text-xs">R</kbd>Regenerate
          </Button>
          <Button variant="outline" onClick={enterEditMode} disabled={busy}>
            <kbd className="mr-1.5 rounded bg-black/10 px-1 text-xs">E</kbd>Edit
          </Button>
          <Button variant="outline" onClick={handleSkip} disabled={busy}>
            <kbd className="mr-1.5 rounded bg-black/10 px-1 text-xs">S</kbd>Skip
          </Button>
          <Button variant="ghost" onClick={() => setConfirmSuppress(true)} disabled={busy}>
            <kbd className="mr-1.5 rounded bg-black/10 px-1 text-xs">X</kbd>Suppress
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={confirmSuppress}
        onOpenChange={setConfirmSuppress}
        title={`Suppress ${current.contact_email}?`}
        description="This adds them to the global suppression list permanently — no campaign will ever email this address again."
        confirmLabel="Suppress"
        onConfirm={handleSuppress}
      />
    </div>
  );
}
