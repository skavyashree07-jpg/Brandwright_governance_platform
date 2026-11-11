"use client";
import { useEffect, useMemo, useState } from "react";
import { api, errText, isRisky, isUnverified, Content, ContentDetail, Finding, ReviewProgressEvent } from "@/lib/api";
import { useSourceLabel } from "@/lib/kb";
import { Annotated } from "@/components/Annotated";
import { ReviewProgress } from "@/components/ReviewProgress";
import { Button, DiffViewer, Drawer, FileDropzone, Tooltip } from "@/components/ui";
import { useBrand, useUser } from "@/components/Shell";
import { FileCheck2 } from "lucide-react";

const CHANNELS = ["general", "LinkedIn", "Email", "Website", "Press"];

export default function Workspace() {
  const user = useUser();
  const { activeBrand, activeBrandId } = useBrand();
  const draftStorageKey = `bw_workspace_draft:${user.organisation_id}:${user.id}:${activeBrandId ?? "all"}`;
  const [f, setF] = useState({ title: "", intent: "", channel: "general", body: "" });
  const [draftRestored, setDraftRestored] = useState(false);
  const [draftSaveState, setDraftSaveState] = useState<"saved" | "saving" | "error">("saved");
  const [draftStorageError, setDraftStorageError] = useState("");
  const [upload, setUpload] = useState<File | null>(null);
  const [uploadWarnings, setUploadWarnings] = useState<string[]>([]);
  const [altText, setAltText] = useState("");
  const [c, setC] = useState<Content | null>(null);
  const [fs, setFs] = useState<Finding[]>([]);
  // The exact text + intent the findings belong to. Spans are character offsets into THIS text.
  const [reviewed, setReviewed] = useState<{ body: string; intent: string } | null>(null);
  const [engine, setEngine] = useState<"ok" | "degraded" | null>(null);
  const [aiServices, setAiServices] = useState<string[]>([]);
  const [reviewProgress, setReviewProgress] = useState<Pick<ReviewProgressEvent, "status" | "stage" | "message"> | null>(null);
  const [dis, setDis] = useState<string | null>(null); const [reason, setReason] = useState("");
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null);
  const [on, setOn] = useState<string | null>(null);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [msg, setMsg] = useState("");
  const [versionHistory, setVersionHistory] = useState<ContentDetail["versions"]>([]);
  const [versionError, setVersionError] = useState("");
  const [versionLoading, setVersionLoading] = useState(false);
  const [versionDrawerOpen, setVersionDrawerOpen] = useState(false);
  const [previewRewriteId, setPreviewRewriteId] = useState<string | null>(null);
  const label = useSourceLabel();
  const stale = !!reviewed && (f.body !== reviewed.body || f.intent !== reviewed.intent);
  const locked = !!c && !["draft", "changes_requested"].includes(c.status);
  const frozen = busy || locked || stale;

  useEffect(() => {
    setDraftRestored(false);
    setF({ title: "", intent: "", channel: "general", body: "" });
    setUpload(null);
    setUploadWarnings([]);
    setAltText("");
    setC(null);
    setFs([]);
    setReviewed(null);
    setEngine(null);
    setAiServices([]);
    setReviewProgress(null);
    setDis(null);
    setReason("");
    setEditing(null);
    setOn(null);
    setErr("");
    setMsg("");
    setVersionHistory([]);
    setVersionError("");
    setVersionDrawerOpen(false);
    setPreviewRewriteId(null);
  }, [draftStorageKey]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(draftStorageKey);
      if (saved) {
        const parsed: unknown = JSON.parse(saved);
        if (typeof parsed === "object" && parsed !== null && "title" in parsed && "intent" in parsed && "channel" in parsed && "body" in parsed) {
          const draft = parsed as { title: unknown; intent: unknown; channel: unknown; body: unknown };
          if ([draft.title, draft.intent, draft.channel, draft.body].every(value => typeof value === "string")) {
            setF({ title: draft.title as string, intent: draft.intent as string, channel: draft.channel as string, body: draft.body as string });
            setMsg("Restored your locally saved draft.");
          } else throw new Error("Saved draft fields are invalid.");
        } else throw new Error("Saved draft has an invalid format.");
      }
    } catch (error) {
      setDraftStorageError(errText(error));
    } finally {
      setDraftRestored(true);
    }
  }, [draftStorageKey]);

  useEffect(() => {
    if (!draftRestored || c || locked) return;
    setDraftSaveState("saving");
    const timer = window.setTimeout(() => {
      try {
        if (f.title || f.intent || f.body) localStorage.setItem(draftStorageKey, JSON.stringify(f));
        else localStorage.removeItem(draftStorageKey);
        setDraftSaveState("saved");
      } catch (error) {
        setDraftSaveState("error");
        setDraftStorageError(errText(error));
      }
    }, 500);
    return () => window.clearTimeout(timer);
  }, [c, draftRestored, draftStorageKey, f, locked]);

  useEffect(() => {
    if (!draftRestored || c || locked || !(f.title || f.intent || f.body)) return;
    const protectUnsaved = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", protectUnsaved);
    return () => window.removeEventListener("beforeunload", protectUnsaved);
  }, [c, draftRestored, f, locked]);

  useEffect(() => {
    if (!c?.id) { setVersionHistory([]); return; }
    let active = true;
    setVersionLoading(true);
    setVersionError("");
    api.content(c.id).then(detail => {
      if (active) setVersionHistory(detail.versions ?? []);
    }).catch(error => {
      if (active) setVersionError(errText(error));
    }).finally(() => {
      if (active) setVersionLoading(false);
    });
    return () => { active = false; };
  }, [c?.id, c?.current_version_no]);

  const sorted = useMemo(() => [...fs].sort((a, b) => a.span.start - b.span.start), [fs]);
  const num = useMemo(() => Object.fromEntries(sorted.map((x, i) => [x.id, i + 1])) as Record<string, number>, [sorted]);
  const open = sorted.filter(x => !x.decision);          // decisions come from the server, so they survive a re-run
  const handled = sorted.filter(x => !!x.decision);
  const blockers = open.filter(isRisky).length;

  async function waitForReview(jobId: string, intent: string, initialBody: string) {
    let body = initialBody;
    const terminal = await api.watchReview(jobId, event => {
      setReviewProgress({ status: event.status, stage: event.stage, message: event.message });
      if (typeof event.metadata?.extracted_text === "string") {
        body = event.metadata.extracted_text;
        setF(current => ({ ...current, body }));
        setReviewed({ body, intent });
      }
      if (event.metadata?.engine_status === "degraded") setEngine("degraded");
      if (event.metadata?.ai_services_used) setAiServices(event.metadata.ai_services_used);
      if (event.findings.length) {
        setFs(current => {
          const known = new Set(current.map(finding => finding.id));
          return [...current, ...event.findings.filter(finding => !known.has(finding.id))];
        });
      }
    });
    if (terminal.status === "failed") throw new Error(terminal.message || "The review could not be completed. Please retry.");
    setReviewProgress(null);
    return { event: terminal, body };
  }

  async function run(body: string) {
    setBusy(true); setErr(""); setMsg(""); setFs([]); setReviewProgress(null);
    try {
      if (upload) {
        let extracted = f.body;
        let initialReview;
        if (c) {
          initialReview = await api.runReview(c.id);
        } else {
          const uploaded = await api.uploadContent(upload, f.title, f.intent, f.channel, altText);
          setC(uploaded);
          setUploadWarnings(uploaded.extraction_warnings ?? []);
          extracted = uploaded.body;
          initialReview = uploaded;
        }
        let findings = initialReview.findings;
        if ((initialReview.status === "queued" || initialReview.status === "running") && initialReview.job_id) {
          const result = await waitForReview(initialReview.job_id, f.intent, extracted);
          extracted = result.body;
          findings = result.event.findings;
        } else if (initialReview.status === "failed") {
          throw new Error(initialReview.review_error || "The review could not be completed. Please retry.");
        } else {
          setFs(findings);
          setEngine(initialReview.engine_status === "degraded" ? "degraded" : "ok");
          setAiServices(initialReview.ai_services_used ?? []);
          setReviewed({ body: extracted, intent: f.intent });
        }
        setFs(current => {
          const merged = new Map(current.map(finding => [finding.id, finding]));
          for (const finding of findings) merged.set(finding.id, finding);
          return [...merged.values()];
        });
        setReviewed({ body: extracted, intent: f.intent });
        setF(current => ({ ...current, body: extracted }));
        setUpload(null);
        setUploadWarnings([]);
        setMsg(`Pre-check finished: ${findings.filter(x => !x.decision).length} open issues.`);
        setBusy(false);
        return;
      }
      const cur = c
        ? await api.saveVersion(c.id, body, f.intent, f.channel)
        : await api.createContent(f.title, body, f.intent, f.channel);
      setC(cur);                                           // set before reviewing, so a failed review can be retried
      try { localStorage.removeItem(draftStorageKey); }
      catch (storageError) { setDraftStorageError(errText(storageError)); }
      const initialReview = await api.runReview(cur.id);
      let findings = initialReview.findings;
      if ((initialReview.status === "queued" || initialReview.status === "running") && initialReview.job_id) {
        const result = await waitForReview(initialReview.job_id, f.intent, body);
        findings = result.event.findings;
      } else if (initialReview.status === "failed") {
        throw new Error("The review could not be completed. Please retry.");
      } else {
        setFs(findings);
        setEngine(initialReview.engine_status === "degraded" ? "degraded" : "ok");
        setAiServices(initialReview.ai_services_used ?? []);
      }
      setFs(current => {
        const merged = new Map(current.map(finding => [finding.id, finding]));
        for (const finding of findings) merged.set(finding.id, finding);
        return [...merged.values()];
      });
      setReviewed({ body, intent: f.intent });
      setMsg(`Pre-check finished: ${findings.filter(x => !x.decision).length} open issues.`);
    } catch (e) { setErr(errText(e)); }
    setBusy(false);
  }

  async function accept(x: Finding) {
    if (!x.suggestion || !reviewed) return;
    const b = reviewed.body;
    const body = inline(x)
      ? b.slice(0, x.span.start) + x.suggestion.text + b.slice(x.span.end)
      : x.suggestion.text;
    setBusy(true); setErr("");
    try { await api.decide(x.id, "accept"); }               // record first: never change the text without an audit record
    catch (e) { setErr(errText(e)); setBusy(false); return; }
    setF(p => ({ ...p, body }));
    await run(body);
  }

  async function dismiss(x: Finding) {
    const why = reason.trim(); if (!why) return;
    setBusy(true); setErr("");
    try {
      await api.decide(x.id, "dismiss", why);
      setFs(l => l.map(y => (y.id === x.id ? { ...y, decision: { action: "dismiss", reason: why } } : y)));
      setDis(null); setReason(""); setMsg(`Issue ${num[x.id]} dismissed. Your reason is recorded.`);
    } catch (e) { setErr(errText(e)); }
    setBusy(false);
  }

  async function saveEdit(x: Finding) {
    if (!editing || editing.id !== x.id || !reviewed || !editing.text.trim()) return;
    const body = inline(x)
      ? reviewed.body.slice(0, x.span.start) + editing.text + reviewed.body.slice(x.span.end)
      : editing.text;
    setBusy(true); setErr("");
    try { await api.decide(x.id, "edit", undefined, editing.text); }
    catch (e) { setErr(errText(e)); setBusy(false); return; }
    setEditing(null);
    setF(p => ({ ...p, body }));
    await run(body);
  }

  async function submit() {
    if (!c) return;
    setBusy(true); setErr("");
    try { setC(await api.submit(c.id)); setMsg("Submitted. A reviewer has your draft now."); } catch (e) { setErr(errText(e)); }
    setBusy(false);
  }

  const pick = (x: Finding) => { setOn(x.id); document.getElementById(`f-${x.id}`)?.focus(); };
  const inline = (x: Finding) => x.span.end > x.span.start;

  const card = (x: Finding, done: boolean) => {
    const src = label(x.source);
    const text = reviewed?.body.slice(x.span.start, x.span.end) ?? "";
    return (
      <article key={x.id} id={`f-${x.id}`} tabIndex={-1} aria-labelledby={`ft-${x.id}`} className={`f${isRisky(x) ? " high" : ""}${on === x.id ? " on" : ""}`}>
        <span className={`tag ${isRisky(x) ? "hi" : "me"}`}>{isUnverified(x) ? "? Cannot verify" : x.severity === "high" ? "▲ High" : `◆ ${x.severity}`}</span>
        <strong id={`ft-${x.id}`}>Issue {num[x.id]}</strong> <span className="mu">{x.category} · confidence {Math.round(x.confidence * 100)}%{inline(x) ? "" : " · whole draft"}</span>
        <p style={{ margin: ".35rem 0" }}>{x.explanation}</p>
        {isUnverified(x) && !done && <p className="note">Not a confirmed error. Nothing in your approved facts supports this claim, so a person will check it.</p>}
        <div className="mu"><strong>Source:</strong> {src ?? "No supporting source found. A person needs to check this."}</div>
        {x.suggestion && !done && (
          <div className="fix"><del>{text || "(insert)"}</del> <ins>{x.suggestion.text}</ins> {x.suggestion.intent_preserved !== false && <span className="ok">✓ Intent Lock passed</span>}
            <Button type="button" size="sm" aria-expanded={previewRewriteId === x.id} onClick={() => setPreviewRewriteId(current => current === x.id ? null : x.id)}>Preview rewrite</Button>
            {previewRewriteId === x.id && <DiffViewer before={text || "(insert)"} after={x.suggestion.text} />}
          </div>
        )}
        {!x.suggestion && !done && <div className="fix mu">No automatic fix. A reviewer will decide.</div>}
        {done && <p className="mu" style={{ margin: ".4rem 0 0" }}>{x.decision?.action === "accept" ? "Accepted: the fix was applied." : x.decision?.action === "edit" ? "Edited text was submitted and recorded." : "Dismissed: your reason was submitted and recorded."}</p>}
        {!done && !locked && (editing?.id === x.id ? (
          <div>
            <label htmlFor={`e-${x.id}`}>{inline(x) ? "Your replacement text" : "Edit the full draft"}</label>
            <textarea id={`e-${x.id}`} autoFocus value={editing.text} onChange={e => setEditing({ id: x.id, text: e.target.value })} />
            <div className="row" style={{ marginTop: ".5rem" }}>
              <button className="btn pr" disabled={frozen || !editing.text.trim()} onClick={() => saveEdit(x)}>Record edit and re-check</button>
              <button className="btn" disabled={busy} onClick={() => setEditing(null)}>Cancel</button>
            </div>
          </div>
        ) : dis === x.id ? (
          <div>
            <label htmlFor={`r-${x.id}`}>Why is this not an issue? (required)</label>
            <input id={`r-${x.id}`} autoFocus value={reason} onChange={e => setReason(e.target.value)} />
            <div className="row" style={{ marginTop: ".5rem" }}>
              <button className="btn pr" disabled={busy || !reason.trim()} onClick={() => dismiss(x)}>Confirm dismissal</button>
              <button className="btn" onClick={() => { setDis(null); document.getElementById(`f-${x.id}`)?.focus(); }}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="row" style={{ marginTop: ".5rem" }}>
            {x.suggestion && <button className="btn pr" disabled={frozen} onClick={() => accept(x)}>Accept fix</button>}
            <button className="btn" disabled={frozen} onClick={() => setEditing({ id: x.id, text: inline(x) ? text : reviewed?.body ?? "" })}>{inline(x) ? "Edit text" : "Edit full draft"}</button>
            <button className="btn" disabled={frozen} onClick={() => { setDis(x.id); setReason(""); }}>Dismiss with reason</button>
            {inline(x) && !stale && <button className="btn quiet" onClick={() => { setOn(x.id); document.getElementById(`m-${x.id}`)?.focus(); }}>Find in draft</button>}
          </div>
        ))}
      </article>
    );
  };

  return (
    <div className="workspace-page">
      <div className="page-heading workspace-heading">
        <div>
          <div className="section-tag">CREATOR WORKSPACE</div>
          <h1>Check a draft</h1>
          <p className="mu">{activeBrand ? `Reviewing for ${activeBrand.name}.` : "No single brand is active; this review will use organisation-wide shared guidance."}</p>
          <p className="mu">Compare your content with approved guidance before sending it for review.</p>
        </div>
        <div className="workspace-heading-actions">
          <div className="workspace-principle"><FileCheck2 size={18} aria-hidden="true" /><span>AI explains and suggests. People decide.</span></div>
          <Button type="button" onClick={() => window.print()} disabled={!reviewed}>Print review report</Button>
        </div>
      </div>
      <p className="workspace-save-state" role="status" aria-live="polite">
        {!draftRestored ? "Loading saved draft…" : draftSaveState === "saving" ? "Saving draft locally…" : draftSaveState === "error" ? "Draft could not be saved locally." : "Draft saved on this device."}
      </p>
      {draftStorageError && <p className="alert error" role="alert">Local draft storage issue: {draftStorageError}</p>}
      <div className="cols workspace-grid">
      <p role="status" className="sr-only">{msg}</p>
      <section className="pn" aria-labelledby="d">
        <h2 id="d">Your draft</h2>
        {!c && <button
          type="button"
          className="btn"
          disabled={busy}
          onClick={() => {
            setF({
              title: "Smart Review announcement",
              intent: "Introduce Smart Review and build confidence in its reliability.",
              channel: "general",
              body: "Introducing Smart Review, the absolute best compliance tool on the market. It is 100% unbreakable and guarantees zero errors. Over 10,000 companies trust us.",
            });
            setUpload(null);
            setFs([]);
            setReviewed(null);
            setReviewProgress(null);
            setErr("");
            setMsg("Example draft loaded. Review it before submitting.");
          }}
        >Load example</button>}
        {c && <p className="mu">Status: {c.status.replace("_", " ")} · version {c.current_version_no}</p>}
        <label htmlFor="t">Title</label><input id="t" value={f.title} disabled={!!c} onChange={e => setF({ ...f, title: e.target.value })} />
        <label htmlFor="i">Intent in one line (fixes may not change it) <Tooltip label="Suggestions that alter your stated intent are rejected."><span tabIndex={0} aria-label="Intent guidance">?</span></Tooltip></label><input id="i" value={f.intent} maxLength={300} disabled={locked} onChange={e => setF({ ...f, intent: e.target.value })} aria-describedby="intent-help" />
        <span id="intent-help" className="field-help">Suggestions must preserve this intent. You make the final content decision.</span>
        <label htmlFor="ch">Channel</label>
        <select id="ch" value={f.channel} disabled={!!c} onChange={e => setF({ ...f, channel: e.target.value })}>{CHANNELS.map(o => <option key={o}>{o}</option>)}</select>
        {!c && <FileDropzone label="Upload a document or image" accept=".txt,.md,.csv,.docx,.pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp" onFile={file => { setUpload(file); setUploadWarnings([]); }} />}
        {upload && <p className="mu">Selected: {upload.name}. Text is extracted for review; the original is stored in the organisation’s private file store.</p>}
        {uploadWarnings.map((warning, index) => <p key={`${index}-${warning}`} className="note" role="status">{warning}</p>)}
        {upload && <><label htmlFor="alt">Image alternative text (if applicable)</label><input id="alt" value={altText} disabled={!!c} onChange={e => setAltText(e.target.value)} /></>}
        <label htmlFor="b">Content</label><textarea id="b" value={f.body} disabled={locked} onChange={e => setF({ ...f, body: e.target.value })} />
        <div className="row" style={{ marginTop: ".7rem" }}>
          <button className="btn pr" disabled={busy || locked || !f.title || !f.intent || (!f.body && !upload)} onClick={() => run(f.body)}>{busy ? "Working…" : reviewed ? "Run pre-check again" : "Run pre-check"}</button>
          <button className="btn" disabled={!c || !reviewed || locked || stale || blockers > 0 || busy} onClick={submit}>Submit for review</button>
          {c && <Button type="button" onClick={() => setVersionDrawerOpen(true)}>Version history</Button>}
        </div>
        {!reviewed && <p className="mu">Run a pre-check before you submit.</p>}
        {stale && <p className="note" role="status">You changed the draft after the last check. Run the pre-check again before you accept fixes or submit.</p>}
        {!stale && blockers > 0 && <p className="mu">Submit unlocks once high-severity and unverified issues are fixed or dismissed with a reason.</p>}
        {locked && <p className="mu">This version is with a reviewer, so editing is locked.</p>}
        {engine === "degraded" && <p className="note" role="status">The AI review engine is offline. This pre-check used rule-based checks only, so judgement-based issues may be missing.</p>}
        {reviewed && <p className="mu">AI services used: {aiServices.length ? aiServices.join(", ") : "none (deterministic checks only)"}</p>}
        {err && <p className="err" role="alert">{err}</p>}
        {reviewed && !stale && (<><h3 style={{ marginTop: "1rem" }}>Annotated preview</h3><Annotated body={reviewed.body} findings={open} num={num} activeId={on} onPick={pick} /></>)}
      </section>

      <section className="pn findings-sidebar" aria-labelledby="fh">
        {reviewProgress && <ReviewProgress {...reviewProgress} findings={fs} />}
        <h2 id="fh">Findings ({open.length} open)</h2>
        {!fs.length && !reviewed && <p className="mu">Run a pre-check to see issues with their source and a suggested fix.</p>}
        {reviewed && !open.length && (fs.length === 0
          ? <p className="ok"><strong>No findings from this pre-check.</strong></p>
          : <p className="ok"><strong>✓ No open issues.</strong> Every finding has a decision.</p>)}
        {open.map(x => card(x, false))}
        {handled.length > 0 && <details><summary>Decided ({handled.length})</summary>{handled.map(x => card(x, true))}</details>}
        <p className="mu">AI never edits your text. Every accept, edit, and dismissal is your action and is recorded.</p>
      </section>
      </div>
      <Drawer open={versionDrawerOpen} onClose={() => setVersionDrawerOpen(false)} title="Version history">
        {versionLoading && <p role="status">Loading versions…</p>}
        {versionError && <p className="err" role="alert">Version history could not be loaded: {versionError}</p>}
        {!versionLoading && !versionError && !versionHistory.length && <p className="mu">No saved versions are available.</p>}
        {[...versionHistory].sort((a, b) => a.version_no - b.version_no).map((version, index, versions) => {
          const next = versions[index + 1];
          return <section className="version-item" key={version.version_no}>
            <h3>Version {version.version_no}{next ? ` compared with version ${next.version_no}` : ""}</h3>
            <DiffViewer before={version.body} after={next?.body ?? version.body} />
          </section>;
        })}
      </Drawer>
      {reviewed && <section className="print-report" aria-label="Printable review report">
        <h1>Brandwright review report</h1>
        <p><strong>Content:</strong> {c?.title || f.title || "Untitled"} | <strong>Version:</strong> {c?.current_version_no ?? 1}</p>
        <p><strong>Intent:</strong> {reviewed.intent}</p>
        <p><strong>Generated:</strong> {new Date().toLocaleString()}</p>
        <h2>Reviewed content</h2><div className="print-content">{reviewed.body}</div>
        <h2>Findings</h2>
        {sorted.length ? sorted.map((finding, index) => <article key={finding.id}><h3>{index + 1}. {finding.severity.toUpperCase()} {finding.category}</h3><p>{finding.explanation}</p><p><strong>Source:</strong> {label(finding.source) ?? "Cannot verify against an approved source."}</p>{finding.suggestion && <p><strong>Suggestion:</strong> {finding.suggestion.text}</p>}</article>) : <p>No findings.</p>}
      </section>}
    </div>
  );
}
