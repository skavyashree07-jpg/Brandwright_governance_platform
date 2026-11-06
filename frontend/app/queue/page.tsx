"use client";
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ClipboardCheck } from "lucide-react";
import { api, errText, isRisky, isUnverified, Comment, Content, ContentDetail, Finding } from "@/lib/api";
import { useSourceLabel } from "@/lib/kb";
import { Annotated } from "@/components/Annotated";
import { useUser } from "@/components/Shell";
import { downloadCsv } from "@/lib/csv";
import { Button, Input, Select } from "@/components/ui";

type Log = { id: string; action: string; details: string | null; created_at: string };

function ReviewDetail({ it, onChanged }: { it: Content; onChanged: () => void }) {
  const u = useUser();
  const label = useSourceLabel();
  const [d, setD] = useState<ContentDetail | null>(null);
  const [fs, setFs] = useState<Finding[]>([]);
  const [aiServices, setAiServices] = useState<string[]>([]);
  const [cms, setCms] = useState<Comment[]>([]);
  const [audit, setAudit] = useState<Log[] | null>(null);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [detailLoading, setDetailLoading] = useState(true);
  const [detailErrors, setDetailErrors] = useState<{ content?: string; findings?: string; comments?: string }>({});
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState("");
  const [text, setText] = useState("");
  const [target, setTarget] = useState<{ start: number; end: number; n: number } | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [approvalComment, setApprovalComment] = useState("");
  const [requestingChanges, setRequestingChanges] = useState(false);
  const [changesComment, setChangesComment] = useState("");
  const [reviewReady, setReviewReady] = useState(false);

  const load = useCallback(async () => {
    setDetailLoading(true);
    setDetailErrors({});
    const results = await Promise.allSettled([api.content(it.id), api.findings(it.id), api.comments(it.id)]);
    const errors: typeof detailErrors = {};
    if (results[0].status === "fulfilled") setD(results[0].value);
    else errors.content = errText(results[0].reason);
    if (results[1].status === "fulfilled") {
      setFs(results[1].value.findings);
      setAiServices(results[1].value.ai_services_used ?? []);
    } else errors.findings = errText(results[1].reason);
    if (results[2].status === "fulfilled") setCms(results[2].value);
    else errors.comments = errText(results[2].reason);
    setDetailErrors(errors);
    setDetailLoading(false);
  }, [it.id]);
  useEffect(() => { load(); }, [load]);

  const sorted = useMemo(() => [...fs].sort((a, b) => a.span.start - b.span.start), [fs]);
  const num = useMemo(() => Object.fromEntries(sorted.map((x, i) => [x.id, i + 1])) as Record<string, number>, [sorted]);
  const flagged = sorted.filter(x => isRisky(x) || x.decision?.action === "dismiss" || x.decision?.action === "edit");
  const rest = sorted.filter(x => !flagged.includes(x));
  const undecidedRisk = sorted.filter(x => isRisky(x) && !x.decision).length;
  // Mirrors the server rules so the button explains itself instead of failing with a 403/409.
  const needsNamed = fs.some(x => x.category === "claim" || isUnverified(x));
  const cantApprove = detailLoading || !!detailErrors.findings || (u.role === "manager" && needsNamed) || undecidedRisk > 0;

  const run = async (fn: () => Promise<unknown>, done?: () => void) => {
    setBusy(true); setErr("");
    try { await fn(); done?.(); } catch (e) { setErr(errText(e)); }
    setBusy(false);
  };
  const recheck = async () => {
    setBusy(true); setErr("");
    try {
      const initial = await api.runReview(it.id);
      if (initial.status === "queued" || initial.status === "running") {
        const deadline = Date.now() + 120_000;
        while (Date.now() < deadline) {
          const current = await api.reviewStatus(it.id);
          if (current.status === "completed" || current.status === "reviewed") break;
          if (current.status === "failed") throw new Error(current.review_error || "The review job failed.");
          await new Promise(resolve => setTimeout(resolve, 700));
        }
        if (Date.now() >= deadline) throw new Error("The review is taking longer than expected. Try again shortly.");
      }
      setReviewReady(true);
      await load();
    } catch (e) { setErr(errText(e)); }
    setBusy(false);
  };
  const decisionText = (x: Finding) =>
    x.decision?.action === "accept" ? "Accepted the suggested fix"
    : x.decision?.action === "dismiss" ? `Dismissed (recorded by the creator)`
    : x.decision?.action === "edit" ? "Edited text submitted by the creator" : "No decision yet";
  const comment = (x: Finding) => { setTarget({ start: x.span.start, end: x.span.end, n: num[x.id] }); document.getElementById(`cm-${it.id}`)?.focus(); };

  const card = (x: Finding) => (
    <article key={x.id} className={`f${isRisky(x) ? " high" : ""}`}>
      <span className={`tag ${isRisky(x) ? "hi" : "me"}`}>{isUnverified(x) ? "? Cannot verify" : x.severity === "high" ? "▲ High" : `◆ ${x.severity}`}</span>
      <strong>Issue {num[x.id]}</strong> <span className="mu">{x.category} · confidence {Math.round(x.confidence * 100)}%</span>
      {d && x.span.end > x.span.start && <blockquote className="q">“{d.body.slice(x.span.start, x.span.end)}”</blockquote>}
      <p style={{ margin: ".35rem 0" }}>{x.explanation}</p>
      <div className="mu"><strong>Matched source:</strong> {label(x.source) ?? "No support found."}</div>
      <div className="mu"><strong>Creator’s decision:</strong> {decisionText(x)}</div>
      <button className="btn quiet" onClick={() => comment(x)}>Comment on this passage</button>
    </article>
  );

  async function loadAudit() {
    setAuditLoading(true);
    setAuditError("");
    try { setAudit(await api.audit(it.id)); }
    catch (error) { setAuditError(errText(error)); }
    finally { setAuditLoading(false); }
  }

  if (!d) return detailLoading
    ? <p role="status">Loading the draft…</p>
    : <p className="err" role="alert">Draft details could not be loaded: {detailErrors.content ?? err ?? "Unexpected response."}</p>;
  return (
    <div>
      {detailErrors.content && <p className="err" role="alert">Could not refresh the draft details: {detailErrors.content} <button className="btn quiet" onClick={() => void load()}>Retry</button></p>}
      {detailErrors.findings && <p className="err" role="alert">Findings could not be loaded: {detailErrors.findings} <button className="btn quiet" onClick={() => void load()}>Retry</button></p>}
      <p className="mu"><strong>Intent:</strong> {d.intent} · <strong>Channel:</strong> {d.channel}</p>
      <p className="mu">AI services used: {aiServices.length ? aiServices.join(", ") : "none (deterministic checks only)"}</p>
      {it.status === "needs_recheck" && <div className="note">
        <p>A referenced fact changed. Re-run the engine against the current approved knowledge before resolving its alert.</p>
        <button className="btn" disabled={busy || reviewReady} onClick={recheck}>{reviewReady ? "Knowledge rechecked" : "Recheck latest facts"}</button>
      </div>}
      <Annotated body={d.body} findings={sorted} num={num} onPick={x => comment(x)} />
      <h3 style={{ marginTop: "1rem" }}>Needs your check ({flagged.length})</h3>
      {detailLoading && <p className="mu" role="status">Loading findings…</p>}
      {!detailLoading && !detailErrors.findings && flagged.length === 0 && rest.length === 0 && <p className="ok">No findings on this version.</p>}
      {!detailLoading && !detailErrors.findings && flagged.length === 0 && rest.length > 0 && <p className="ok">No high-risk or dismissed findings on this version.</p>}
      {flagged.map(card)}
      {!detailLoading && !detailErrors.findings && rest.length > 0 && <details><summary>Other findings ({rest.length})</summary>{rest.map(card)}</details>}

      <h3 style={{ marginTop: "1rem" }}>Comments ({cms.length})</h3>
      {detailLoading && <p className="mu" role="status">Loading comments…</p>}
      {detailErrors.comments && <p className="err" role="alert">Comments could not be loaded: {detailErrors.comments} <button className="btn quiet" onClick={() => void load()}>Retry</button></p>}
      {!detailLoading && !detailErrors.comments && cms.length === 0 && <p className="mu">No comments yet.</p>}
      {cms.map(c => (
        <p key={c.id} style={{ margin: ".3rem 0" }}>
          <span className="mu">{new Date(c.created_at).toLocaleString()}{c.span_end > c.span_start ? ` · on “${d.body.slice(c.span_start, c.span_end)}”` : ""}: </span>{c.body}
        </p>
      ))}
      <label htmlFor={`cm-${it.id}`}>{target ? `Comment on issue ${target.n}` : "Comment on the whole draft"}</label>
      <div className="row">
        <input id={`cm-${it.id}`} style={{ flex: 1 }} value={text} onChange={e => setText(e.target.value)} />
        <button className="btn" disabled={busy || !text.trim()} onClick={() => run(() => api.addComment(it.id, text.trim(), target?.start ?? 0, target?.end ?? 0), () => { setText(""); setTarget(null); load(); })}>Add comment</button>
        {target && <button className="btn quiet" onClick={() => setTarget(null)}>Comment on the whole draft instead</button>}
      </div>

      <div className="row" style={{ marginTop: ".9rem" }}>
        {confirm ? (
          <>
            <span role="alert"><strong>Approve version {it.current_version_no} and lock it?</strong> This is recorded and cannot be undone.</span>
              <label className="review-decision-comment">Required approval comment<textarea value={approvalComment} onChange={event => setApprovalComment(event.target.value)} /></label>
              <button className="btn pr" data-review-action="approve" disabled={busy || !approvalComment.trim()} onClick={() => run(async () => { await api.addComment(it.id, approvalComment.trim()); await api.approve(it.id); }, onChanged)}>Yes, approve and lock</button>
              <button className="btn" autoFocus onClick={() => { setConfirm(false); setApprovalComment(""); }}>Keep reviewing</button>
            </>
          ) : requestingChanges ? (
            <>
              <label className="review-decision-comment">Required change request comment<textarea value={changesComment} onChange={event => setChangesComment(event.target.value)} /></label>
              <button className="btn pr" disabled={busy || !changesComment.trim()} onClick={() => run(async () => { await api.addComment(it.id, changesComment.trim()); await api.requestChanges(it.id); }, onChanged)}>Send change request</button>
              <button className="btn" onClick={() => { setRequestingChanges(false); setChangesComment(""); }}>Cancel</button>
            </>
          ) : (
            <>
              <button className="btn pr" data-review-action="approve" disabled={busy || cantApprove} onClick={() => setConfirm(true)}>Approve and lock…</button>
              <button className="btn" data-review-action="request-changes" disabled={busy} onClick={() => setRequestingChanges(true)}>Request changes</button>
            </>
          )}
      </div>
      {u.role === "manager" && needsNamed && <p className="mu">This draft contains claims. A named Reviewer must approve it.</p>}
      {undecidedRisk > 0 && <p className="mu">{undecidedRisk} high-risk {undecidedRisk === 1 ? "finding has" : "findings have"} no decision from the creator. Request changes instead.</p>}
      {err && <p className="err" role="alert">{err}</p>}

      <details onToggle={e => {
        if ((e.target as HTMLDetailsElement).open && audit === null && !auditLoading) void loadAudit();
      }}>
        <summary>Audit trail</summary>
        {auditLoading && <p className="mu" role="status">Loading audit trail…</p>}
        {auditError && <p className="err" role="alert">Audit trail could not be loaded: {auditError} <button className="btn quiet" onClick={() => void loadAudit()}>Retry</button></p>}
        {audit?.length === 0 && <p className="mu">No entries yet.</p>}
        {(audit ?? []).map(a => <div key={a.id} className="mu">{new Date(a.created_at).toLocaleString()} · <strong>{a.action}</strong> {a.details}</div>)}
      </details>
    </div>
  );
}

