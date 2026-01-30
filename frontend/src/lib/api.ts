const API_BASE = "/api";

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

// --- Types ---

export interface EmailSummary {
  id: number;
  message_id: string;
  folder: string;
  from_address: string | null;
  from_name: string | null;
  subject: string | null;
  date_sent: string | null;
  is_read: boolean;
  is_starred: boolean;
  has_attachments: boolean;
  size_bytes: number | null;
}

export interface EmailDetail extends EmailSummary {
  to_addresses: Array<{ name: string | null; address: string }>;
  cc_addresses: Array<{ name: string | null; address: string }>;
  body_text: string | null;
  body_html: string | null;
  date_synced: string | null;
  raw_headers: Record<string, string> | null;
}

export interface EmailListResponse {
  emails: EmailSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface SyncStatus {
  connected: boolean;
  syncing: boolean;
  last_error: string | null;
  folders: string[];
  stats: {
    total_emails: number;
    sync_states: Array<{
      folder: string;
      last_uid: number;
      last_sync: string | null;
      total_synced: number;
    }>;
  };
}

export interface ProcessingStats {
  total_emails: number;
  classified: number;
  unclassified: number;
  total_links: number;
  pending_links: number;
  total_senders: number;
  by_category: Record<string, number>;
}

export interface ExtractedLink {
  id: number;
  email_id: number;
  url: string;
  domain: string | null;
  link_type: string | null;
  relevance_score: number | null;
  pipeline_status: string;
  extracted_at: string | null;
}

export interface SenderProfile {
  id: number;
  email_address: string;
  display_name: string | null;
  sender_type: string | null;
  total_emails: number;
  emails_opened: number;
  relevance_score: number | null;
  suggested_action: string | null;
  first_seen: string | null;
  last_seen: string | null;
}

export interface Proposal {
  id: number;
  type: string;
  title: string;
  description: string;
  affected_count: number;
  status: string;
  created_at: string | null;
  reviewed_at: string | null;
}

// --- API Functions ---

export const api = {
  // Sync
  syncStatus: () => fetchJSON<SyncStatus>("/sync/status"),
  syncConnect: () => fetchJSON<any>("/sync/connect", { method: "POST" }),
  syncRun: (folder = "INBOX") =>
    fetchJSON<any>(`/sync/run?folder=${folder}`, { method: "POST" }),

  // Emails
  listEmails: (params?: {
    folder?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.folder) query.set("folder", params.folder);
    if (params?.search) query.set("search", params.search);
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    return fetchJSON<EmailListResponse>(`/emails/?${query}`);
  },
  getEmail: (id: number) => fetchJSON<EmailDetail>(`/emails/${id}`),
  emailStats: () => fetchJSON<any>("/emails/stats"),

  // Processing
  processEmails: (limit = 50) =>
    fetchJSON<any>(`/process?limit=${limit}`, { method: "POST" }),
  processingStats: () => fetchJSON<ProcessingStats>("/process/stats"),

  // Links
  listLinks: (params?: {
    min_relevance?: number;
    pipeline_status?: string;
    limit?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.min_relevance != null)
      query.set("min_relevance", String(params.min_relevance));
    if (params?.pipeline_status)
      query.set("pipeline_status", params.pipeline_status);
    if (params?.limit) query.set("limit", String(params.limit));
    return fetchJSON<ExtractedLink[]>(`/links?${query}`);
  },

  // Senders
  listSenders: (params?: { sender_type?: string; sort_by?: string }) => {
    const query = new URLSearchParams();
    if (params?.sender_type) query.set("sender_type", params.sender_type);
    if (params?.sort_by) query.set("sort_by", params.sort_by);
    return fetchJSON<SenderProfile[]>(`/senders?${query}`);
  },

  // Proposals
  listProposals: (status?: string) => {
    const query = status ? `?status=${status}` : "";
    return fetchJSON<Proposal[]>(`/proposals/${query}`);
  },
  generateProposals: () =>
    fetchJSON<any>("/proposals/generate", { method: "POST" }),
  approveProposal: (id: number) =>
    fetchJSON<any>(`/proposals/${id}/approve`, { method: "POST" }),
  rejectProposal: (id: number) =>
    fetchJSON<any>(`/proposals/${id}/reject`, { method: "POST" }),

  // Pipeline
  pipelineStats: () => fetchJSON<any>("/pipeline/stats"),
  queueForExtraction: () =>
    fetchJSON<any>("/pipeline/queue", { method: "POST" }),
};
