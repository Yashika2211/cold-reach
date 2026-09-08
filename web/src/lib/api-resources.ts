import { apiDelete, apiFetch, apiGet, apiPatch, apiPost } from "@/lib/api";
import type {
  ColumnMapping,
  Company,
  Contact,
  ImportCommitResponse,
  ImportParseResponse,
  ImportPreviewResponse,
  Page,
  SuppressionEntry,
} from "@/lib/types";

// --- auth ---
export type Me = { id: string; email: string };

export const authApi = {
  me: () => apiGet<Me>("/auth/me"),
  login: (email: string, password: string) => apiPost<Me>("/auth/login", { email, password }),
  logout: () => apiPost<{ status: string }>("/auth/logout"),
};

// --- companies ---
export type CompanyListParams = { search?: string; limit?: number; offset?: number };

function toQuery(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") qs.set(key, String(value));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export const companiesApi = {
  list: (params: CompanyListParams = {}) => apiGet<Page<Company>>(`/companies${toQuery(params)}`),
  create: (data: Partial<Company>) => apiPost<Company>("/companies", data),
  update: (id: string, data: Partial<Company>) => apiPatch<Company>(`/companies/${id}`, data),
  remove: (id: string) => apiDelete<void>(`/companies/${id}`),
};

// --- contacts ---
export type ContactListParams = {
  search?: string;
  status?: string;
  source?: string;
  company_id?: string;
  limit?: number;
  offset?: number;
};

export const contactsApi = {
  list: (params: ContactListParams = {}) => apiGet<Page<Contact>>(`/contacts${toQuery(params)}`),
  create: (data: Record<string, unknown>) => apiPost<Contact>("/contacts", data),
  update: (id: string, data: Record<string, unknown>) => apiPatch<Contact>(`/contacts/${id}`, data),
  remove: (id: string) => apiDelete<void>(`/contacts/${id}`),
  bulkSuppress: (contact_ids: string[]) =>
    apiPost<{ suppressed: number }>("/contacts/bulk-suppress", { contact_ids }),
};

// --- suppression ---
export const suppressionApi = {
  list: (params: { search?: string; limit?: number; offset?: number } = {}) =>
    apiGet<Page<SuppressionEntry>>(`/suppression${toQuery(params)}`),
  create: (email: string, reason = "manual_block") =>
    apiPost<SuppressionEntry>("/suppression", { email, reason }),
  remove: (id: string) => apiDelete<void>(`/suppression/${id}`),
};

// --- contact import ---
export const contactImportApi = {
  parseFile: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<ImportParseResponse>("/contacts/import/parse-file", {
      method: "POST",
      body: form,
    });
  },
  parseText: (text: string) =>
    apiPost<ImportParseResponse>("/contacts/import/parse-text", { text }),
  preview: (import_token: string, mapping: ColumnMapping) =>
    apiPost<ImportPreviewResponse>("/contacts/import/preview", { import_token, mapping }),
  commit: (import_token: string, mapping: ColumnMapping) =>
    apiPost<ImportCommitResponse>("/contacts/import/commit", { import_token, mapping }),
};
