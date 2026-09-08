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
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { EmailTemplate } from "@/lib/types";

const schema = z.object({
  name: z.string().min(1, "Required"),
  subject_skeleton: z.string().min(1, "Required"),
  body_skeleton: z.string().min(1, "Required"),
  llm_instructions: z.string().optional(),
});

export type TemplateFormValues = z.infer<typeof schema>;

function toFormValues(template?: EmailTemplate | null): TemplateFormValues {
  return {
    name: template?.name ?? "",
    subject_skeleton: template?.subject_skeleton ?? "",
    body_skeleton: template?.body_skeleton ?? "",
    llm_instructions: template?.llm_instructions ?? "",
  };
}

export function TemplateFormDialog({
  open,
  onOpenChange,
  template,
  onSubmit,
  isPending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  template?: EmailTemplate | null;
  onSubmit: (values: TemplateFormValues) => Promise<unknown> | void;
  isPending: boolean;
}) {
  const form = useForm<TemplateFormValues>({
    resolver: zodResolver(schema),
    defaultValues: toFormValues(template),
  });

  useEffect(() => {
    if (open) form.reset(toFormValues(template));
  }, [open, template, form]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{template ? "Edit template" : "New template"}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Cold outreach - engineering" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="subject_skeleton"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Subject skeleton</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="body_skeleton"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Body skeleton</FormLabel>
                  <FormControl>
                    <Textarea rows={4} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="llm_instructions"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>LLM instructions</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={3}
                      placeholder="Tone and what to personalize on for this template."
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
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
