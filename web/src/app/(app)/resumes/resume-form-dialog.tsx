"use client";

import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { ResumeVariant } from "@/lib/types";

const schema = z.object({
  name: z.string().min(1, "Required"),
  role_family: z.string().optional(),
  positioning_summary: z.string().optional(),
  highlight_projects_text: z.string().optional(),
  is_default: z.boolean(),
});

export type ResumeFormValues = z.infer<typeof schema>;
export type ResumeFormSubmitValues = {
  name: string;
  role_family?: string;
  positioning_summary?: string;
  highlight_projects: string[];
  is_default: boolean;
};

function toFormValues(variant?: ResumeVariant | null): ResumeFormValues {
  return {
    name: variant?.name ?? "",
    role_family: variant?.role_family ?? "",
    positioning_summary: variant?.positioning_summary ?? "",
    highlight_projects_text: (variant?.highlight_projects ?? []).join("\n"),
    is_default: variant?.is_default ?? false,
  };
}

export function ResumeFormDialog({
  open,
  onOpenChange,
  variant,
  onSubmit,
  isPending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  variant?: ResumeVariant | null;
  onSubmit: (values: ResumeFormSubmitValues) => Promise<unknown> | void;
  isPending: boolean;
}) {
  const form = useForm<ResumeFormValues>({
    resolver: zodResolver(schema),
    defaultValues: toFormValues(variant),
  });

  useEffect(() => {
    if (open) form.reset(toFormValues(variant));
  }, [open, variant, form]);

  function handleSubmit(values: ResumeFormValues) {
    return onSubmit({
      name: values.name,
      role_family: values.role_family || undefined,
      positioning_summary: values.positioning_summary || undefined,
      highlight_projects: (values.highlight_projects_text ?? "")
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      is_default: values.is_default,
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{variant ? "Edit resume variant" : "New resume variant"}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Name</FormLabel>
                    <FormControl>
                      <Input placeholder="Data Engineering" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="role_family"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Role family</FormLabel>
                    <FormControl>
                      <Input placeholder="data-engineering" {...field} />
                    </FormControl>
                    <FormDescription>Groups variants for the &quot;default&quot; toggle.</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="positioning_summary"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Positioning summary</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={3}
                      placeholder="2-3 sentences on how this variant frames the sender."
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="highlight_projects_text"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Highlight projects</FormLabel>
                  <FormControl>
                    <Textarea rows={4} placeholder="One project per line" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="is_default"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded border p-3">
                  <div>
                    <FormLabel>Default for this role family</FormLabel>
                    <FormDescription>Unsets the default on other variants sharing it.</FormDescription>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={isPending}>
                {isPending ? "Saving…" : "Save"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
