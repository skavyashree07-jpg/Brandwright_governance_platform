"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errText, Content, Finding, Rule, Fact, Term, Asset } from "@/lib/api";
import { useUser } from "@/components/Shell";
import { Badge, Button, Card, Dialog, EmptyState, Input, Select, Skeleton, Textarea } from "@/components/ui";
import { downloadCsv } from "@/lib/csv";
import { useSourceLabel } from "@/lib/kb";

type Surface = "dashboard" | "submissions" | "submission" | "review" | "knowledge" | "audit" | "team" | "settings" | "notifications";
const statusTone = (status: string): "neutral" | "success" | "warning" | "danger" => {
  if (["approved", "completed"].includes(status)) return "success";
  if (["changes_requested", "needs_recheck", "failed"].includes(status)) return "danger";
  if (["in_review", "submitted", "queued", "running"].includes(status)) return "warning";
  return "neutral";
};
const readable = (status: string) => status.replace(/_/g, " ");

function PageHeading({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <header className="page-heading product-heading"><div><h1>{title}</h1><p className="mu">{description}</p></div>{action}</header>;
}

function QueryState({ loading, error, empty, children }: { loading: boolean; error?: unknown; empty: boolean; children: React.ReactNode }) {
  if (loading) return <div className="product-skeletons" role="status" aria-label="Loading"><Skeleton /><Skeleton /><Skeleton /></div>;
  if (error) return <p className="alert error" role="alert">{errText(error)}</p>;
  if (empty) return <EmptyState title="Nothing here yet" description="New activity will appear here when the team starts a review." />;
  return <>{children}</>;
}

function Status({ value }: { value: string }) {
  return <Badge tone={statusTone(value)}>{readable(value)}</Badge>;
}

function Dashboard() {
  const user = useUser();
  const items = useQuery({ queryKey: ["content-list", user.organisation_id], queryFn: api.contentList });
  const mine = (items.data ?? []).filter(item => item.creator_id === user.id);
  const open = mine.filter(item => ["changes_requested", "needs_recheck"].includes(item.status));
  const [checklistDismissed, setChecklistDismissed] = useState(false);
  return <div className="product-page">
    <PageHeading title={`Good to see you, ${user.email.split("@")[0]}`} description="Keep your next draft moving through review." action={<Link className="btn pr" href="/workspace">New review</Link>} />
    {!checklistDismissed && <section className="onboarding-panel"><div><h2>Start with the essentials</h2><p>Set up a few things before your first publication review.</p></div><ol><li><Link href="/workspace">Create a first review</Link></li><li>Confirm your team’s approved brand guidance</li><li>Send a draft to a reviewer</li></ol><Button variant="ghost" onClick={() => setChecklistDismissed(true)}>Hide checklist</Button></section>}
    <div className="product-stats"><Card title="Needs your attention"><strong className="product-stat-value">{items.isPending ? "…" : open.length}</strong><p className="mu">Drafts that need your changes</p></Card><Card title="Recent submissions"><strong className="product-stat-value">{items.isPending ? "…" : mine.length}</strong><p className="mu">Your submitted content</p></Card><Card title="Review principle"><p>AI explains and suggests. People make the final decision.</p></Card></div>
    <Card title="Open findings to fix"><QueryState loading={items.isPending} error={items.error} empty={!open.length}>{open.map(item => <Link className="product-list-row" href={`/submissions/${item.id}`} key={item.id}><span>{item.title || "Untitled draft"}</span><Status value={item.status} /><span>Version {item.current_version_no}</span></Link>)}</QueryState></Card>
    <Card title="Recent submissions"><QueryState loading={items.isPending} error={items.error} empty={!mine.length}>{mine.slice(0, 5).map(item => <Link className="product-list-row" href={`/submissions/${item.id}`} key={item.id}><span>{item.title || "Untitled draft"}</span><Status value={item.status} /><time>{item.created_at ? new Date(item.created_at).toLocaleDateString() : `Version ${item.current_version_no}`}</time></Link>)}</QueryState><Link href="/submissions">View all submissions</Link></Card>
    <Card title="A useful review habit"><p className="mu">Write the intent in one clear sentence before checking a draft. Suggestions are evaluated against that intent, and you decide which changes to make.</p></Card>
  </div>;
}

function Submissions() {
  const user = useUser();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [savedViews, setSavedViews] = useState<{ name: string; query: string; status: string }[]>([]);
  const [viewName, setViewName] = useState("");
  const [selectedView, setSelectedView] = useState("");
  const [viewError, setViewError] = useState("");
  const [viewsLoaded, setViewsLoaded] = useState(false);
  const result = useQuery({ queryKey: ["content-list", user.organisation_id], queryFn: api.contentList });
  const storageKey = `bw_submission_views:${user.organisation_id}:${user.id}`;
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed: unknown = JSON.parse(saved);
        if (!Array.isArray(parsed) || parsed.some(item => !item || typeof item.name !== "string" || typeof item.query !== "string" || typeof item.status !== "string")) {
          throw new Error("Saved views have an invalid format.");
        }
        setSavedViews(parsed);
      }
    } catch (cause) { setViewError(errText(cause)); }
    finally { setViewsLoaded(true); }
  }, [storageKey]);
  useEffect(() => {
    if (!viewsLoaded) return;
    try { localStorage.setItem(storageKey, JSON.stringify(savedViews)); }
    catch (cause) { setViewError(errText(cause)); }
  }, [savedViews, storageKey, viewsLoaded]);
  const filtered = (result.data ?? []).filter(item => item.creator_id === user.id)
    .filter(item => `${item.title ?? ""} ${item.id}`.toLowerCase().includes(query.toLowerCase()))
    .filter(item => !status || item.status === status);
  function saveView() {
    const name = viewName.trim();
    if (!name) return;
    setSavedViews(current => [...current.filter(view => view.name !== name), { name, query, status }]);
    setSelectedView(name); setViewName(""); setViewError("");
  }
  function applyView(name: string) {
    setSelectedView(name);
    const saved = savedViews.find(view => view.name === name);
    if (saved) { setQuery(saved.query); setStatus(saved.status); }
  }
  return <div className="product-page"><PageHeading title="Submissions" description="Search your drafts and follow their review status." action={<Link className="btn pr" href="/workspace">New review</Link>} />
    <section className="product-filters"><Input label="Search submissions" value={query} onChange={event => setQuery(event.target.value)} placeholder="Title or ID" /><Select label="Status" value={status} onChange={event => setStatus(event.target.value)} options={[{ value: "", label: "All statuses" }, ...["draft", "submitted", "in_review", "approved", "changes_requested", "needs_recheck"].map(value => ({ value, label: readable(value) }))]} /></section>
    <section className="saved-view-tools" aria-label="Saved submission views">
      <Select label="Saved views" value={selectedView} onChange={event => applyView(event.target.value)} options={[{ value: "", label: "Choose a saved view" }, ...savedViews.map(view => ({ value: view.name, label: view.name }))]} />
      <Input label="Name this view" value={viewName} onChange={event => setViewName(event.target.value)} placeholder="For example: Needs attention" />
      <Button onClick={saveView} disabled={!viewName.trim()}>Save view</Button>
      <Button onClick={() => downloadCsv("brandwright-submissions.csv", ["Title", "Status", "Version", "Created", "ID"], filtered.map(item => [item.title || "Untitled", item.status, String(item.current_version_no), item.created_at ?? "", item.id]))} disabled={!filtered.length}>Export CSV</Button>
      {selectedView && <Button variant="ghost" onClick={() => { setSavedViews(current => current.filter(view => view.name !== selectedView)); setSelectedView(""); }}>Delete view</Button>}
    </section>
    {!viewsLoaded && <p className="mu" role="status">Loading saved views…</p>}
    {viewError && <p className="alert error" role="alert">Saved-view storage error: {viewError}</p>}
    <Card title={`Your content (${filtered.length})`}><QueryState loading={result.isPending} error={result.error} empty={!filtered.length}>{filtered.map(item => <Link className="product-list-row" href={`/submissions/${item.id}`} key={item.id}><span><strong>{item.title || "Untitled draft"}</strong><small>Version {item.current_version_no} · {item.created_at ? new Date(item.created_at).toLocaleString() : "Date unavailable"}</small></span><Status value={item.status} /></Link>)}</QueryState></Card>
  </div>;
}

