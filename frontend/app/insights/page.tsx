"use client";
import { ChangeEvent, FormEvent, useCallback, useEffect, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useUser } from "@/components/Shell";
import { z } from "zod";
import {
  api, errText, Asset, Fact, FactDriftAlert, GuidelineHealth, Overview, Rule, Term,
  TrustScorecard,
} from "@/lib/api";

const pct = (value: unknown) =>
  typeof value === "number" ? `${Math.round(value <= 1 ? value * 100 : value)}%` : "Not available";
const trustRunSchema = z.object({
  precision: z.number().min(0).max(100),
  recall: z.number().min(0).max(100),
  created_at: z.string().min(1),
}).passthrough();
type InsightKey = "health" | "drift" | "overview" | "rules" | "facts" | "terms" | "assets";

export default function Insights() {
  const user = useUser();
  const [health, setHealth] = useState<GuidelineHealth[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [drift, setDrift] = useState<FactDriftAlert[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [clarifications, setClarifications] = useState<Record<string, { id: string; drafted_text: string }>>({});
  const [errors, setErrors] = useState<string[]>([]);
  const [trustError, setTrustError] = useState("");
  const [message, setMessage] = useState("");
  const [trustRunning, setTrustRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [guidelineFile, setGuidelineFile] = useState<File | null>(null);
  const [factText, setFactText] = useState("");
  const [factOwner, setFactOwner] = useState("");
  const [termBanned, setTermBanned] = useState("");
  const [termPreferred, setTermPreferred] = useState("");
  const [assetFile, setAssetFile] = useState<File | null>(null);
  const [assetName, setAssetName] = useState("");
  const [savedTrustRun, setSavedTrustRun] = useState<TrustScorecard | null>(null);

  const { data: snapshot, isPending: loading, refetch } = useQuery({
    queryKey: ["governance-insights", user.organisation_id],
    queryFn: async () => {
      const results = await Promise.allSettled([
        api.health(), api.drift(), api.overview(), api.rules(),
        api.facts(), api.terms(), api.assets(),
      ]);
      const keys: InsightKey[] = ["health", "drift", "overview", "rules", "facts", "terms", "assets"];
      const failures: Partial<Record<InsightKey, string>> = {};
      results.forEach((result, index) => {
        if (result.status === "rejected") failures[keys[index]] = errText(result.reason);
      });
      return {
        health: results[0].status === "fulfilled" ? results[0].value : undefined,
        drift: results[1].status === "fulfilled" ? results[1].value : undefined,
        overview: results[2].status === "fulfilled" ? results[2].value : undefined,
        rules: results[3].status === "fulfilled" ? results[3].value : undefined,
        facts: results[4].status === "fulfilled" ? results[4].value : undefined,
        terms: results[5].status === "fulfilled" ? results[5].value : undefined,
        assets: results[6].status === "fulfilled" ? results[6].value : undefined,
        failures,
      };
    },
  });

  useEffect(() => {
    if (!snapshot) return;
    if (snapshot.health) setHealth(snapshot.health);
    if (snapshot.drift) setDrift(snapshot.drift);
    if (snapshot.overview) setOverview(snapshot.overview);
    if (snapshot.rules) setRules(snapshot.rules);
    if (snapshot.facts) setFacts(snapshot.facts);
    if (snapshot.terms) setTerms(snapshot.terms);
    if (snapshot.assets) setAssets(snapshot.assets);
  }, [snapshot]);

  useEffect(() => {
    const key = `bw_trust_run:${user.organisation_id}`;
    const stored = sessionStorage.getItem(key);
    if (!stored) {
      setSavedTrustRun(null);
      return;
    }
    try {
      const parsed = trustRunSchema.safeParse(JSON.parse(stored));
      if (parsed.success) setSavedTrustRun(parsed.data);
      else {
        sessionStorage.removeItem(key);
        setTrustError("The saved evaluation result was invalid. Run the evaluation again.");
      }
    } catch {
      sessionStorage.removeItem(key);
      setTrustError("The saved evaluation result could not be read. Run the evaluation again.");
    }
  }, [user.organisation_id]);

  const refresh = useCallback(async () => {
    await refetch();
  }, [refetch]);

  async function act(work: () => Promise<unknown>, success: string, reload = true) {
    setBusy(true);
    setErrors([]);
    setMessage("");
    try {
      await work();
      setMessage(success);
      if (reload) await refresh();
    } catch (error) {
      setErrors([errText(error)]);
    } finally {
      setBusy(false);
    }
  }

  async function uploadGuideline(event: FormEvent) {
    event.preventDefault();
    if (!guidelineFile) return;
    await act(async () => {
      const uploaded = await api.uploadGuideline(guidelineFile);
      setMessage(`Guideline uploaded. ${uploaded.rules.length} extracted rule drafts need human approval.`);
      setGuidelineFile(null);
      await refresh();
    }, "Guideline processed. Review the extracted draft rules below.", false);
  }

  async function addFact(event: FormEvent) {
    event.preventDefault();
    await act(() => api.createFact({ text: factText, owner: factOwner || undefined }), "Fact added.");
    setFactText("");
    setFactOwner("");
  }

  async function addTerm(event: FormEvent) {
    event.preventDefault();
    await act(() => api.createTerm({ banned: termBanned, preferred: termPreferred }), "Terminology added.");
    setTermBanned("");
    setTermPreferred("");
  }

  async function addAsset(event: FormEvent) {
    event.preventDefault();
    if (!assetFile) return;
    await act(() => api.uploadAsset(assetFile, assetName || assetFile.name), "Asset uploaded.");
    setAssetFile(null);
    setAssetName("");
  }

  async function runTrust() {
    setTrustRunning(true);
    setTrustError("");
    setMessage("");
    try {
      const response = await api.runTrust();
      const parsed = trustRunSchema.safeParse(response);
      if (!parsed.success) {
        throw new Error("The evaluation returned incomplete metrics. Run it again or contact an administrator.");
      }
      sessionStorage.setItem(`bw_trust_run:${user.organisation_id}`, JSON.stringify(parsed.data));
      setSavedTrustRun(parsed.data);
      setMessage("Evaluation run completed against the labelled dataset.");
    } catch (error) {
      setTrustError(errText(error));
    } finally {
      setTrustRunning(false);
    }
  }

  function chooseFile(setter: (file: File | null) => void) {
    return (event: ChangeEvent<HTMLInputElement>) => setter(event.target.files?.[0] ?? null);
  }

  const scoreData = savedTrustRun;
  const failed = (key: InsightKey) => snapshot?.failures[key];
  const metrics: [string, number | string][] = [
    ["Reviews run", overview?.reviews_run ?? "Unavailable"],
    ["Unsupported claims flagged", overview?.unsupported_claims_flagged ?? "Unavailable"],
    ["Facts expiring in 30 days", overview?.facts_expiring_30d ?? "Unavailable"],
    ["AI usage records", overview?.ai_usage_log_entries ?? "Unavailable"],
  ];
  const scoreChartData = scoreData
    && typeof scoreData.precision === "number"
    && typeof scoreData.recall === "number"
    ? [
      { metric: "Precision", score: Math.round(scoreData.precision <= 1 ? scoreData.precision * 100 : scoreData.precision) },
      { metric: "Recall", score: Math.round(scoreData.recall <= 1 ? scoreData.recall * 100 : scoreData.recall) },
    ]
    : [];

  return <div className="insights-page">
    <div className="page-heading">
      <div>
        <div className="section-tag">ORGANISATION GOVERNANCE</div>
        <h1>Governance insights</h1>
        <p className="mu">Manage approved sources and review governance signals.</p>
      </div>
      <span className="tag me">Live API data</span>
    </div>

    <Tabs.Root defaultValue="governance" className="insights-tabs">
      <Tabs.List className="insights-tabs-list" aria-label="Governance sections">
        <Tabs.Trigger className="insights-tab" value="governance">Governance</Tabs.Trigger>
        <Tabs.Trigger className="insights-tab" value="knowledge">Knowledge base</Tabs.Trigger>
      </Tabs.List>

      <Tabs.Content className="insights-panel" value="governance">
        <div className="metric-grid">
          {metrics.map(([label, value]) => <div className="metric-card" key={label}><span>{label}</span><strong>{loading ? "Loading" : failed("overview") ? "Unavailable" : value}</strong></div>)}
        </div>
        {failed("overview") && <p className="alert error" role="alert">Overview data could not be loaded: {failed("overview")} <button className="btn" onClick={() => void refresh()}>Retry</button></p>}
        <div className="cols">
          <section className="pn">
            <h2>Guideline health</h2>
            <p className="mu">Dismissals and edits are signals for owners, not automatic rule changes.</p>
            {loading && <div className="data-skeleton" role="status">Loading guideline health…</div>}
            {!loading && failed("health") && <p className="alert error" role="alert">Guideline health could not be loaded: {failed("health")} <button className="btn" onClick={() => void refresh()}>Retry</button></p>}
            {!loading && !failed("health") && !health.length && <p className="empty-state">No guideline health data yet. Decision patterns appear after findings are reviewed.</p>}
            {!loading && !failed("health") && !!health.length && <div className="table-wrap guideline-health-wrap"><table className="guideline-health-table"><thead><tr><th scope="col">Rule</th><th scope="col">Decisions</th><th scope="col">Dismissed</th><th scope="col">Status</th><th scope="col">Action</th></tr></thead><tbody>
              {[...health].sort((a, b) => b.dismiss_rate - a.dismiss_rate).map(rule => <tr key={rule.rule_id}>
                <td data-label="Rule" className="health-rule-cell"><strong>{rule.clause_number}</strong><details className="rule-text-expander"><summary><span className="rule-text-preview">{rule.text}</span><span className="rule-text-prompt">Show full rule</span></summary><p>{rule.text}</p></details></td>
                <td data-label="Decisions" className="health-number-cell">{rule.total_decisions}</td>
                <td data-label="Dismissed" className="health-number-cell">{pct(rule.dismiss_rate)}</td>
                <td data-label="Status" className="health-status-cell"><span className={`tag ${rule.status === "unclear" ? "me" : "ok"}`}>{rule.status === "unclear" ? "Needs review" : "Healthy"}</span></td>
                <td data-label="Action" className="health-action-cell"><button className="btn" disabled={busy} onClick={() => void act(async () => {
                  const draft = await api.draftClarification(rule.rule_id);
                  setClarifications(value => ({ ...value, [rule.rule_id]: draft }));
                }, "Clarification draft created.", false)}>Draft clarification</button>
                  {clarifications[rule.rule_id] && <div className="fix">
                    <p>{clarifications[rule.rule_id].drafted_text}</p>
                    <p className="mu">This proposal does not change the active rule until approved.</p>
                    <button className="btn pr" disabled={busy} onClick={() => void act(
                      () => api.updateClarification(clarifications[rule.rule_id].id, "approved"),
                      "Clarification approved and applied to the rule.",
                    )}>Approve draft</button>
                    <button className="btn" disabled={busy} onClick={() => void act(
                      () => api.updateClarification(clarifications[rule.rule_id].id, "rejected"),
                      "Clarification rejected.",
                    )}>Reject draft</button>
                  </div>}
                </td>
              </tr>)}
            </tbody></table></div>}
          </section>
          <section className="pn">
            <h2>Trust scorecard</h2>
            <button className="btn pr" disabled={busy || trustRunning} onClick={() => void runTrust()}>{trustRunning ? "Running evaluation…" : "Run labelled evaluation"}</button>
            {trustRunning && <p className="data-skeleton" role="status">Running the labelled evaluation. Results will appear here when it finishes.</p>}
            {trustError && <p className="alert error" role="alert">{trustError}</p>}
            {scoreData ? <>
              <div className="score-row"><div><span>Precision</span><strong>{pct(scoreData.precision)}</strong></div><div><span>Recall</span><strong>{pct(scoreData.recall)}</strong></div></div>
              <p className="mu">Last run: {scoreData.created_at && Number.isFinite(Date.parse(scoreData.created_at)) ? new Date(scoreData.created_at).toLocaleString() : "Timestamp unavailable"}{typeof scoreData.sample_count === "number" ? ` · ${scoreData.sample_count} labelled samples` : ""}</p>
              {scoreData.precision === 0 && scoreData.recall === 0 && <p className="mu">Zero is a measured result for this run, not missing data. Review the labelled samples before interpreting it.</p>}
              {scoreChartData.length > 0 && <div className="score-chart" role="img" aria-label={`Trust scorecard: precision ${pct(scoreData.precision)}, recall ${pct(scoreData.recall)}`}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={scoreChartData} layout="vertical" margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
                    <CartesianGrid stroke="#e6ebe2" horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} tick={{ fill: "#647184", fontSize: 10 }} tickLine={false} axisLine={false} />
                    <YAxis type="category" dataKey="metric" width={76} tick={{ fill: "#435246", fontSize: 10 }} tickLine={false} axisLine={false} />
                    <Tooltip formatter={(value) => [`${value}%`, "Score"]} />
                    <Bar dataKey="score" fill="#cfe65b" radius={[0, 4, 4, 0]} maxBarSize={24} />
                  </BarChart>
                </ResponsiveContainer>
              </div>}
            </> : !trustRunning && <div className="empty-state"><strong>No evaluation run yet</strong><p>Run the labelled evaluation to measure precision and recall for the current review pipeline.</p></div>}
            <p className="mu">Metrics use the checked-in labelled samples, not fixed demo values.</p>
            <h3>Fact-drift alerts</h3>
            {loading && <div className="data-skeleton" role="status">Loading fact-drift alerts…</div>}
            {!loading && failed("drift") && <p className="alert error" role="alert">Fact-drift alerts could not be loaded: {failed("drift")} <button className="btn" onClick={() => void refresh()}>Retry</button></p>}
            {!loading && !failed("drift") && !drift.length && <p className="empty-state">No active fact-drift alerts.</p>}
            {!loading && !failed("drift") && drift.map(alert => <div className="alert-row" key={alert.id}>
              <span className="tag me">Recheck</span>
              <span>Content reference {alert.ref_id.slice(0, 8)} on {new Date(alert.created_at).toLocaleDateString()}</span>
              <button className="btn" disabled={busy} onClick={() => void act(() => api.resolveAlert(alert.id), "Fact-drift alert resolved.")}>Resolve</button>
            </div>)}
          </section>
        </div>
      </Tabs.Content>

      <Tabs.Content className="insights-panel" value="knowledge">
        <section className="pn">
          <h2>Knowledge base</h2>
          <p className="mu">Uploaded guideline clauses stay in draft until an organisation manager or admin approves them.</p>
          <form className="row" onSubmit={uploadGuideline}>
            <label htmlFor="guideline-file">Guideline document</label>
            <input id="guideline-file" type="file" accept=".txt,.md,.csv,.docx,.pdf" onChange={chooseFile(setGuidelineFile)} />
            <button className="btn pr" disabled={busy || !guidelineFile}>Upload and extract drafts</button>
          </form>
          {rules.some(rule => rule.status !== "approved") && <div className="table-wrap" style={{ marginTop: "1rem" }}>
            <table><thead><tr><th>Draft clause</th><th>Category</th><th>Source status</th><th>Action</th></tr></thead><tbody>
              {rules.filter(rule => rule.status !== "approved").map(rule => <tr key={rule.id}>
                <td><strong>{rule.clause_number}</strong><br />{rule.text}</td><td>{rule.category}</td><td>{rule.status}</td>
                <td><button className="btn" disabled={busy || rule.status === "rejected"} onClick={() => void act(() => api.updateRule(rule.id, { status: "approved" }), "Guideline rule approved.")}>Approve rule</button></td>
              </tr>)}
            </tbody></table>
          </div>}
          <div className="cols" style={{ marginTop: "1.25rem" }}>
            <form onSubmit={addFact}>
              <h3>Add approved fact</h3>
              <label htmlFor="fact-text">Fact text</label><textarea id="fact-text" required value={factText} onChange={e => setFactText(e.target.value)} />
              <label htmlFor="fact-owner">Owner</label><input id="fact-owner" value={factOwner} onChange={e => setFactOwner(e.target.value)} />
              <button className="btn pr" disabled={busy || !factText.trim()}>Add fact</button>
            </form>
            <form onSubmit={addTerm}>
              <h3>Terminology</h3>
              <label htmlFor="term-banned">Banned term</label><input id="term-banned" required value={termBanned} onChange={e => setTermBanned(e.target.value)} />
              <label htmlFor="term-preferred">Preferred replacement</label><input id="term-preferred" required value={termPreferred} onChange={e => setTermPreferred(e.target.value)} />
              <button className="btn pr" disabled={busy || !termBanned.trim() || !termPreferred.trim()}>Add terminology rule</button>
            </form>
          </div>
          <form className="asset-upload row" onSubmit={addAsset} style={{ marginTop: "1.25rem" }}>
            <label htmlFor="asset-name">Asset name</label><input id="asset-name" value={assetName} onChange={e => setAssetName(e.target.value)} />
            <label htmlFor="asset-file">Brand asset</label><input id="asset-file" type="file" onChange={chooseFile(setAssetFile)} />
            <button className="btn pr" disabled={busy || !assetFile}>Upload asset</button>
          </form>
          <div className="knowledge-data" aria-label="Knowledge base data status">
            <div><strong>Guideline rules</strong>{loading ? <span role="status">Loading…</span> : failed("rules") ? <span className="inline-error" role="alert">Could not load rules: {failed("rules")}</span> : !rules.length ? <span>No guideline rules yet.</span> : <span>{rules.length} rules, {rules.filter(rule => rule.status === "approved").length} approved</span>}</div>
            <div><strong>Approved facts</strong>{loading ? <span role="status">Loading…</span> : failed("facts") ? <span className="inline-error" role="alert">Could not load facts: {failed("facts")}</span> : !facts.length ? <span>No facts added yet.</span> : <span>{facts.length} facts</span>}</div>
            <div><strong>Terminology</strong>{loading ? <span role="status">Loading…</span> : failed("terms") ? <span className="inline-error" role="alert">Could not load terms: {failed("terms")}</span> : !terms.length ? <span>No terminology rules yet.</span> : <span>{terms.length} terminology rules</span>}</div>
            <div><strong>Brand assets</strong>{loading ? <span role="status">Loading…</span> : failed("assets") ? <span className="inline-error" role="alert">Could not load assets: {failed("assets")}</span> : !assets.length ? <span>No brand assets uploaded yet.</span> : <span>{assets.length} assets</span>}</div>
          </div>
        </section>
      </Tabs.Content>
    </Tabs.Root>
    {message && <p className="ok" role="status">{message}</p>}
    {errors.map(error => <p className="alert error" role="alert" key={error}>{error}</p>)}
  </div>;
}
