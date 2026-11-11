const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
export const API = API_BASE;
export const UNAUTHORIZED_EVENT = "brandwright:unauthorized";
export const CONNECTION_LOST_EVENT = "brandwright:connection-lost";
export const CONNECTION_RESTORED_EVENT = "brandwright:connection-restored";

export type Role = "creator" | "manager" | "reviewer" | "admin";
export type DemoRole = Extract<Role, "creator" | "reviewer" | "admin">;
export type User = { id: string; email: string; role: Role; organisation_id: string; jury_demo?: boolean };
export type Brand = {
  id: string;
  name: string;
  description?: string | null;
  industry?: string | null;
  website_url?: string | null;
  logo_url?: string | null;
  primary_colour?: string | null;
  secondary_colour?: string | null;
  voice?: string | null;
  target_audience?: string | null;
  mission?: string | null;
  vision?: string | null;
  guidelines?: string | null;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
};
export type Content = {
  id: string; title: string | null; current_version_no: number; status: string; created_at?: string; creator_id?: string; brand_id?: string | null;
};
export type ContentDetail = Content & {
  body: string; intent: string; channel: string;
  versions: { version_no: number; body: string; intent: string; created_at: string }[];
};
export type Rule = {
  id: string; brand_id?: string | null; clause_number: string; text: string; category: string;
  channels?: string[]; type?: string | null; config?: Record<string, unknown> | null;
  status: string; version: number;
};
export type Fact = {
  id: string; brand_id?: string | null; text: string; owner?: string | null; source_url?: string | null;
  expires_at?: string | null; status: string; version: number;
};
export type Term = { id: string; brand_id?: string | null; preferred: string; banned: string; notes?: string | null };
export type Asset = { id: string; brand_id?: string | null; name: string; file_url: string; metadata_json?: string | null };
export type RuleDraftUpload = { id: string; title: string; rules: Rule[]; extraction_warnings?: string[] };
export type Clarification = {
  id: string; rule_id: string; current_text: string; drafted_text: string;
  status: string; requires_owner_approval: boolean;
};
export type DecisionAction = "accept" | "edit" | "dismiss";
export type FindingDecision = { action: DecisionAction; reason?: string | null };
export type Finding = {
  id: string; span: { start: number; end: number }; category: string; severity: string;
  status: string; confidence: number; check_type?: string;
  source: { type?: string | null; id?: string | null } | null;
  explanation: string;
  suggestion: { text: string; intent_preserved?: boolean } | null;
  decision?: FindingDecision | null;
};
export type Comment = {
  id: string; user_id: string; span_start: number; span_end: number; body: string; created_at: string;
};
export type AuditEntry = {
  id: string; action: string; details: string | null; created_at: string;
};
export type ReviewResult = {
  findings: Finding[];
  engine_status: "ok" | "degraded" | "queued" | "running" | "completed" | "failed";
  ai_services_used?: string[];
  ai_skipped_reason?: string | null;
  cached?: boolean;
  status?: string;
  job_id?: string | null;
  stage?: string | null;
  review_error?: string | null;
};
export type UploadedReview = ContentDetail & ReviewResult & {
  review_status: string;
  extracted_text?: string;
  extraction_warnings?: string[];
};
export type ReviewStatus = ReviewResult & {
  id: string;
  job_id?: string | null;
  content_id: string;
  version_no: number;
  status: "queued" | "running" | "completed" | "failed" | string;
  stage?: string | null;
  review_error?: string | null;
};
export type ReviewProgressEvent = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  stage: string;
  message: string;
  findings: Finding[];
  metadata?: {
    extracted_text?: string;
    warnings?: string[];
    engine_status?: string;
    ai_services_used?: string[];
  };
};
export type GuidelineHealth = {
  rule_id: string; clause_number: string; text: string; category: string;
  dismiss_rate: number; total_decisions: number; status: "unclear" | "healthy";
};
export type FactDriftAlert = { id: string; ref_id: string; created_at: string; status?: string };
export type TrustScorecard = {
  precision?: number; recall?: number; latest?: { precision?: number; recall?: number };
  created_at?: string | null;
  run_id?: string;
  f1?: number;
  macro_f1?: number;
  sample_count?: number;
  traces?: unknown[];
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

function notifyUnauthorized() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
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
  const isForm = typeof FormData !== "undefined" && init.body instanceof FormData;
  const activeBrandId = typeof window !== "undefined" ? window.localStorage.getItem("bw_active_brand_id") : null;
  const isBrandScoped = path.startsWith("/kb/")
    || path === "/content"
    || path === "/content/upload"
    || path === "/queue";
  const hasExplicitBrand = new URLSearchParams(path.split("?")[1] ?? "").has("brand_id");
  if (activeBrandId && isBrandScoped && !hasExplicitBrand) {
    const separator = path.includes("?") ? "&" : "?";
    path = `${path}${separator}brand_id=${encodeURIComponent(activeBrandId)}`;
  }
  if (init.body && !isForm && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init, headers, cache: "no-store",
    });
    if (typeof window !== "undefined") window.dispatchEvent(new Event(CONNECTION_RESTORED_EVENT));
  } catch (error) {
    if (error instanceof TypeError && typeof window !== "undefined") window.dispatchEvent(new Event(CONNECTION_LOST_EVENT));
    throw error;
  }
  if (!response.ok) {
    if (response.status === 401 && token && path !== "/auth/login") notifyUnauthorized();
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

async function watchReview(
  jobId: string,
  onEvent: (event: ReviewProgressEvent) => void,
  signal?: AbortSignal,
): Promise<ReviewProgressEvent> {
  let lastEventId = "";
  let delay = 500;
  const deadline = Date.now() + 120_000;

  while (Date.now() < deadline) {
    if (signal?.aborted) throw new DOMException("Review stream aborted", "AbortError");
    try {
      const headers = new Headers();
      const token = tk.get();
      if (token) headers.set("Authorization", `Bearer ${token}`);
      if (lastEventId) headers.set("Last-Event-ID", lastEventId);
      const response = await fetch(`${API_BASE}/reviews/${jobId}/events`, {
        headers, cache: "no-store", signal,
      });
      if (typeof window !== "undefined") window.dispatchEvent(new Event(CONNECTION_RESTORED_EVENT));
      if (!response.ok) {
        if (response.status === 401 && token) notifyUnauthorized();
        let detail = response.statusText;
        try {
          const payload = await response.json();
          detail = messageFromDetail(payload?.detail ?? payload?.message ?? detail);
        } catch { /* response did not contain JSON */ }
        throw new ApiError(response.status, detail);
      }
      if (!response.body) throw new Error("The review progress stream is unavailable.");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let terminal: ReviewProgressEvent | null = null;
      while (!terminal) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, "\n");
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          let eventId = "";
          const data: string[] = [];
          for (const line of block.split("\n")) {
            if (line.startsWith("id:")) eventId = line.slice(3).trim();
            if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
          }
          if (!data.length) continue;
          const event = JSON.parse(data.join("\n")) as ReviewProgressEvent;
          if (eventId) lastEventId = eventId;
          onEvent(event);
          if (event.status === "completed" || event.status === "failed") {
            terminal = event;
            break;
          }
        }
      }
      if (terminal) {
        await reader.cancel();
        return terminal;
      }
    } catch (error) {
      if (signal?.aborted || (error instanceof DOMException && error.name === "AbortError")) throw error;
      if (error instanceof TypeError && typeof window !== "undefined") window.dispatchEvent(new Event(CONNECTION_LOST_EVENT));
      if (error instanceof ApiError && error.status < 500) throw error;
      if (!(error instanceof TypeError) && !(error instanceof ApiError)) throw error;
    }
    await new Promise<void>((resolve, reject) => {
      const onAbort = () => {
        clearTimeout(timer);
        signal?.removeEventListener("abort", onAbort);
        reject(new DOMException("Review stream aborted", "AbortError"));
      };
      const timer = setTimeout(() => {
        signal?.removeEventListener("abort", onAbort);
        resolve();
      }, delay);
      signal?.addEventListener("abort", onAbort, { once: true });
    });
    delay = Math.min(delay * 2, 4000);
  }
  throw new Error("The review is taking longer than expected. Reconnect or retry in a moment.");
}