function ContentDetail({ id, review = false }: { id: string; review?: boolean }) {
  const sourceLabel = useSourceLabel();
  const queryClient = useQueryClient();
  const content = useQuery({ queryKey: ["content", id], queryFn: () => api.content(id) });
  const findings = useQuery({ queryKey: ["findings", id], queryFn: () => api.findings(id) });
  const comments = useQuery({ queryKey: ["comments", id], queryFn: () => api.comments(id) });
  const audit = useQuery({ queryKey: ["audit", id], queryFn: () => api.audit(id), enabled: !review });
  const [comment, setComment] = useState("");
  const [requiredComment, setRequiredComment] = useState("");
  const [dialog, setDialog] = useState<"approve" | "changes" | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const detail = content.data;
  const refresh = async () => { await Promise.all([content.refetch(), findings.refetch(), comments.refetch(), audit.refetch()]); };
  async function decide(event: FormEvent) {
    event.preventDefault();
    if (!detail || !dialog) return;
    setBusy(true); setError("");
    try {
      if (requiredComment.trim()) await api.addComment(id, requiredComment.trim());
      await (dialog === "approve" ? api.approve(id) : api.requestChanges(id));
      setDialog(null); setRequiredComment(""); await refresh();
    } catch (cause) { setError(errText(cause)); }
    finally { setBusy(false); }
  }
  async function addComment(event: FormEvent) {
    event.preventDefault();
    if (!comment.trim()) return;
    setBusy(true); setError("");
    try { await api.addComment(id, comment.trim()); setComment(""); await comments.refetch(); }
    catch (cause) { setError(errText(cause)); }
    finally { setBusy(false); }
  }
  const label = review ? "Review submission" : "Submission details";
  return <div className="product-page"><PageHeading title={detail?.title || label} description={detail ? `Version ${detail.current_version_no} · ${detail.channel} · ${detail.intent}` : "Content, decisions and review history."} action={<div className="product-actions"><Link href={review ? "/queue" : "/submissions"}>Back to {review ? "queue" : "submissions"}</Link><Button onClick={() => window.print()} disabled={!detail}>Print review report</Button></div>} />
    <QueryState loading={content.isPending} error={content.error} empty={!detail}><div className={`detail-split ${review ? "review-detail-split" : ""}`}>
      <Card title="Content"><p className="review-principle">AI explains and suggests. People make the final decision.</p><pre className="content-reading">{detail?.body}</pre></Card>
      <div className="detail-column"><Card title={`Findings (${findings.data?.findings.length ?? 0})`}><QueryState loading={findings.isPending} error={findings.error} empty={!findings.data?.findings.length}>{(findings.data?.findings ?? []).map((finding: Finding) => <article className="finding-summary" key={finding.id}><div><Status value={finding.severity} /> {finding.status.includes("verify") && <Badge tone="warning">Cannot verify</Badge>}</div><p>{finding.explanation}</p>{finding.source && <small>Source reference: {finding.source.id}</small>}{finding.suggestion && <p><strong>Suggested wording:</strong> {finding.suggestion.text}</p>}</article>)}</QueryState></Card>
        <Card title="Decision"><p>Human approval remains the final decision.</p>{review && <div className="product-actions"><Button variant="primary" onClick={() => setDialog("approve")}>Approve</Button><Button onClick={() => setDialog("changes")}>Request changes</Button></div>}</Card>
        <Card title="Comments"><QueryState loading={comments.isPending} error={comments.error} empty={!comments.data?.length}>{(comments.data ?? []).map(entry => <p className="product-list-row" key={entry.id}>{entry.body}<small>{new Date(entry.created_at).toLocaleString()}</small></p>)}</QueryState><form onSubmit={addComment}><Textarea label="Add a comment" value={comment} onChange={event => setComment(event.target.value)} /><Button disabled={busy || !comment.trim()}>Post comment</Button></form></Card>
      </div>
    </div></QueryState>
    {!review && detail && <Card title="Version history">{detail.versions.map(version => <details className="version-item" key={version.version_no}><summary>Version {version.version_no} · {new Date(version.created_at).toLocaleString()}</summary><pre className="content-reading">{version.body}</pre></details>)}</Card>}
    {!review && <Card title="Timeline"><QueryState loading={audit.isPending} error={audit.error} empty={!audit.data?.length}>{(audit.data ?? []).map(entry => <p className="product-list-row" key={entry.id}><span>{entry.action} {entry.details}</span><time>{new Date(entry.created_at).toLocaleString()}</time></p>)}</QueryState></Card>}
    {detail && <section className="print-report" aria-label="Printable review report">
      <h1>Brandwright review report</h1>
      <p><strong>Content:</strong> {detail.title || "Untitled"} | <strong>Version:</strong> {detail.current_version_no}</p>
      <p><strong>Intent:</strong> {detail.intent}</p>
      <p><strong>Channel:</strong> {detail.channel} | <strong>Status:</strong> {detail.status}</p>
      <p><strong>Generated:</strong> {new Date().toLocaleString()}</p>
      <h2>Reviewed content</h2><div className="print-content">{detail.body}</div>
      <h2>Findings</h2>
      {(findings.data?.findings ?? []).length ? findings.data?.findings.map((finding, index) => <article key={finding.id}><h3>{index + 1}. {finding.severity.toUpperCase()} {finding.category}</h3><p>{finding.explanation}</p><p><strong>Source:</strong> {sourceLabel(finding.source) ?? "Cannot verify against an approved source."}</p>{finding.suggestion && <p><strong>Suggestion:</strong> {finding.suggestion.text}</p>}</article>) : <p>No findings.</p>}
    </section>}
    {error && <p className="alert error" role="alert">{error}</p>}
    <Dialog open={dialog !== null} onClose={() => setDialog(null)} title={dialog === "approve" ? "Approve this submission?" : "Request changes"}>
      <form className="product-form" onSubmit={decide}><Textarea label={dialog === "approve" ? "Approval comment (required)" : "What needs to change? (required)"} required value={requiredComment} onChange={event => setRequiredComment(event.target.value)} /><div className="product-actions"><Button variant="primary" loading={busy} disabled={!requiredComment.trim()}>{dialog === "approve" ? "Confirm approval" : "Send request"}</Button><Button type="button" onClick={() => setDialog(null)}>Cancel</Button></div></form>
    </Dialog>
  </div>;
}

