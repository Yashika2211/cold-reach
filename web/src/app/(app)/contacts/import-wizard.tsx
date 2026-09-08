"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { contactImportApi } from "@/lib/api-resources";
import {
  IMPORT_FIELDS,
  type ColumnMapping,
  type ImportCommitResponse,
  type ImportParseResponse,
  type ImportPreviewResponse,
} from "@/lib/types";

type Step = "source" | "mapping" | "preview" | "done";

const NONE_VALUE = "__none__";

export function ImportWizard({
  open,
  onOpenChange,
  onImported,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => void;
}) {
  const [step, setStep] = useState<Step>("source");
  const [pasteText, setPasteText] = useState("");
  const [busy, setBusy] = useState(false);
  const [parsed, setParsed] = useState<ImportParseResponse | null>(null);
  const [mapping, setMapping] = useState<ColumnMapping>({});
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [commitResult, setCommitResult] = useState<ImportCommitResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function reset() {
    setStep("source");
    setPasteText("");
    setParsed(null);
    setMapping({});
    setPreview(null);
    setCommitResult(null);
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  async function handleParsed(response: ImportParseResponse) {
    setParsed(response);
    setMapping(response.suggested_mapping);
    setStep("mapping");
  }

  async function handleFileSelected(file: File) {
    setBusy(true);
    try {
      const response = await contactImportApi.parseFile(file);
      await handleParsed(response);
    } catch (err) {
      toast.error(errorMessage(err, "Could not parse that file"));
    } finally {
      setBusy(false);
    }
  }

  async function handlePasteContinue() {
    if (!pasteText.trim()) return;
    setBusy(true);
    try {
      const response = await contactImportApi.parseText(pasteText);
      await handleParsed(response);
    } catch (err) {
      toast.error(errorMessage(err, "Could not parse that text"));
    } finally {
      setBusy(false);
    }
  }

  async function handlePreview() {
    if (!parsed) return;
    setBusy(true);
    try {
      const response = await contactImportApi.preview(parsed.import_token, mapping);
      setPreview(response);
      setStep("preview");
    } catch (err) {
      toast.error(errorMessage(err, "Preview failed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleCommit() {
    if (!parsed) return;
    setBusy(true);
    try {
      const response = await contactImportApi.commit(parsed.import_token, mapping);
      setCommitResult(response);
      setStep("done");
      onImported();
    } catch (err) {
      toast.error(errorMessage(err, "Import failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import contacts</DialogTitle>
        </DialogHeader>

        {step === "source" && (
          <Tabs defaultValue="file">
            <TabsList>
              <TabsTrigger value="file">Upload CSV</TabsTrigger>
              <TabsTrigger value="paste">Paste text</TabsTrigger>
            </TabsList>
            <TabsContent value="file" className="space-y-4">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                className="block w-full text-sm"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileSelected(file);
                }}
              />
              <p className="text-sm text-muted-foreground">
                CSV files up to 2MB / 2,000 rows. The header row is used for column mapping.
              </p>
            </TabsContent>
            <TabsContent value="paste" className="space-y-4">
              <Textarea
                rows={10}
                placeholder={"First Name,Last Name,Email,Title,Company\nJane,Doe,jane@acme.com,HR Manager,Acme"}
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
              />
              <DialogFooter>
                <Button onClick={handlePasteContinue} disabled={busy || !pasteText.trim()}>
                  Continue
                </Button>
              </DialogFooter>
            </TabsContent>
          </Tabs>
        )}

        {step === "mapping" && parsed && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {parsed.row_count} rows found. Map CSV columns to contact fields — email is
              required.
            </p>
            <div className="space-y-2">
              {IMPORT_FIELDS.map((field) => (
                <div key={field.key} className="flex items-center gap-3">
                  <span className="w-32 text-sm">
                    {field.label}
                    {field.required && <span className="text-destructive"> *</span>}
                  </span>
                  <Select
                    value={mapping[field.key] ?? NONE_VALUE}
                    onValueChange={(value) =>
                      setMapping((m) => ({ ...m, [field.key]: value === NONE_VALUE ? null : value }))
                    }
                  >
                    <SelectTrigger className="w-64">
                      <SelectValue placeholder="Not mapped" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NONE_VALUE}>Not mapped</SelectItem>
                      {parsed.headers.map((header) => (
                        <SelectItem key={header} value={header}>
                          {header}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ))}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setStep("source")}>
                Back
              </Button>
              <Button onClick={handlePreview} disabled={busy || !mapping.email}>
                Preview
              </Button>
            </DialogFooter>
          </div>
        )}

        {step === "preview" && preview && (
          <div className="space-y-4">
            <div className="flex gap-2">
              <Badge>{preview.summary.create} to create</Badge>
              <Badge variant="secondary">{preview.summary.skip_duplicate} duplicates</Badge>
              <Badge variant="destructive">{preview.summary.error} errors</Badge>
            </div>
            <div className="max-h-72 overflow-auto rounded border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">Row</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Result</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {preview.results.map((r) => (
                    <TableRow key={r.row_number}>
                      <TableCell>{r.row_number}</TableCell>
                      <TableCell className="max-w-52 truncate">{r.data.email ?? "—"}</TableCell>
                      <TableCell>
                        {r.action === "create" && <Badge>create</Badge>}
                        {r.action === "skip_duplicate" && (
                          <Badge variant="secondary">duplicate</Badge>
                        )}
                        {r.action === "error" && (
                          <span className="text-sm text-destructive">{r.error}</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setStep("mapping")}>
                Back
              </Button>
              <Button onClick={handleCommit} disabled={busy || preview.summary.create === 0}>
                Import {preview.summary.create} contacts
              </Button>
            </DialogFooter>
          </div>
        )}

        {step === "done" && commitResult && (
          <div className="space-y-4">
            <div className="flex gap-2">
              <Badge>{commitResult.created} created</Badge>
              <Badge variant="secondary">{commitResult.skipped_duplicate} duplicates skipped</Badge>
              <Badge variant="destructive">{commitResult.skipped_invalid} invalid</Badge>
            </div>
            {commitResult.errors.length > 0 && (
              <div className="max-h-52 overflow-auto rounded border p-2 text-sm">
                {commitResult.errors.map((e) => (
                  <div key={e.row_number} className="text-muted-foreground">
                    Row {e.row_number}: {e.error}
                  </div>
                ))}
              </div>
            )}
            <DialogFooter>
              <Button onClick={() => handleOpenChange(false)}>Done</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    try {
      const parsed = JSON.parse(err.message);
      if (typeof parsed === "string") return parsed;
    } catch {
      // not JSON, fall through
    }
    return err.message || fallback;
  }
  return fallback;
}
