"use client";
import { useMemo, useState } from "react";
import { api, errText, isRisky, isUnverified, Content, Finding } from "@/lib/api";
import { useSourceLabel } from "@/lib/kb";
import { Annotated } from "@/components/Annotated";

const CHANNELS = ["general", "LinkedIn", "Email", "Website", "Press"];

export default function Workspace() {
  const [f, setF] = useState({ title: "", intent: "", channel: "general", body: "" });
  const [c, setC] = useState<Content | null>(null);
  const [fs, setFs] = useState<Finding[]>([]);
  // The exact text + intent the findings belong to. Spans are character offsets into THIS text.
  const [reviewed, setReviewed] = useState<{ body: string; intent: string } | null>(null);
  const [engine, setEngine] = useState<"ok" | "degraded" | null>(null);
  const [dis, setDis] = useState<string | null>(null); const [reason, setReason] = useState("");
  const [on, setOn] = useState<string | null>(null);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [msg, setMsg] = useState("");
  const label = useSourceLabel();

  const stale = !!reviewed && (f.body !== reviewed.body || f.intent !== reviewed.intent);
  const locked = !!c && !["draft", "changes_requested"].includes(c.status);
  const frozen = busy || locked || stale;

  const sorted = useMemo(() => [...fs].sort((a, b) => a.span.start - b.span.start), [fs]);
  const num = useMemo(() => Object.fromEntries(sorted.map((x, i) => [x.id, i + 1])) as Record<string, number>, [sorted]);
  const open = sorted.filter(x => !x.decision);          // decisions come from the server, so they survive a re-run
  const handled = sorted.filter(x => !!x.decision);
  const blockers = open.filter(isRisky).length;

  async function run(body: string) {
    setBusy(true); setErr(""); setMsg("");
    try {
      const cur = c ? await api.saveVersion(c.id, body, f.intent) : await api.createContent(f.title, body, f.intent, f.channel);
      setC(cur);                                           // set before reviewing, so a failed review can be retried
      const r = await api.runReview(cur.id);
      setFs(r.findings); setEngine(r.engine_status); setReviewed({ body, intent: f.intent });
      setMsg(`Pre-check finished: ${r.findings.filter(x => !x.decision).length} open issues.`);
    } catch (e) { setErr(errText(e)); }
    setBusy(false);
  }

  async function accept(x: Finding) {
    if (!x.suggestion || !reviewed) return;
    const b = reviewed.body;
    const body = b.slice(0, x.span.start) + x.suggestion.text + b.slice(x.span.end);
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
      setFs(l => l.map(y => (y.id === x.id ? { ...y, decision: "dismiss" } : y)));
      setDis(null); setReason(""); setMsg(`Issue ${num[x.id]} dismissed. Your reason is recorded.`);
    } catch (e) { setErr(errText(e)); }
    setBusy(false);
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
          <div className="fix"><del>{text || "(insert)"}</del> <ins>{x.suggestion.text}</ins> {x.suggestion.intent_preserved !== false && <span className="ok">✓ Intent Lock passed</span>}</div>
        )}
        {!x.suggestion && !done && <div className="fix mu">No automatic fix. A reviewer will decide.</div>}
        {done && <p className="mu" style={{ margin: ".4rem 0 0" }}>{x.decision === "accept" ? "Accepted: the fix was applied." : "Dismissed: your reason was submitted and recorded."}</p>}
        {!done && !locked && (dis === x.id ? (
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
            <button className="btn" disabled={frozen} onClick={() => { setDis(x.id); setReason(""); }}>Dismiss with reason</button>
            {inline(x) && !stale && <button className="btn quiet" onClick={() => { setOn(x.id); document.getElementById(`m-${x.id}`)?.focus(); }}>Find in draft</button>}
          </div>
        ))}
      </article>
    );
  };

  return (
    <div className="cols">
      <p role="status" className="sr-only">{msg}</p>
      <section className="pn" aria-labelledby="d">
        <h2 id="d">Your draft</h2>
        {c && <p className="mu">Status: {c.status.replace("_", " ")} · version {c.current_version_no}</p>}
        <label htmlFor="t">Title</label><input id="t" value={f.title} disabled={!!c} onChange={e => setF({ ...f, title: e.target.value })} />
        <label htmlFor="i">Intent in one line (fixes may not change it)</label><input id="i" value={f.intent} maxLength={300} disabled={locked} onChange={e => setF({ ...f, intent: e.target.value })} />
        <label htmlFor="ch">Channel</label>
        <select id="ch" value={f.channel} disabled={!!c} onChange={e => setF({ ...f, channel: e.target.value })}>{CHANNELS.map(o => <option key={o}>{o}</option>)}</select>
        <label htmlFor="b">Content</label><textarea id="b" value={f.body} disabled={locked} onChange={e => setF({ ...f, body: e.target.value })} />
        <div className="row" style={{ marginTop: ".7rem" }}>
          <button className="btn pr" disabled={busy || locked || !f.title || !f.intent || !f.body} onClick={() => run(f.body)}>{busy ? "Working…" : reviewed ? "Run pre-check again" : "Run pre-check"}</button>
          <button className="btn" disabled={!c || !reviewed || locked || stale || blockers > 0 || busy} onClick={submit}>Submit for review</button>
        </div>
        {!reviewed && <p className="mu">Run a pre-check before you submit.</p>}
        {stale && <p className="note" role="status">You changed the draft after the last check. Run the pre-check again before you accept fixes or submit.</p>}
        {!stale && blockers > 0 && <p className="mu">Submit unlocks once high-severity and unverified issues are fixed or dismissed with a reason.</p>}
        {locked && <p className="mu">This version is with a reviewer, so editing is locked.</p>}
        {engine === "degraded" && <p className="note" role="status">The AI review engine is offline. This pre-check used rule-based checks only, so judgement-based issues may be missing.</p>}
        {err && <p className="err" role="alert">{err}</p>}
        {reviewed && !stale && (<><h3 style={{ marginTop: "1rem" }}>Annotated preview</h3><Annotated body={reviewed.body} findings={open} num={num} activeId={on} onPick={pick} /></>)}
      </section>

      <section className="pn" aria-labelledby="fh">
        <h2 id="fh">Findings ({open.length} open)</h2>
        {!fs.length && !reviewed && <p className="mu">Run a pre-check to see issues with their source and a suggested fix.</p>}
        {reviewed && !open.length && <p className="ok"><strong>✓ No open issues.</strong> Every finding has a decision.</p>}
        {open.map(x => card(x, false))}
        {handled.length > 0 && <details><summary>Decided ({handled.length})</summary>{handled.map(x => card(x, true))}</details>}
        <p className="mu">AI never edits your text. Every accept and dismiss is your click, and each one is recorded.</p>
      </section>
    </div>
  );
}
