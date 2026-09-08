"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { contactsApi, suppressionApi } from "@/lib/api-resources";
import type { Contact, ContactStatus } from "@/lib/types";
import { ContactFormDialog, type ContactFormValues } from "./contact-form-dialog";
import { ImportWizard } from "./import-wizard";

const STATUS_OPTIONS: { value: ContactStatus | "all"; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "new", label: "New" },
  { value: "queued", label: "Queued" },
  { value: "sent", label: "Sent" },
  { value: "opened", label: "Opened" },
  { value: "replied", label: "Replied" },
  { value: "bounced", label: "Bounced" },
  { value: "opted_out", label: "Opted out" },
  { value: "suppressed", label: "Suppressed" },
];

export default function ContactsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string>("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [bulkSuppressOpen, setBulkSuppressOpen] = useState(false);
  const [deleting, setDeleting] = useState<Contact | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["contacts", search, status],
    queryFn: () =>
      contactsApi.list({ search, status: status === "all" ? undefined : status, limit: 100 }),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["contacts"] });

  const createMutation = useMutation({
    mutationFn: (values: ContactFormValues) => contactsApi.create(cleanValues(values)),
    onSuccess: () => {
      toast.success("Contact added");
      setAddOpen(false);
      invalidate();
    },
    onError: () => toast.error("Failed to add contact — email may already exist"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => contactsApi.remove(id),
    onSuccess: () => {
      toast.success("Contact deleted");
      setDeleting(null);
      invalidate();
    },
  });

  const suppressOneMutation = useMutation({
    mutationFn: (email: string) => suppressionApi.create(email),
    onSuccess: () => {
      toast.success("Suppressed");
      invalidate();
    },
  });

  const bulkSuppressMutation = useMutation({
    mutationFn: () => contactsApi.bulkSuppress(Array.from(selected)),
    onSuccess: (res) => {
      toast.success(`Suppressed ${res.suppressed} contacts`);
      setSelected(new Set());
      setBulkSuppressOpen(false);
      invalidate();
    },
  });

  const items = data?.items ?? [];
  const allSelected = items.length > 0 && items.every((c) => selected.has(c.id));

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(items.map((c) => c.id)));
    }
  }

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Contacts</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            Import CSV
          </Button>
          <Button onClick={() => setAddOpen(true)}>Add contact</Button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Input
          placeholder="Search name, email, title…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {selected.size > 0 && (
        <div className="flex items-center gap-3 rounded border bg-muted/50 px-3 py-2">
          <span className="text-sm">{selected.size} selected</span>
          <Button variant="destructive" size="sm" onClick={() => setBulkSuppressOpen(true)}>
            Suppress
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </div>
      )}

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox checked={allSelected} onCheckedChange={toggleAll} />
              </TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-0" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground">
                  No contacts yet. Add one or import a CSV.
                </TableCell>
              </TableRow>
            )}
            {items.map((contact) => (
              <TableRow key={contact.id}>
                <TableCell>
                  <Checkbox
                    checked={selected.has(contact.id)}
                    onCheckedChange={() => toggleOne(contact.id)}
                  />
                </TableCell>
                <TableCell className="font-medium">
                  {[contact.first_name, contact.last_name].filter(Boolean).join(" ") || "—"}
                </TableCell>
                <TableCell>{contact.email}</TableCell>
                <TableCell>{contact.title ?? "—"}</TableCell>
                <TableCell>{contact.company_name ?? "—"}</TableCell>
                <TableCell className="flex gap-1">
                  <Badge variant={contact.status === "suppressed" ? "destructive" : "secondary"}>
                    {contact.status}
                  </Badge>
                  {contact.is_suppressed && contact.status !== "suppressed" && (
                    <Badge variant="destructive">suppressed</Badge>
                  )}
                </TableCell>
                <TableCell className="flex gap-2 whitespace-nowrap">
                  {!contact.is_suppressed && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => suppressOneMutation.mutate(contact.email)}
                    >
                      Suppress
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => setDeleting(contact)}>
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <ContactFormDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        isPending={createMutation.isPending}
        onSubmit={(values) => createMutation.mutateAsync(values)}
      />

      <ImportWizard open={importOpen} onOpenChange={setImportOpen} onImported={invalidate} />

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete ${deleting?.email}?`}
        description="This removes the contact from ColdReach. This can't be undone from the UI."
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
      />

      <ConfirmDialog
        open={bulkSuppressOpen}
        onOpenChange={setBulkSuppressOpen}
        title={`Suppress ${selected.size} contacts?`}
        description="These addresses are added to the global suppression list and will never be sent to by any campaign."
        confirmLabel="Suppress"
        onConfirm={() => bulkSuppressMutation.mutate()}
      />
    </div>
  );
}

function cleanValues(values: ContactFormValues) {
  return Object.fromEntries(
    Object.entries(values).map(([k, v]) => [k, v === "" ? undefined : v])
  );
}
