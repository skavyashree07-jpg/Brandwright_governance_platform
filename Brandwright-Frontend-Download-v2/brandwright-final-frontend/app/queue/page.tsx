"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, errText, isRisky, isUnverified, Comment, Content, ContentDetail, Finding } from "@/lib/api";
import { useSourceLabel } from "@/lib/kb";
import { Annotated } from "@/components/Annotated";
import { useUser } from "@/components/Shell";

type Log = { id: string; action: string; details: string | null; created_at: string };

function ReviewDetail({ it, onChanged }: { it: Content; onChanged: () => void }) {
  const u = useUser();
  const label = useSourceLabel();
  const [d, setD] = useState<ContentDetail | null>(null);
  const [fs, setFs] = useState<Finding[]>([]);
  const [cms, setCms] = useState<Comment[]>([]);
  const [audit, setAudit] = useState<Log[] | null>(null);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [target, setTarget] = useState<{ start: number; end: number; n: number } | null>(null);
  const [confirm, setConfirm] = useState(false);

  const load = useCallback(async () => {
    try {
      const [a, b, c] = await Promise.all([api.content(it.id), api.findings(it.id), api.comments(it.id)]);
      setD(a); setFs(b.findings); setCms(c);
    } catch (e) { setErr(errText(e)); }
  }, [it.id]);
  useEffect(() => { load(); }, [load]);

  const sorted = useMemo(() => [...fs].sort((a, b) => a.span.start - b.span.start), [fs]);
  const num = useMemo(() => Object.fromEntries(sorted.map((x, i) => [x.id, i + 1])) as Record<string, number>, [sorted]);
  const flagged = sorted.filter(x => isRisky(x) || x.decision === "dismiss" || x.decision === "override");
  const rest = sorted.filter(x => !flagged.includes(x));
  const undecidedRisk = sorted.filter(x => isRisky(x) && !x.decision).length;
  // Mirrors the server rules so the button explains itself instead of failing with a 403/409.
  const needsNamed = fs.some(x => x.category === "claim" || isUnverified(x));
  const cantApprove = (u.role === "manager" && needsNamed) || undecidedRisk > 0;

  const run = async (fn: () => Promise<unknown>, done?: () => void) => {
    setBusy(true); setErr("");
    try { await fn(); done?.(); } catch (e) { setErr(errText(e)); }
    setBusy(false);
  };
  const decisionText = (x: Finding) =>
    x.decision === "accept" ? "Accepted the suggested fix"
    : x.decision === "dismiss" ? `Dismissed (recorded by the creator)`
    : x.decision === "override" ? "Overrode the finding" : "No decision yet";
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

  if (!d) return err ? <p className="err" role="alert">{err}</p> : <p role="status">Loading the draft…</p>;
  return (
    <div>
      <p className="mu"><strong>Intent:</strong> {d.intent} · <strong>Channel:</strong> {d.channel}</p>
      <Annotated body={d.body} findings={sorted} num={num} onPick={x => comment(x)} />
      <h3 style={{ marginTop: "1rem" }}>Needs your check ({flagged.length})</h3>
      {flagged.length === 0 && <p className="ok">No high-risk or dismissed findings on this version.</p>}
      {flagged.map(card)}
      {rest.length > 0 && <details><summary>Other findings ({rest.length})</summary>{rest.map(card)}</details>}

      <h3 style={{ marginTop: "1rem" }}>Comments ({cms.length})</h3>
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
            <button className="btn pr" disabled={busy} onClick={() => run(() => api.approve(it.id), onChanged)}>Yes, approve and lock</button>
            <button className="btn" autoFocus onClick={() => setConfirm(false)}>Keep reviewing</button>
          </>
        ) : (
          <>
            <button className="btn pr" disabled={busy || cantApprove} onClick={() => setConfirm(true)}>Approve and lock…</button>
            <button className="btn" disabled={busy} onClick={() => run(() => api.requestChanges(it.id), onChanged)}>Request changes</button>
          </>
        )}
      </div>
      {u.role === "manager" && needsNamed && <p className="mu">This draft contains claims. A named Reviewer must approve it.</p>}
      {undecidedRisk > 0 && <p className="mu">{undecidedRisk} high-risk {undecidedRisk === 1 ? "finding has" : "findings have"} no decision from the creator. Request changes instead.</p>}
      {err && <p className="err" role="alert">{err}</p>}

      <details onToggle={e => { if ((e.target as HTMLDetailsElement).open) api.audit(it.id).then(setAudit).catch(() => setAudit([])); }}>
        <summary>Audit trail</summary>
        {audit === null && <p className="mu">Loading…</p>}
        {audit?.length === 0 && <p className="mu">No entries yet.</p>}
        {(audit ?? []).map(a => <div key={a.id} className="mu">{new Date(a.created_at).toLocaleString()} · <strong>{a.action}</strong> {a.details}</div>)}
      </details>
    </div>
  );
}

export default function Queue() {
  const [items, setItems] = useState<Content[] | null>(null);
  const [err, setErr] = useState(""); const [openId, setOpenId] = useState<string | null>(null);
  const load = useCallback(() => api.queue().then(setItems).catch(e => setErr(errText(e))), []);
  useEffect(() => { load(); }, [load]);
  return (
    <section className="pn" aria-labelledby="qh">
      <h2 id="qh">Review queue</h2>
      <p className="mu">Items waiting for a human decision. Open one to see the draft, the flagged claims with their sources, and what the creator decided.</p>
      {err && <p className="err" role="alert">{err}</p>}
      {items === null && !err && <p role="status">Loading…</p>}
      {items?.length === 0 && <p>Nothing is waiting. New submissions appear here.</p>}
      {items?.map(it => (
        <article key={it.id} className="f" aria-labelledby={`qt-${it.id}`}>
          <h3 id={`qt-${it.id}`}>{it.title ?? "Untitled"}</h3>
          <p className="mu">Version {it.current_version_no} · <span className="tag me">{it.status === "needs_recheck" ? "◆ Fact changed: recheck" : "In review"}</span></p>
          <button className="btn" aria-expanded={openId === it.id} aria-controls={`rd-${it.id}`} onClick={() => setOpenId(openId === it.id ? null : it.id)}>{openId === it.id ? "Close review" : "Open for review"}</button>
          {openId === it.id && <div id={`rd-${it.id}`} style={{ marginTop: ".8rem" }}><ReviewDetail it={it} onChanged={() => { setOpenId(null); load(); }} /></div>}
        </article>
      ))}
    </section>
  );
}