const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, body?: unknown) => request<T>(path, {
  method: "POST", ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

export const api = {
  login: (email: string, password: string) =>
    post<{ access_token: string; token_type: string }>("/auth/login", { email, password }),
  demoLogin: (role: DemoRole) =>
    request<{ access_token: string; token_type: string }>("/auth/demo-login", {
      method: "POST",
      body: JSON.stringify({ role }),
      signal: AbortSignal.timeout(15_000),
    }),
  juryDemoLogin: () =>
    request<{ access_token: string; token_type: string }>("/auth/jury-demo-login", {
      method: "POST",
      signal: AbortSignal.timeout(15_000),
    }),
  jurySwitchRole: (role: DemoRole) =>
    post<{ access_token: string; token_type: string }>("/auth/jury-switch-role", { role }),
  me: () => get<User>("/auth/me"),
  brands: (q = "", includeArchived = false) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (includeArchived) params.set("include_archived", "true");
    const query = params.toString();
    return get<Brand[]>(`/brands${query ? `?${query}` : ""}`);
  },
  brand: (id: string) => get<Brand>(`/brands/${id}`),
  createBrand: (brand: Omit<Brand, "id" | "logo_url" | "status" | "created_at" | "updated_at">) =>
    post<Brand>("/brands", brand),
  updateBrand: (id: string, patch: Partial<Omit<Brand, "id" | "logo_url" | "status" | "created_at" | "updated_at">>) =>
    request<Brand>(`/brands/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  archiveBrand: (id: string) => post<Brand>(`/brands/${id}/archive`),
  uploadBrandLogo: (id: string, file: File) => {
    const form = new FormData();
    form.set("file", file);
    return request<Brand>(`/brands/${id}/logo`, { method: "POST", body: form });
  },
  brandLogo: async (id: string): Promise<Blob> => {
    const token = tk.get();
    const response = await fetch(`${API_BASE}/brands/${encodeURIComponent(id)}/logo`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: "no-store",
    });
    if (!response.ok) {
      if (response.status === 401 && token) notifyUnauthorized();
      let detail = response.statusText;
      try {
        const payload = await response.json();
        detail = messageFromDetail(payload?.detail ?? payload?.message ?? detail);
      } catch { /* response did not contain JSON */ }
      throw new ApiError(response.status, detail, response.headers.get("X-Request-ID") ?? undefined);
    }
    return response.blob();
  },
  rules: (brandId?: string) => get<Rule[]>(brandId ? `/kb/rules?brand_id=${encodeURIComponent(brandId)}` : "/kb/rules"),
  facts: (brandId?: string) => get<Fact[]>(brandId ? `/kb/facts?brand_id=${encodeURIComponent(brandId)}` : "/kb/facts"),
  terms: (brandId?: string) => get<Term[]>(brandId ? `/kb/terms?brand_id=${encodeURIComponent(brandId)}` : "/kb/terms"),
  uploadGuideline: (file: File, brandId?: string) => {
    const form = new FormData();
    form.set("file", file);
    const query = brandId ? `?brand_id=${encodeURIComponent(brandId)}` : "";
    return request<RuleDraftUpload>(`/kb/guidelines${query}`, { method: "POST", body: form });
  },
  updateRule: (id: string, patch: Partial<Rule>) =>
    request<Rule>(`/kb/rules/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  createRule: (rule: Pick<Rule, "clause_number" | "text" | "category"> & Partial<Pick<Rule, "channels">>, brandId?: string) =>
    post<Rule>(`/kb/rules${brandId ? `?brand_id=${encodeURIComponent(brandId)}` : ""}`, rule),
  createFact: (fact: Pick<Fact, "text"> & Partial<Pick<Fact, "owner" | "source_url" | "expires_at">>, brandId?: string) =>
    post<Fact>(`/kb/facts${brandId ? `?brand_id=${encodeURIComponent(brandId)}` : ""}`, fact),
  createTerm: (term: Pick<Term, "preferred" | "banned"> & Partial<Pick<Term, "notes">>, brandId?: string) =>
    post<Term>(`/kb/terms${brandId ? `?brand_id=${encodeURIComponent(brandId)}` : ""}`, term),
  assets: (brandId?: string) => get<Asset[]>(brandId ? `/kb/assets?brand_id=${encodeURIComponent(brandId)}` : "/kb/assets"),
  uploadAsset: (file: File, name: string, brandId?: string) => {
    const form = new FormData();
    form.set("file", file);
    form.set("name", name);
    const query = brandId ? `?brand_id=${encodeURIComponent(brandId)}` : "";
    return request<Asset>(`/kb/assets/upload${query}`, { method: "POST", body: form });
  },
  contentList: () => get<Content[]>("/content"),
  createContent: (title: string, body: string, intent: string, channel: string) =>
    post<Content>("/content", { title, body, intent, channel }),
  uploadContent: (file: File, title: string, intent: string, channel: string, altText: string) => {
    const form = new FormData();
    form.set("file", file);
    form.set("title", title);
    form.set("intent", intent);
    form.set("channel", channel);
    form.set("alt_text", altText);
    return request<UploadedReview>("/content/upload", { method: "POST", body: form });
  },
  saveVersion: (id: string, body: string, intent: string, channel = "general") =>
    post<Content>(`/content/${id}/versions`, { body, intent, channel }),
  content: (id: string) => get<ContentDetail>(`/content/${id}`),
  findings: (id: string) => get<{ version_no: number; status: string; review_error?: string | null; findings: Finding[]; ai_services_used?: string[] }>(`/content/${id}/findings`),
  runReview: (id: string) => post<ReviewResult>(`/content/${id}/review`),
  reviewStatus: (id: string) => get<ReviewStatus>(`/reviews/${id}`),
  watchReview,
  submit: (id: string) => post<Content>(`/content/${id}/submit`),
  approve: (id: string) => post<Content>(`/content/${id}/approve`),
  requestChanges: (id: string) => post<Content>(`/content/${id}/request-changes`),
  queue: () => get<Content[]>("/queue"),
  comments: (id: string) => get<Comment[]>(`/content/${id}/comments`),
  addComment: (id: string, body: string, span_start = 0, span_end = 0) =>
    post<Comment>(`/content/${id}/comments`, { body, span_start, span_end }),
  audit: (id: string) => get<AuditEntry[]>(`/content/${id}/audit`),
  decide: (findingId: string, action: DecisionAction, reason?: string, editedText?: string) =>
    post(`/findings/${findingId}/decision`, {
      action,
      ...(reason ? { reason } : {}),
      ...(editedText !== undefined ? { edited_text: editedText } : {}),
    }),
  health: () => get<GuidelineHealth[]>("/insights/guideline-health"),
  drift: () => get<FactDriftAlert[]>("/alerts/fact-drift"),
  resolveAlert: (id: string) => request(`/alerts/${id}`, { method: "PATCH", body: JSON.stringify({ status: "resolved" }) }),
  scorecard: () => get<TrustScorecard>("/trust/scorecard"),
  runTrust: () => post<TrustScorecard>("/trust/run"),
  draftClarification: (ruleId: string) =>
    post<Clarification>(`/insights/guideline-health/${ruleId}/clarification`),
  updateClarification: (id: string, status: "approved" | "rejected") =>
    request<Clarification>(`/insights/clarifications/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  overview: () => get<Overview>("/insights/overview"),
};

export const isUnverified = (finding: Finding) => finding.status.toLowerCase().includes("verify");
export const isRisky = (finding: Finding) => finding.severity === "high" || isUnverified(finding);
