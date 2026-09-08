import { apiDelete, apiFetch, apiGet, apiPatch, apiPost } from "@/lib/api";
import type {
  ColumnMapping,
  Company,
  ConnectionTestResult,
  Contact,
  EmailTemplate,
  GenerationResult,
  ImportCommitResponse,
  ImportParseResponse,
  ImportPreviewResponse,
  Page,
  ResumeVariant,
  SendingAccount,
  SendTestEmailResponse,
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

// --- sending accounts ---
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const sendingAccountsApi = {
  list: () => apiGet<SendingAccount[]>("/sending-accounts"),
  createSmtp: (data: {
    display_name: string;
    from_address: string;
    daily_cap: number;
    smtp_credentials: { host: string; port: number; username: string; password: string };
  }) => apiPost<SendingAccount>("/sending-accounts", { ...data, provider_type: "smtp" }),
  createApi: (data: {
    display_name: string;
    from_address: string;
    daily_cap: number;
    api_credentials: { vendor: "resend" | "sendgrid"; api_key: string };
  }) =>
    apiPost<SendingAccount>("/sending-accounts", {
      ...data,
      provider_type: data.api_credentials.vendor === "resend" ? "api_resend" : "api_sendgrid",
    }),
  update: (id: string, data: Partial<Pick<SendingAccount, "display_name" | "daily_cap" | "is_active">>) =>
    apiPatch<SendingAccount>(`/sending-accounts/${id}`, data),
  remove: (id: string) => apiDelete<void>(`/sending-accounts/${id}`),
  test: (id: string) => apiPost<ConnectionTestResult>(`/sending-accounts/${id}/test`),
  sendTest: (id: string, to_email: string, resume_variant_id?: string) =>
    apiPost<SendTestEmailResponse>(`/sending-accounts/${id}/send-test`, {
      to_email,
      resume_variant_id,
    }),
  gmailOAuthStatus: () => apiGet<{ configured: boolean }>("/sending-accounts/oauth/gmail/status"),
  gmailOAuthStartUrl: () => `${API_URL}/sending-accounts/oauth/gmail/start`,
};

// --- resume variants ---
export const resumeVariantsApi = {
  list: () => apiGet<ResumeVariant[]>("/resume-variants"),
  create: (data: {
    name: string;
    role_family?: string;
    positioning_summary?: string;
    highlight_projects: string[];
    is_default?: boolean;
  }) => apiPost<ResumeVariant>("/resume-variants", data),
  update: (id: string, data: Partial<ResumeVariant>) =>
    apiPatch<ResumeVariant>(`/resume-variants/${id}`, data),
  remove: (id: string) => apiDelete<void>(`/resume-variants/${id}`),
  upload: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<ResumeVariant>(`/resume-variants/${id}/upload`, { method: "POST", body: form });
  },
  fileUrl: (id: string) => `${API_URL}/resume-variants/${id}/file`,
};

// --- email templates ---
export const emailTemplatesApi = {
  list: () => apiGet<EmailTemplate[]>("/email-templates"),
  create: (data: {
    name: string;
    subject_skeleton: string;
    body_skeleton: string;
    llm_instructions?: string;
  }) => apiPost<EmailTemplate>("/email-templates", data),
  update: (id: string, data: Partial<EmailTemplate>) =>
    apiPatch<EmailTemplate>(`/email-templates/${id}`, data),
  remove: (id: string) => apiDelete<void>(`/email-templates/${id}`),
};

// --- email generation ---
export const emailGenerationApi = {
  preview: (data: {
    contact_id: string;
    resume_variant_id: string;
    template_id: string;
    step_number?: number;
    steering_note?: string;
  }) => apiPost<GenerationResult>("/email-generation/preview", data),
};
