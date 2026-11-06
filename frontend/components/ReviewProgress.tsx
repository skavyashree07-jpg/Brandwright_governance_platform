type ProgressFinding = {
  id: string;
  category: string;
  explanation: string;
};

const stages = [
  ["extraction", "Extracting content"],
  ["deterministic_checks", "Checking deterministic rules"],
  ["claim_verification", "Verifying claims"],
  ["ai_review", "Reviewing with AI"],
] as const;

export function ReviewProgress({
  status,
  stage,
  message,
  findings,
}: {
  status: string;
  stage: string;
  message: string;
  findings: ProgressFinding[];
}) {
  if (!status || status === "completed" || status === "failed") return null;
  const activeStage = stages.findIndex(([key]) => key === stage);
  const percentage = activeStage < 0 ? 0 : Math.round(((activeStage + 1) / stages.length) * 100);

  return (
    <section className="panel" aria-label="Review progress">
      <div role="status" aria-live="polite">
        <strong>Review {status}</strong>
        <p>{message || "Preparing your content for review."}</p>
        <progress value={percentage} max={100} aria-label={`Review ${percentage}% complete`} />
        <ol>
          {stages.map(([key, label], index) => (
            <li key={key} aria-current={key === stage ? "step" : undefined}>
              {index < activeStage ? "Complete: " : key === stage ? "In progress: " : ""}
              {label}
            </li>
          ))}
        </ol>
        <p>{findings.length} finding{findings.length === 1 ? "" : "s"} received so far.</p>
      </div>
      <ul className="sr-only" aria-live="polite" aria-label="New findings">
        {findings.map((finding) => (
          <li key={finding.id}>{`New ${finding.category} finding: ${finding.explanation}`}</li>
        ))}
      </ul>
    </section>
  );
}
