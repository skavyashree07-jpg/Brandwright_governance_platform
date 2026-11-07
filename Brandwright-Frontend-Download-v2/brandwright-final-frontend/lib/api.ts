const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
export const API = API_BASE;

export type Role = "creator" | "manager" | "reviewer" | "admin";
export type User = {
  id: string;
  email: string;
  role: Role;
  organisation_id: string;
  jury_demo?: boolean;
};
export type Content = {
  id: string; title: string | null; current_version_no: number; status: string; created_at?: string;
};
export type ContentDetail = Content & {
  body: string; intent: string; channel: string;
  versions: { version_no: number; body: string; intent: string; created_at: string }[];
};
export type Rule = {
  id: string; clause_number: string; text: string; category: string;
  channels?: string[]; type?: string | null; config?: Record<string, unknown> | null;
  status: string; version: number;
};
export type Fact = {
  id: string; text: string; owner?: string | null; source_url?: string | null;
  expires_at?: string | null; status: string; version: number;
};
export type Decision = "accept" | "dismiss" | "override";
export type Finding = {
  id: string; span: { start: number; end: number }; category: string; severity: string;
  status: string; confidence: number; check_type?: string;
  source: { type?: string | null; id?: string | null } | null;
  explanation: string;
  suggestion: { text: string; intent_preserved?: boolean } | null;
  decision?: Decision | null;
};
export type Comment = {
  id: string; user_id: string; span_start: number; span_end: number; body: string; created_at: string;
};
export type AuditEntry = {
  id: string; action: string; details: string | null; created_at: string;
};
export type ReviewResult = { findings: Finding[]; engine_status: "ok" | "degraded"; cached?: boolean };
export type GuidelineHealth = {
  rule_id: string; clause_number: string; text: string; category: string;
  dismiss_rate: number; total_decisions: number; status: "unclear" | "healthy";
};
export type FactDriftAlert = { id: string; ref_id: string; created_at: string; status?: string };
export type TrustScorecard = {
  precision?: number; recall?: number; latest?: { precision?: number; recall?: number };
  [key: string]: unknown;
};
export type Overview = {
  content_by_status?: Record<string, number>;
  findings_by_severity?: Record<string, number>;
  unsupported_claims_flagged?: number;
  reviews_run?: number;
  avg_review_latency_ms?: number;
  degraded_reviews?: number;
  human_decisions?: Record<string, number>;
  facts_expiring_30d?: number;
  ai_usage_log_entries?: number;
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public requestId?: string) {
    super(message); this.name = "ApiError";
  }
}

export const tk = {
  get: () => typeof window === "undefined" ? null : window.localStorage.getItem("bw_token"),
  set: (token: string) => { if (typeof window !== "undefined") window.localStorage.setItem("bw_token", token); },
  clear: () => { if (typeof window !== "undefined") window.localStorage.removeItem("bw_token"); },
};

function messageFromDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) return String((item as {msg: unknown}).msg);
      return String(item);
    }).join(" ");
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as {message: unknown}).message);
  }
  return "The request could not be completed. Please try again.";
}

export const errText = (error: unknown) => {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session has expired. Please sign in again.";
    if (error.status === 403) return "Your account does not have permission to do this.";
    if (error.status === 404) return "This item could not be found.";
    if (error.status === 409) return error.message;
    return error.message;
  }
  if (error instanceof TypeError) return "Cannot reach the backend. Check that it is running and try again.";
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = tk.get();
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, {
    ...init, headers, cache: "no-store",
  });
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const payload = await response.json();
      detail = payload?.detail ?? payload?.message ?? detail;
    } catch { /* response did not contain JSON */ }
    throw new ApiError(response.status, messageFromDetail(detail), response.headers.get("X-Request-ID") ?? undefined);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, body?: unknown) => request<T>(path, {
  method: "POST", ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

export const api = {
  login: (email: string, password: string) =>
  post<{ access_token: string; token_type: string }>("/auth/login", { email, password }),

juryDemoLogin: () =>
  post<{ access_token: string; token_type: string }>("/auth/jury-demo-login"),

jurySwitchRole: (role: "admin" | "reviewer" | "creator") =>
  post<{ access_token: string; token_type: string }>("/auth/jury-switch-role", { role }),

me: () => get<User>("/auth/me"),
  rules: () => get<Rule[]>("/kb/rules"),
  facts: () => get<Fact[]>("/kb/facts"),
  contentList: () => get<Content[]>("/content"),
  createContent: (title: string, body: string, intent: string, channel: string) =>
    post<Content>("/content", { title, body, intent, channel }),
  saveVersion: (id: string, body: string, intent: string) =>
    post<Content>(`/content/${id}/versions`, { body, intent }),
  content: (id: string) => get<ContentDetail>(`/content/${id}`),
  findings: (id: string) => get<{ version_no: number; findings: Finding[] }>(`/content/${id}/findings`),
  runReview: (id: string) => post<ReviewResult>(`/content/${id}/review`),
  submit: (id: string) => post<Content>(`/content/${id}/submit`),
  approve: (id: string) => post<Content>(`/content/${id}/approve`),
  requestChanges: (id: string) => post<Content>(`/content/${id}/request-changes`),
  queue: () => get<Content[]>("/queue"),
  comments: (id: string) => get<Comment[]>(`/content/${id}/comments`),
  addComment: (id: string, body: string, span_start = 0, span_end = 0) =>
    post<Comment>(`/content/${id}/comments`, { body, span_start, span_end }),
  audit: (id: string) => get<AuditEntry[]>(`/content/${id}/audit`),
  decide: (findingId: string, action: Decision, reason?: string) =>
    post(`/findings/${findingId}/decision`, { action, ...(reason ? { reason } : {}) }),
  health: () => get<GuidelineHealth[]>("/insights/guideline-health"),
  drift: () => get<FactDriftAlert[]>("/alerts/fact-drift"),
  scorecard: () => get<TrustScorecard>("/trust/scorecard"),
  overview: () => get<Overview>("/insights/overview"),
};

export const isUnverified = (finding: Finding) => finding.status.toLowerCase().includes("verify");
export const isRisky = (finding: Finding) => finding.severity === "high" || isUnverified(finding);
