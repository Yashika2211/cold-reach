"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { companiesApi } from "@/lib/api-resources";
import type { Company } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { CompanyFormDialog, type CompanyFormValues } from "./company-form-dialog";

export default function CompaniesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Company | null>(null);
  const [deleting, setDeleting] = useState<Company | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["companies", search],
    queryFn: () => companiesApi.list({ search, limit: 100 }),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["companies"] });

  const createMutation = useMutation({
    mutationFn: (values: CompanyFormValues) => companiesApi.create(cleanValues(values)),
    onSuccess: () => {
      toast.success("Company created");
      setFormOpen(false);
      invalidate();
    },
    onError: () => toast.error("Failed to create company"),
  });

  const updateMutation = useMutation({
    mutationFn: (values: CompanyFormValues) =>
      companiesApi.update(editing!.id, cleanValues(values)),
    onSuccess: () => {
      toast.success("Company updated");
      setFormOpen(false);
      setEditing(null);
      invalidate();
    },
    onError: () => toast.error("Failed to update company"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => companiesApi.remove(id),
    onSuccess: () => {
      toast.success("Company deleted");
      setDeleting(null);
      invalidate();
    },
    onError: () => toast.error("Failed to delete company"),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Companies</h1>
        <Button
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          New company
        </Button>
      </div>

      <Input
        placeholder="Search by name or domain…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Domain</TableHead>
              <TableHead>Industry</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Research summary</TableHead>
              <TableHead className="w-0" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground">
                  No companies yet.
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((company) => (
              <TableRow key={company.id}>
                <TableCell className="font-medium">{company.name}</TableCell>
                <TableCell>{company.domain ?? "—"}</TableCell>
                <TableCell>{company.industry ?? "—"}</TableCell>
                <TableCell>{company.location ?? "—"}</TableCell>
                <TableCell className="max-w-xs truncate text-muted-foreground">
                  {company.research_summary ?? "—"}
                </TableCell>
                <TableCell className="flex gap-2 whitespace-nowrap">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setEditing(company);
                      setFormOpen(true);
                    }}
                  >
                    Edit
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setDeleting(company)}>
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <CompanyFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        company={editing}
        isPending={createMutation.isPending || updateMutation.isPending}
        onSubmit={(values) =>
          editing ? updateMutation.mutateAsync(values) : createMutation.mutateAsync(values)
        }
      />

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete ${deleting?.name}?`}
        description="This can't be undone from the UI. Contacts linked to this company will keep their company reference."
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
      />
    </div>
  );
}

function cleanValues(values: CompanyFormValues) {
  return Object.fromEntries(
    Object.entries(values).map(([k, v]) => [k, v === "" ? null : v])
  );
}
