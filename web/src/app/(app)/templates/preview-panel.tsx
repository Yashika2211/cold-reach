"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { contactsApi, emailGenerationApi, resumeVariantsApi } from "@/lib/api-resources";
import type { EmailTemplate, GenerationResult } from "@/lib/types";

const STEP_OPTIONS = [
  { value: "0", label: "Initial email" },
  { value: "1", label: "Follow-up 1" },
  { value: "2", label: "Follow-up 2" },
];

export function PreviewPanel({ template }: { template: EmailTemplate }) {
  const [contactId, setContactId] = useState<string>("");
  const [resumeVariantId, setResumeVariantId] = useState<string>("");
  const [stepNumber, setStepNumber] = useState("0");
  const [steeringNote, setSteeringNote] = useState("");
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [generating, setGenerating] = useState(false);

  const { data: contactsPage } = useQuery({
    queryKey: ["contacts", "for-preview"],
    queryFn: () => contactsApi.list({ limit: 100 }),
  });
  const { data: resumeVariants } = useQuery({
    queryKey: ["resume-variants"],
    queryFn: resumeVariantsApi.list,
  });

  async function handleGenerate(useSteeringNote: boolean) {
    if (!contactId || !resumeVariantId) {
      toast.error("Pick a contact and resume variant first");
      return;
    }
    setGenerating(true);
    try {
      const response = await emailGenerationApi.preview({
        contact_id: contactId,
        resume_variant_id: resumeVariantId,
        template_id: template.id,
        step_number: Number(stepNumber),
        steering_note: useSteeringNote ? steeringNote || undefined : undefined,
      });
      setResult(response);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Live LLM preview</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1">
            <Label>Contact</Label>
            <Select value={contactId} onValueChange={setContactId}>
              <SelectTrigger>
                <SelectValue placeholder="Pick a contact" />
              </SelectTrigger>
              <SelectContent>
                {contactsPage?.items.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {[c.first_name, c.last_name].filter(Boolean).join(" ") || c.email}
                    {c.company_name ? ` — ${c.company_name}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Resume variant</Label>
            <Select value={resumeVariantId} onValueChange={setResumeVariantId}>
              <SelectTrigger>
                <SelectValue placeholder="Pick a resume variant" />
              </SelectTrigger>
              <SelectContent>
                {resumeVariants?.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Step</Label>
            <Select value={stepNumber} onValueChange={setStepNumber}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STEP_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Button onClick={() => handleGenerate(false)} disabled={generating}>
          {generating ? "Generating…" : "Generate"}
        </Button>

        {result && (
          <div className="space-y-3 rounded border p-4">
            <div className="flex flex-wrap items-center gap-2">
              {result.quality_gate.passed ? (
                <Badge>quality gate: passed</Badge>
              ) : (
                <Badge variant="destructive">quality gate: failed</Badge>
              )}
              {result.needs_more_context && <Badge variant="destructive">needs more context</Badge>}
            </div>

            {!result.quality_gate.passed && (
              <ul className="list-disc pl-5 text-sm text-destructive">
                {result.quality_gate.failures.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            )}

            <div>
              <Label className="text-xs text-muted-foreground">Subject</Label>
              <p className="font-medium">{result.subject}</p>
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Body</Label>
              <p className="whitespace-pre-wrap text-sm">{result.body}</p>
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Personalization rationale</Label>
              <p className="text-sm text-muted-foreground">{result.personalization_rationale}</p>
            </div>

            <div className="space-y-2 pt-2">
              <Label className="text-xs text-muted-foreground">
                Steering note (optional) — regenerate with guidance
              </Label>
              <Textarea
                rows={2}
                value={steeringNote}
                onChange={(e) => setSteeringNote(e.target.value)}
                placeholder="e.g. lead with the internship instead of the hackathon project"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleGenerate(true)}
                disabled={generating}
              >
                Regenerate
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
