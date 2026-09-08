"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { ApiError } from "@/lib/api";
import { resumeVariantsApi } from "@/lib/api-resources";
import type { ResumeVariant } from "@/lib/types";
import { ResumeFormDialog, type ResumeFormSubmitValues } from "./resume-form-dialog";

export default function ResumesPage() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ResumeVariant | null>(null);
  const [deleting, setDeleting] = useState<ResumeVariant | null>(null);
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadTargetId = useRef<string | null>(null);

  const { data: variants, isLoading } = useQuery({
    queryKey: ["resume-variants"],
    queryFn: resumeVariantsApi.list,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["resume-variants"] });

  const createMutation = useMutation({
    mutationFn: (values: ResumeFormSubmitValues) => resumeVariantsApi.create(values),
    onSuccess: () => {
      toast.success("Resume variant created");
      setFormOpen(false);
      invalidate();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (values: ResumeFormSubmitValues) => resumeVariantsApi.update(editing!.id, values),
    onSuccess: () => {
      toast.success("Resume variant updated");
      setFormOpen(false);
      setEditing(null);
      invalidate();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => resumeVariantsApi.remove(id),
    onSuccess: () => {
      toast.success("Deleted");
      setDeleting(null);
      invalidate();
    },
  });

  async function handleFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    const id = uploadTargetId.current;
    if (!file || !id) return;
    setUploadingId(id);
    try {
      await resumeVariantsApi.upload(id, file);
      toast.success("PDF uploaded");
      invalidate();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploadingId(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Resume Variants</h1>
        <Button
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          New variant
        </Button>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        hidden
        onChange={handleFileChosen}
      />

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : variants?.length === 0 ? (
        <p className="text-muted-foreground">No resume variants yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {variants?.map((variant) => (
            <Card key={variant.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{variant.name}</CardTitle>
                  <div className="flex gap-1">
                    {variant.is_default && <Badge>default</Badge>}
                    {variant.has_pdf ? (
                      <Badge variant="secondary">PDF attached</Badge>
                    ) : (
                      <Badge variant="destructive">no PDF</Badge>
                    )}
                  </div>
                </div>
                {variant.role_family && (
                  <CardDescription>{variant.role_family}</CardDescription>
                )}
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  {variant.positioning_summary || "No positioning summary yet."}
                </p>
                {variant.highlight_projects.length > 0 && (
                  <ul className="list-disc pl-5 text-sm text-muted-foreground">
                    {variant.highlight_projects.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                )}
                <div className="flex gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      uploadTargetId.current = variant.id;
                      fileInputRef.current?.click();
                    }}
                    disabled={uploadingId === variant.id}
                  >
                    {uploadingId === variant.id
                      ? "Uploading…"
                      : variant.has_pdf
                        ? "Replace PDF"
                        : "Upload PDF"}
                  </Button>
                  {variant.has_pdf && (
                    <Button variant="outline" size="sm" asChild>
                      <a href={resumeVariantsApi.fileUrl(variant.id)} target="_blank" rel="noreferrer">
                        View PDF
                      </a>
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setEditing(variant);
                      setFormOpen(true);
                    }}
                  >
                    Edit
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setDeleting(variant)}>
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <ResumeFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        variant={editing}
        isPending={createMutation.isPending || updateMutation.isPending}
        onSubmit={(values) =>
          editing ? updateMutation.mutateAsync(values) : createMutation.mutateAsync(values)
        }
      />

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete ${deleting?.name}?`}
        description="This can't be undone from the UI."
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
      />
    </div>
  );
}
