"use client";
import { useEffect, useState } from "react";
import { api, errText, FactDriftAlert, GuidelineHealth, Overview, TrustScorecard } from "@/lib/api";

const pct = (value: unknown) => typeof value === "number" ? `${Math.round(value <= 1 ? value * 100 : value)}%` : "Not available";
export default function Insights() {
  const [health, setHealth] = useState<GuidelineHealth[]>([]);
  const [drift, setDrift] = useState<FactDriftAlert[]>([]);
  const [score, setScore] = useState<TrustScorecard | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.allSettled([api.health(), api.drift(), api.scorecard(), api.overview()]).then((results) => {
      if (!active) return;
      const names = ["Guideline Health", "Fact-drift alerts", "Trust scorecard", "Overview"];
      results.forEach((result, index) => {
        if (result.status === "rejected") setErrors((current) => [...current, `${names[index]}: ${errText(result.reason)}`]);
      });
      if (results[0].status === "fulfilled") setHealth(results[0].value);
      if (results[1].status === "fulfilled") setDrift(results[1].value);
      if (results[2].status === "fulfilled") setScore(results[2].value);
      if (results[3].status === "fulfilled") setOverview(results[3].value);
      setLoading(false);
    });
    return () => { active = false; };
  }, []);

  const scoreData = score?.latest ?? score;
  const metrics = [
    ["Reviews run", overview?.reviews_run ?? "—"],
    ["Unsupported claims flagged", overview?.unsupported_claims_flagged ?? "—"],
    ["Facts expiring in 30 days", overview?.facts_expiring_30d ?? "—"],
    ["Average review latency", overview?.avg_review_latency_ms != null ? `${overview.avg_review_latency_ms} ms` : "—"],
  ];

  return <div className="insights-page">
    <div className="page-heading"><div><div className="section-tag">ORGANISATION / GOVERNANCE</div><h1>Governance insights</h1><p className="mu">Spot unclear rules, fact changes and review-system signals.</p></div><span className="tag me">Live API data</span></div>
    <div className="metric-grid">{metrics.map(([label, value]) => <div className="metric-card" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
    <div className="cols">
      <section className="pn"><h2>Guideline health</h2><p className="mu">A high dismissal rate can indicate a rule that needs clarification or revision.</p>
        {loading && <p className="mu">Loading guideline data…</p>}
        {!loading && !health.length && <p className="mu">No guideline decisions have been recorded yet.</p>}
        {!!health.length && <div className="table-wrap"><table><thead><tr><th>Rule</th><th>Decisions</th><th>Dismissed</th><th>Status</th></tr></thead><tbody>
          {[...health].sort((a,b)=>b.dismiss_rate-a.dismiss_rate).map((rule)=><tr key={rule.rule_id}><td><strong>{rule.clause_number}</strong><br/>{rule.text}</td><td>{rule.total_decisions}</td><td>{pct(rule.dismiss_rate)}</td><td><span className={`tag ${rule.status==="unclear"?"me":"ok"}`}>{rule.status==="unclear"?"Needs review":"Healthy"}</span></td></tr>)}
        </tbody></table></div>}
      </section>
      <section className="pn"><h2>Trust scorecard</h2>
        {scoreData ? <div className="score-row"><div><span>Precision</span><strong>{pct(scoreData.precision)}</strong></div><div><span>Recall</span><strong>{pct(scoreData.recall)}</strong></div></div> : <p className="mu">Evaluation metrics are not available. The review engine may be offline or no evaluation run exists.</p>}
        <h2 style={{marginTop:"24px"}}>Fact-drift alerts</h2>
        {!drift.length && <p className="mu">No active fact-drift alerts.</p>}
        {drift.map((alert)=><div className="alert-row" key={alert.id}><span className="tag me">Recheck</span><span>Content reference {alert.ref_id.slice(0,8)} · {new Date(alert.created_at).toLocaleDateString()}</span></div>)}
      </section>
    </div>
    {errors.map((error)=><p className="alert error" role="status" key={error}>{error}</p>)}
  </div>;
}
