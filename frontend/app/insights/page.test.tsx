import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import Insights from "./page";

vi.mock("@/components/Shell", () => ({
  useUser: () => ({ id: "manager-1", email: "manager@brandwright.test", role: "manager", organisation_id: "org-1" }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    health: vi.fn().mockResolvedValue([]),
    drift: vi.fn().mockResolvedValue([]),
    runTrust: vi.fn().mockResolvedValue({
      precision: 0.8, recall: 0.75, created_at: "2026-03-10T12:00:00Z", sample_count: 3,
    }),
    overview: vi.fn().mockResolvedValue({
      reviews_run: 12,
      unsupported_claims_flagged: 3,
      facts_expiring_30d: 2,
      ai_usage_log_entries: 6,
    }),
    rules: vi.fn().mockResolvedValue([]),
    facts: vi.fn().mockResolvedValue([]),
    terms: vi.fn().mockResolvedValue([]),
    assets: vi.fn().mockResolvedValue([]),
    updateRule: vi.fn(),
    createFact: vi.fn(),
    createTerm: vi.fn(),
    uploadGuideline: vi.fn(),
    uploadAsset: vi.fn(),
  },
  errText: (error: unknown) => error instanceof Error ? error.message : "Request failed",
}));

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.clearAllMocks();
});

function renderInsights() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><Insights /></QueryClientProvider>);
}

describe("Governance insights", () => {
  it("renders API metrics and the human-governed trust controls", async () => {
    renderInsights();

    expect(await screen.findByText("12")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Governance" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("heading", { name: "Trust scorecard" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Run labelled evaluation" })).toBeTruthy();
  });

  it("shows a real empty state, runs the evaluation, and displays its result and timestamp", async () => {
    renderInsights();

    expect(await screen.findByText("No evaluation run yet")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Run labelled evaluation" }));

    await waitFor(() => expect(api.runTrust).toHaveBeenCalledOnce());
    expect(await screen.findByText("80%", { exact: true })).toBeTruthy();
    expect(screen.getByText("75%", { exact: true })).toBeTruthy();
    expect(screen.getByText(/Last run:/)).toBeTruthy();
    expect(screen.getByText(/3 labelled samples/)).toBeTruthy();
  });

  it("shows a useful error when the evaluation request fails", async () => {
    vi.mocked(api.runTrust).mockRejectedValueOnce(new Error("Evaluation service unavailable"));
    renderInsights();

    fireEvent.click(await screen.findByRole("button", { name: "Run labelled evaluation" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Evaluation service unavailable");
    expect(screen.getByText("No evaluation run yet")).toBeTruthy();
  });

  it("expands long guideline text and keeps its status available", async () => {
    vi.mocked(api.health).mockResolvedValueOnce([{
      rule_id: "rule-1",
      clause_number: "R1.1",
      text: "All public-facing content must use the approved product name and avoid unsupported performance claims.",
      category: "messaging",
      dismiss_rate: 0.5,
      total_decisions: 4,
      status: "unclear",
    }]);
    renderInsights();

    const summary = await screen.findByText("Show full rule");
    const details = summary.closest("details");
    expect(details?.open).toBe(false);
    fireEvent.click(summary);
    expect(details?.open).toBe(true);
    expect(screen.getByText("Needs review")).toBeTruthy();
  });

  it("shows a data error instead of presenting a failed request as an empty result", async () => {
    vi.mocked(api.health).mockRejectedValueOnce(new Error("Guideline service unavailable"));
    renderInsights();

    expect((await screen.findByRole("alert")).textContent).toContain("Guideline service unavailable");
    expect(screen.queryByText(/No guideline health data yet/)).toBeNull();
  });
});
