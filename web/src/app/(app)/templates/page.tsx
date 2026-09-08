"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

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
import { emailTemplatesApi } from "@/lib/api-resources";
import type { EmailTemplate } from "@/lib/types";
import { PreviewPanel } from "./preview-panel";
import { TemplateFormDialog, type TemplateFormValues } from "./template-form-dialog";

export default function TemplatesPage() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<EmailTemplate | null>(null);
  const [deleting, setDeleting] = useState<EmailTemplate | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: templates, isLoading } = useQuery({
    queryKey: ["email-templates"],
    queryFn: emailTemplatesApi.list,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["email-templates"] });

  const createMutation = useMutation({
    mutationFn: (values: TemplateFormValues) => emailTemplatesApi.create(values),
    onSuccess: () => {
      toast.success("Template created");
      setFormOpen(false);
      invalidate();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (values: TemplateFormValues) => emailTemplatesApi.update(editing!.id, values),
    onSuccess: () => {
      toast.success("Template updated");
      setFormOpen(false);
      setEditing(null);
      invalidate();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => emailTemplatesApi.remove(id),
    onSuccess: () => {
      toast.success("Deleted");
      setDeleting(null);
      if (selectedId === deleting?.id) setSelectedId(null);
      invalidate();
    },
  });

  const selected = templates?.find((t) => t.id === selectedId) ?? null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Templates</h1>
        <Button
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          New template
        </Button>
      </div>

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="space-y-3">
            {templates?.length === 0 && (
              <p className="text-muted-foreground">No templates yet.</p>
            )}
            {templates?.map((template) => (
              <Card
                key={template.id}
                className={selectedId === template.id ? "border-primary" : "cursor-pointer"}
                onClick={() => setSelectedId(template.id)}
              >
                <CardHeader>
                  <CardTitle className="text-base">{template.name}</CardTitle>
                  <CardDescription>{template.subject_skeleton}</CardDescription>
                </CardHeader>
                <CardContent className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditing(template);
                      setFormOpen(true);
                    }}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleting(template);
                    }}
                  >
                    Delete
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>

          <div>
            {selected ? (
              <PreviewPanel template={selected} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Select a template to preview it against a sample contact.
              </p>
            )}
          </div>
        </div>
      )}

      <TemplateFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        template={editing}
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
