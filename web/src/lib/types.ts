export type Page<T> = { items: T[]; total: number; limit: number; offset: number };

export type Company = {
  id: string;
  name: string;
  domain: string | null;
  industry: string | null;
  size_band: string | null;
  careers_page_url: string | null;
  location: string | null;
  research_summary: string | null;
  created_at: string;
  updated_at: string;
};

export type ContactSource = "csv" | "enriched" | "manual";
export type VerificationStatus = "unverified" | "verified" | "risky" | "invalid";
export type ContactStatus =
  | "new"
  | "queued"
  | "sent"
  | "opened"
  | "replied"
  | "bounced"
  | "opted_out"
  | "suppressed";

export type Contact = {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string;
  normalized_email: string;
  title: string | null;
  company_id: string | null;
  company_name: string | null;
  linkedin_url: string | null;
  notes: string | null;
  source: ContactSource;
  verification_status: VerificationStatus;
  confidence_score: number | null;
  status: ContactStatus;
  is_suppressed: boolean;
  created_at: string;
  updated_at: string;
};

export type SuppressionEntry = {
  id: string;
  email: string;
  normalized_email: string;
  reason: string;
  source: string;
  created_at: string;
};

export type ImportField =
  | "first_name"
  | "last_name"
  | "email"
  | "title"
  | "company_name"
  | "linkedin_url"
  | "notes";

export const IMPORT_FIELDS: { key: ImportField; label: string; required?: boolean }[] = [
  { key: "email", label: "Email", required: true },
  { key: "first_name", label: "First name" },
  { key: "last_name", label: "Last name" },
  { key: "title", label: "Title" },
  { key: "company_name", label: "Company" },
  { key: "linkedin_url", label: "LinkedIn URL" },
  { key: "notes", label: "Notes" },
];

export type ColumnMapping = Partial<Record<ImportField, string | null>>;

export type ImportParseResponse = {
  import_token: string;
  headers: string[];
  sample_rows: Record<string, string | null>[];
  suggested_mapping: ColumnMapping;
  row_count: number;
};

export type RowResult = {
  row_number: number;
  action: "create" | "skip_duplicate" | "error";
  data: Record<string, string | null>;
  error: string | null;
};

export type ImportPreviewResponse = {
  results: RowResult[];
  summary: { create: number; skip_duplicate: number; error: number };
};

export type ImportCommitResponse = {
  created: number;
  skipped_duplicate: number;
  skipped_invalid: number;
  errors: RowResult[];
};
