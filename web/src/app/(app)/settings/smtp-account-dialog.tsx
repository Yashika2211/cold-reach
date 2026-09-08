"use client";

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

const schema = z.object({
  display_name: z.string().min(1, "Required"),
  from_address: z.string().email("Enter a valid email"),
  host: z.string().min(1, "Required"),
  port: z.coerce.number().int().min(1).max(65535),
  username: z.string().min(1, "Required"),
  password: z.string().min(1, "Required"),
  daily_cap: z.coerce.number().int().min(1).max(150),
});

export type SmtpAccountFormValues = z.infer<typeof schema>;

export function SmtpAccountDialog({
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (values: SmtpAccountFormValues) => Promise<unknown> | void;
  isPending: boolean;
}) {
  const form = useForm<z.input<typeof schema>, unknown, z.output<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      display_name: "",
      from_address: "",
      host: "smtp.gmail.com",
      port: 587,
      username: "",
      password: "",
      daily_cap: 40,
    },
  });

  function handleOpenChange(next: boolean) {
    if (next) form.reset();
    onOpenChange(next);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add SMTP sending account</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="display_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Display name</FormLabel>
                  <FormControl>
                    <Input placeholder="Personal Gmail" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="from_address"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>From address</FormLabel>
                  <FormControl>
                    <Input type="email" placeholder="you@gmail.com" {...field} />
                  </FormControl>
                  <FormDescription>
                    Every email sends from this exact address — it can never be overridden per
                    send.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <FormField
                  control={form.control}
                  name="host"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>SMTP host</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="port"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Port</FormLabel>
                    <FormControl>
                      <Input type="number" {...field} value={field.value as number} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="username"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Username</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Password</FormLabel>
                  <FormControl>
                    <Input type="password" {...field} />
                  </FormControl>
                  <FormDescription>
                    For Gmail, this is a 16-character app password from your Google Account
                    security settings (needs 2-Step Verification on) — not your regular
                    password.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="daily_cap"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Daily send cap</FormLabel>
                  <FormControl>
                    <Input type="number" max={150} {...field} value={field.value as number} />
                  </FormControl>
                  <FormDescription>Hard ceiling is 150/day.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={isPending}>
                {isPending ? "Adding…" : "Add account"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