function Knowledge() {
  const user = useUser(); const client = useQueryClient();
  const [tab, setTab] = useState("guidelines"); const [search, setSearch] = useState("");
  const [approvalFilter, setApprovalFilter] = useState("");
  const [open, setOpen] = useState(false); const [error, setError] = useState(""); const [success, setSuccess] = useState("");
  const [draft, setDraft] = useState({ clause_number: "", text: "", category: "messaging", fact: "", owner: "", preferred: "", banned: "", assetName: "" });
  const [file, setFile] = useState<File | null>(null);
  const rules = useQuery({ queryKey: ["kb-rules", user.organisation_id], queryFn: api.rules });
  const facts = useQuery({ queryKey: ["kb-facts", user.organisation_id], queryFn: api.facts });
  const terms = useQuery({ queryKey: ["kb-terms", user.organisation_id], queryFn: api.terms });
  const assets = useQuery({ queryKey: ["kb-assets", user.organisation_id], queryFn: api.assets });
  async function save(event: FormEvent) {
    event.preventDefault(); setError(""); setSuccess("");
    try {
      if (tab === "guidelines" && file) await api.uploadGuideline(file);
      else if (tab === "guidelines") await api.createRule({ clause_number: draft.clause_number, text: draft.text, category: draft.category });
      else if (tab === "facts") await api.createFact({ text: draft.fact, owner: draft.owner });
      else if (tab === "terms") await api.createTerm({ preferred: draft.preferred, banned: draft.banned });
      else if (file) await api.uploadAsset(file, draft.assetName || file.name);
      setSuccess("Saved to this organisation’s knowledge base."); setFile(null); setOpen(false);
      await Promise.all([rules.refetch(), facts.refetch(), terms.refetch(), assets.refetch()]);
    } catch (cause) { setError(errText(cause)); }
  }
  const collections = { guidelines: rules, facts, terms, assets };
  const current = collections[tab as keyof typeof collections];
  const rows = current.data ?? [];
  const filtered = rows.filter((entry: Rule | Fact | Term | Asset) => JSON.stringify(entry).toLowerCase().includes(search.toLowerCase()))
    .filter((entry: Rule | Fact | Term | Asset) => !approvalFilter || ("status" in entry && entry.status === approvalFilter));
  return <div className="product-page"><PageHeading title="Brand knowledge" description="Manage the approved sources that inform every review." action={<Button variant="primary" onClick={() => setOpen(true)}>Add {tab === "guidelines" ? "guidance" : tab.slice(0, -1)}</Button>} />
    {success && <p role="status" className="ok">{success}</p>}{error && <p role="alert" className="alert error">{error}</p>}
    <div className="product-tabs" role="tablist" aria-label="Knowledge categories">{["guidelines", "facts", "terms", "assets"].map(value => <button key={value} role="tab" aria-selected={tab === value} onClick={() => setTab(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div>
    <Card title={`${tab[0].toUpperCase()}${tab.slice(1)} (${filtered.length})`}><div className="product-filters"><Input label={`Search ${tab}`} value={search} onChange={event => setSearch(event.target.value)} placeholder="Search knowledge" /><Select label="Approval status" value={approvalFilter} onChange={event => setApprovalFilter(event.target.value)} options={[{ value: "", label: "All statuses" }, { value: "approved", label: "Approved" }, { value: "pending", label: "Pending" }, { value: "draft", label: "Draft" }]} /></div>
      <QueryState loading={current.isPending} error={current.error} empty={!filtered.length}>{filtered.map((entry: Rule | Fact | Term | Asset) => <article className="product-list-row" key={entry.id}><span><strong>{"text" in entry ? entry.text : "preferred" in entry ? `${entry.preferred} / ${entry.banned}` : entry.name ?? ("clause_number" in entry ? entry.clause_number : entry.id)}</strong><small>{"status" in entry ? entry.status : "Approved source"}</small></span>{"status" in entry && entry.status !== "approved" && "clause_number" in entry && <Button size="sm" onClick={async () => { try { await api.updateRule(entry.id, { status: "approved" }); await rules.refetch(); } catch (cause) { setError(errText(cause)); } }}>Approve</Button>}</article>)}</QueryState>
    </Card>
    <Dialog open={open} onClose={() => setOpen(false)} title={`Add ${tab === "guidelines" ? "guidance" : tab.slice(0, -1)}`}><form className="product-form" onSubmit={save}>
      {tab === "guidelines" && <><Input label="Clause number" value={draft.clause_number} onChange={event => setDraft({ ...draft, clause_number: event.target.value })} /><Textarea label="Guideline text" value={draft.text} onChange={event => setDraft({ ...draft, text: event.target.value })} /><label>Or upload a guideline file<input type="file" accept=".txt,.md,.csv,.docx,.pdf" onChange={event => setFile(event.target.files?.[0] ?? null)} /></label></>}
      {tab === "facts" && <><Textarea label="Approved fact" value={draft.fact} onChange={event => setDraft({ ...draft, fact: event.target.value })} /><Input label="Owner" value={draft.owner} onChange={event => setDraft({ ...draft, owner: event.target.value })} /></>}
      {tab === "terms" && <><Input label="Banned term" value={draft.banned} onChange={event => setDraft({ ...draft, banned: event.target.value })} /><Input label="Preferred replacement" value={draft.preferred} onChange={event => setDraft({ ...draft, preferred: event.target.value })} /></>}
      {tab === "assets" && <><Input label="Asset name" value={draft.assetName} onChange={event => setDraft({ ...draft, assetName: event.target.value })} /><label>Asset file<input type="file" onChange={event => setFile(event.target.files?.[0] ?? null)} /></label></>}
      <div className="product-actions"><Button variant="primary">Save</Button><Button type="button" onClick={() => setOpen(false)}>Cancel</Button></div>
    </form></Dialog>
  </div>;
}

function AuditLog() {
  const user = useUser();
  const items = useQuery({ queryKey: ["content-list", user.organisation_id], queryFn: api.contentList });
  const [rows, setRows] = useState<{ id: string; action: string; details: string | null; created_at: string; title: string }[]>([]);
  const [error, setError] = useState("");
  const [auditLoading, setAuditLoading] = useState(false);
  useEffect(() => {
    if (!items.data) return;
    let active = true;
    setAuditLoading(true);
    setError("");
    Promise.all(items.data.map(async item => (await api.audit(item.id)).map(entry => ({ ...entry, title: item.title || "Untitled" }))))
      .then(all => { if (active) setRows(all.flat().sort((a, b) => b.created_at.localeCompare(a.created_at))); })
      .catch(cause => { if (active) setError(errText(cause)); })
      .finally(() => { if (active) setAuditLoading(false); });
    return () => { active = false; };
  }, [items.data]);
  function exportRows() {
    const csv = ["date,action,content,details", ...rows.map(row => [row.created_at, row.action, row.title, row.details ?? ""].map(value => `"${String(value).replace(/"/g, '""')}"`).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); const anchor = document.createElement("a"); anchor.href = url; anchor.download = "brandwright-audit.csv"; anchor.click(); URL.revokeObjectURL(url);
  }
  return <div className="product-page"><PageHeading title="Audit log" description="Organisation actions recorded for the content items available to your role." action={<Button onClick={exportRows} disabled={!rows.length}>Export CSV</Button>} />
    {(error || items.error) && <p role="alert" className="alert error">{error || errText(items.error)} <Button onClick={() => void items.refetch()}>Retry</Button></p>}<Card title="Recorded actions"><QueryState loading={items.isPending || auditLoading} error={undefined} empty={!rows.length}>{rows.map(row => <div className="product-list-row" key={row.id}><span><strong>{row.action}</strong><small>{row.title}{row.details ? ` · ${row.details}` : ""}</small></span><time>{new Date(row.created_at).toLocaleString()}</time></div>)}</QueryState></Card>
  </div>;
}

function Notifications() {
  const user = useUser(); const queue = useQuery({ queryKey: ["review-queue", user.organisation_id], queryFn: api.queue, enabled: user.role !== "creator" }); const drift = useQuery({ queryKey: ["fact-drift", user.organisation_id], queryFn: api.drift });
  return <div className="product-page"><PageHeading title="Notifications" description="Review work and approved facts that may need attention." />
    <Card title="Review queue"><QueryState loading={user.role !== "creator" && queue.isPending} error={queue.error} empty={!queue.data?.length}>{(queue.data ?? []).map(item => <Link className="product-list-row" href={`/queue/${item.id}`} key={item.id}><span>{item.title || "Untitled submission"}</span><Status value={item.status} /></Link>)}</QueryState></Card>
    <Card title="Fact drift"><QueryState loading={drift.isPending} error={drift.error} empty={!drift.data?.length}>{(drift.data ?? []).map(alert => <Link className="product-list-row" href="/insights" key={alert.id}><span>Fact changed for content {alert.ref_id.slice(0, 8)}</span><time>{new Date(alert.created_at).toLocaleString()}</time></Link>)}</QueryState></Card>
  </div>;
}

function AdminMock({ page }: { page: "team" | "settings" }) {
  const [saved, setSaved] = useState(false);
  if (page === "team") return <div className="product-page"><PageHeading title="Team" description="Review the access model for this organisation." /><p className="mock-notice"><Badge tone="warning">Example data</Badge> Team listing, invitation, and role-management endpoints are not available in this API.</p><Card title="Example team members">{[["Asha Raman", "Admin"], ["Mina Patel", "Manager"], ["Dev Shah", "Reviewer"], ["Ira Sen", "Creator"]].map(([name, role]) => <div key={name} className="product-list-row"><span><strong>{name}</strong><small>example@brandwright.test</small></span><Badge>{role}</Badge></div>)}<Button onClick={() => setSaved(true)}>Invite a teammate</Button>{saved && <p role="status">Invitation preview only. No invitation was sent.</p>}</Card></div>;
  return <div className="product-page"><PageHeading title="Settings" description="Organisation preferences and workspace controls." /><p className="mock-notice"><Badge tone="warning">Example settings</Badge> Organisation preferences and integrations are not backed by settings endpoints yet.</p><Card title="Review preferences"><form className="product-form" onSubmit={event => { event.preventDefault(); setSaved(true); }}><Select label="Default review channel" options={["General", "Website", "Email", "Press", "LinkedIn"].map(value => ({ value: value.toLowerCase(), label: value }))} /><Select label="Review mode" options={[{ value: "async", label: "Asynchronous" }, { value: "sync", label: "Synchronous local development" }]} /><label className="ds-check"><input type="checkbox" defaultChecked /> Email me when a review needs attention</label><Input label="Retention period (days)" type="number" defaultValue="365" /><Button variant="primary">Save example preferences</Button>{saved && <p role="status">Preview saved in this page only. No settings API was called.</p>}</form></Card></div>;
}

export function ProductPage({ page, id }: { page: Surface; id?: string }) {
  const params = useParams<{ id?: string }>();
  const contentId = id ?? params?.id;
  if (page === "dashboard") return <Dashboard />;
  if (page === "submissions") return <Submissions />;
  if (page === "submission" || page === "review") return contentId ? <ContentDetail id={contentId} review={page === "review"} /> : <p role="alert">A content ID is required.</p>;
  if (page === "knowledge") return <Knowledge />;
  if (page === "audit") return <AuditLog />;
  if (page === "notifications") return <Notifications />;
  return <AdminMock page={page} />;
}