export default function Queue() {
  const user = useUser();
  const [openId, setOpenId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [view, setView] = useState<"table" | "kanban">("table");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkComment, setBulkComment] = useState("");
  const [bulkError, setBulkError] = useState("");
  const [bulkMessage, setBulkMessage] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const [viewName, setViewName] = useState("");
  const [selectedView, setSelectedView] = useState("");
  const [savedViews, setSavedViews] = useState<{ name: string; query: string; status: string }[]>([]);
  const [visibleColumns, setVisibleColumns] = useState(["title", "status", "version"]);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);
  const [preferencesError, setPreferencesError] = useState("");
  const { data: items, error, isPending, refetch } = useQuery({
    queryKey: ["review-queue", user.organisation_id],
    queryFn: api.queue,
    refetchInterval: 30_000,
  });
  const err = error ? errText(error) : "";
  const preferencesKey = `bw_queue_preferences:${user.organisation_id}:${user.id}`;
  useEffect(() => {
    try {
      const saved = localStorage.getItem(preferencesKey);
      if (saved) {
        const parsed: unknown = JSON.parse(saved);
        if (typeof parsed !== "object" || parsed === null) throw new Error("Saved queue preferences have an invalid format.");
        const state = parsed as { views?: unknown; columns?: unknown };
        if (state.views !== undefined && (!Array.isArray(state.views) || state.views.some(item => !item || typeof item.name !== "string" || typeof item.query !== "string" || typeof item.status !== "string"))) throw new Error("Saved queue views have an invalid format.");
        if (state.columns !== undefined && (!Array.isArray(state.columns) || state.columns.some(column => !["title", "status", "version"].includes(String(column))))) throw new Error("Saved queue columns have an invalid format.");
        if (Array.isArray(state.views)) setSavedViews(state.views);
        if (Array.isArray(state.columns) && state.columns.length) setVisibleColumns(state.columns as string[]);
      }
    } catch (cause) { setPreferencesError(errText(cause)); }
    finally { setPreferencesLoaded(true); }
  }, [preferencesKey]);
  useEffect(() => {
    if (!preferencesLoaded) return;
    try { localStorage.setItem(preferencesKey, JSON.stringify({ views: savedViews, columns: visibleColumns })); }
    catch (cause) { setPreferencesError(errText(cause)); }
  }, [preferencesKey, preferencesLoaded, savedViews, visibleColumns]);
  const filtered = (items ?? [])
    .filter(item => `${item.title ?? ""} ${item.id}`.toLowerCase().includes(query.toLowerCase()))
    .filter(item => !statusFilter || item.status === statusFilter);
  const toggleSelected = (id: string) => setSelectedIds(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]);
  function saveView() {
    const name = viewName.trim();
    if (!name) return;
    setSavedViews(current => [...current.filter(view => view.name !== name), { name, query, status: statusFilter }]);
    setSelectedView(name); setViewName(""); setPreferencesError("");
  }
  function applyView(name: string) {
    setSelectedView(name);
    const saved = savedViews.find(view => view.name === name);
    if (saved) { setQuery(saved.query); setStatusFilter(saved.status); }
  }
  function toggleColumn(column: string) {
    setVisibleColumns(current => current.includes(column)
      ? current.length > 1 ? current.filter(item => item !== column) : current
      : [...current, column]);
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey || event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) return;
      if (!["j", "k", "a", "r"].includes(event.key.toLowerCase()) || !filtered.length) return;
      const currentIndex = filtered.findIndex(item => item.id === openId);
      if (event.key.toLowerCase() === "j" || event.key.toLowerCase() === "k") {
        event.preventDefault();
        const nextIndex = currentIndex < 0 ? 0 : (currentIndex + (event.key.toLowerCase() === "j" ? 1 : -1) + filtered.length) % filtered.length;
        setOpenId(filtered[nextIndex].id);
      } else if (openId) {
        const action = event.key.toLowerCase() === "a" ? "approve" : "request-changes";
        const button = document.querySelector<HTMLButtonElement>(`[data-review-action="${action}"]`);
        button?.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [filtered, openId]);

  async function requestChangesForSelected() {
    if (!bulkComment.trim()) return;
    setBulkBusy(true); setBulkError(""); setBulkMessage("");
    const failed: { id: string; error: string }[] = [];
    for (const id of selectedIds) {
      try {
        await api.addComment(id, bulkComment.trim());
        await api.requestChanges(id);
      } catch (cause) {
        failed.push({ id, error: errText(cause) });
      }
    }
    setBulkBusy(false);
    if (failed.length) {
      setBulkError(`Could not update ${failed.length} selected submission${failed.length === 1 ? "" : "s"}. ${failed[0].error}`);
    }
    setBulkMessage(`${selectedIds.length - failed.length} submission${selectedIds.length - failed.length === 1 ? "" : "s"} updated with your comment.`);
    setSelectedIds(failed.map(item => item.id));
    setBulkComment("");
    await refetch();
  }

  return (
    <section className="queue-page" aria-labelledby="qh">
      <div className="page-heading">
        <div>
          <div className="section-tag">REVIEW OPERATIONS</div>
          <h1 id="qh">Review queue</h1>
          <p className="mu">Check the evidence, discuss findings, and record a human decision.</p>
        </div>
        <span className="tag me">{isPending ? "Loading queue" : error ? "Queue unavailable" : `${items?.length ?? 0} waiting for review`}</span>
      </div>
      {err && <p className="err" role="alert">{err} <button className="btn quiet" onClick={() => void refetch()}>Retry</button></p>}
      {isPending && <div className="queue-loading" role="status" aria-label="Loading review queue"><span /><span /><span /></div>}
      {!isPending && items?.length === 0 && <div className="queue-empty"><ClipboardCheck size={25} aria-hidden="true" /><h2>Queue is clear</h2><p>New submissions will appear here when creators send them for review.</p></div>}
      {!!items?.length && <section className="queue-tools" aria-label="Queue filters and actions">
        <label>Search submissions<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Title or ID" /></label>
        <label>Status<select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="">All statuses</option><option value="in_review">In review</option><option value="needs_recheck">Needs recheck</option></select></label>
        <div className="queue-view-toggle" aria-label="Queue layout">
          <button type="button" aria-pressed={view === "table"} onClick={() => setView("table")}>Table</button>
          <button type="button" aria-pressed={view === "kanban"} onClick={() => setView("kanban")}>Kanban</button>
        </div>
        <Select label="Saved views" value={selectedView} onChange={event => applyView(event.target.value)} options={[{ value: "", label: "Choose a saved view" }, ...savedViews.map(saved => ({ value: saved.name, label: saved.name }))]} />
        <Input label="Name this view" value={viewName} onChange={event => setViewName(event.target.value)} placeholder="For example: Needs recheck" />
        <Button onClick={saveView} disabled={!viewName.trim()}>Save view</Button>
        <Button onClick={() => downloadCsv("brandwright-review-queue.csv", ["Title", "Status", "Version", "ID"], filtered.map(item => [item.title || "Untitled", item.status, String(item.current_version_no), item.id]))} disabled={!filtered.length}>Export CSV</Button>
        {selectedView && <Button variant="ghost" onClick={() => { setSavedViews(current => current.filter(saved => saved.name !== selectedView)); setSelectedView(""); }}>Delete view</Button>}
        <details className="queue-column-picker"><summary>Columns</summary><div role="group" aria-label="Visible queue columns">{[["title", "Title"], ["status", "Status"], ["version", "Version"]].map(([key, label]) => <label key={key}><input type="checkbox" checked={visibleColumns.includes(key)} onChange={() => toggleColumn(key)} />{label}</label>)}</div></details>
      </section>}
      {preferencesError && <p className="alert error" role="alert">Saved queue preferences error: {preferencesError}</p>}
      {!preferencesLoaded && <p className="mu" role="status">Loading saved queue views…</p>}
      {!!selectedIds.length && <section className="queue-bulk-actions" aria-label="Bulk request changes">
        <p>{selectedIds.length} selected. Bulk approval is unavailable; request changes with an audit comment.</p>
        <label>Required comment<input value={bulkComment} onChange={event => setBulkComment(event.target.value)} /></label>
        <button className="btn" disabled={bulkBusy || !bulkComment.trim()} onClick={() => void requestChangesForSelected()}>{bulkBusy ? "Updating…" : "Request changes for selected"}</button>
      </section>}
      {bulkError && <p className="err" role="alert">{bulkError}</p>}
      {bulkMessage && <p className="ok" role="status">{bulkMessage}</p>}
      {view === "kanban" ? <div className="queue-kanban">{["in_review", "needs_recheck"].map(status => <section key={status} className="queue-kanban-column"><h2>{status === "needs_recheck" ? "Needs recheck" : "In review"}</h2>{filtered.filter(item => item.status === status).map(it => <article key={it.id} className="queue-kanban-card"><label><input type="checkbox" checked={selectedIds.includes(it.id)} onChange={() => toggleSelected(it.id)} /> Select</label><strong>{it.title ?? "Untitled"}</strong><span>Version {it.current_version_no}</span><button className="btn" onClick={() => setOpenId(openId === it.id ? null : it.id)}>{openId === it.id ? "Close review" : "Open review"}</button>{openId === it.id && <ReviewDetail it={it} onChanged={() => { setOpenId(null); void refetch(); }} />}</article>)}</section>)}</div>
        : <div className="queue-table-wrap" role="region" aria-label="Review queue table" tabIndex={0}><table className="queue-table"><thead><tr><th scope="col"><span className="sr-only">Select</span></th>{visibleColumns.includes("title") && <th scope="col">Submission</th>}{visibleColumns.includes("status") && <th scope="col">Status</th>}{visibleColumns.includes("version") && <th scope="col">Version</th>}<th scope="col">Review</th></tr></thead><tbody>
          {filtered.map(it => <Fragment key={it.id}><tr>
            <td><input aria-label={`Select ${it.title ?? "Untitled"}`} type="checkbox" checked={selectedIds.includes(it.id)} onChange={() => toggleSelected(it.id)} /></td>
            {visibleColumns.includes("title") && <td><strong>{it.title ?? "Untitled"}</strong></td>}
            {visibleColumns.includes("status") && <td><span className={`tag ${it.status === "needs_recheck" ? "me" : "ok"}`}>{it.status === "needs_recheck" ? "Fact changed: recheck" : "In review"}</span></td>}
            {visibleColumns.includes("version") && <td>Version {it.current_version_no}</td>}
            <td><button className="btn queue-toggle" aria-expanded={openId === it.id} aria-controls={`rd-${it.id}`} onClick={() => setOpenId(openId === it.id ? null : it.id)}>{openId === it.id ? "Close review" : "Open for review"}<ChevronDown size={16} aria-hidden="true" /></button></td>
          </tr>{openId === it.id && <tr id={`rd-${it.id}`}><td colSpan={visibleColumns.filter(column => ["title", "status", "version"].includes(column)).length + 2}><div className="queue-detail"><ReviewDetail it={it} onChanged={() => { setOpenId(null); void refetch(); }} /></div></td></tr>}</Fragment>)}
        </tbody></table></div>}
      {!isPending && (items?.length ?? 0) > 0 && filtered.length === 0 && <div className="queue-empty"><h2>No matching submissions</h2><p>Try changing the search or status filter.</p></div>}
    </section>
  );
}
