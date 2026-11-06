import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import Queue from "./page";

vi.mock("@/components/Shell", () => ({
  useUser: () => ({ id: "reviewer-1", email: "reviewer@brandwright.test", role: "reviewer", organisation_id: "org-1" }),
}));

vi.mock("@/lib/kb", () => ({ useSourceLabel: () => () => null }));
vi.mock("@/components/Annotated", () => ({ Annotated: () => <div>Annotated draft</div> }));
vi.mock("@/lib/api", () => ({
  api: {
    queue: vi.fn().mockResolvedValue([]),
    content: vi.fn().mockResolvedValue({
      id: "content-1", title: "Test draft", current_version_no: 1, status: "in_review",
      body: "Draft content", intent: "Explain the product", channel: "Website", versions: [],
    }),
    findings: vi.fn().mockResolvedValue({ findings: [], ai_services_used: [] }),
    comments: vi.fn().mockResolvedValue([]),
    audit: vi.fn().mockResolvedValue([]),
    addComment: vi.fn(),
    runReview: vi.fn(),
    reviewStatus: vi.fn(),
    approve: vi.fn(),
    requestChanges: vi.fn(),
  },
  errText: (error: unknown) => error instanceof Error ? error.message : "Request failed",
  isRisky: (finding: { severity: string }) => finding.severity === "high",
  isUnverified: () => false,
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderQueue() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><Queue /></QueryClientProvider>);
}

describe("Review queue states", () => {
  it("shows a real empty state when the queue request succeeds with no items", async () => {
    renderQueue();

    expect(await screen.findByRole("heading", { name: "Queue is clear" })).toBeTruthy();
  });

  it("does not present a failed queue request as an empty queue", async () => {
    vi.mocked(api.queue).mockRejectedValueOnce(new Error("Queue service unavailable"));
    renderQueue();

    expect((await screen.findByRole("alert")).textContent).toContain("Queue service unavailable");
    expect(screen.queryByRole("heading", { name: "Queue is clear" })).toBeNull();
  });

  it("shows audit failures and allows retrying the audit request", async () => {
    vi.mocked(api.queue).mockResolvedValueOnce([{
      id: "content-1", title: "Test draft", current_version_no: 1, status: "in_review",
    }]);
    vi.mocked(api.audit)
      .mockRejectedValueOnce(new Error("Audit service unavailable"))
      .mockResolvedValueOnce([]);
    renderQueue();

    fireEvent.click(await screen.findByRole("button", { name: "Open for review" }));
    fireEvent.click(await screen.findByText("Audit trail"));
    expect((await screen.findByRole("alert")).textContent).toContain("Audit service unavailable");

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByText("No entries yet.")).toBeTruthy());
  });

  it("requires a comment before requesting changes and records it first", async () => {
    vi.mocked(api.queue).mockResolvedValueOnce([{
      id: "content-1", title: "Test draft", current_version_no: 1, status: "in_review",
    }]);
    renderQueue();
    fireEvent.click(await screen.findByRole("button", { name: "Open for review" }));
    fireEvent.click(await screen.findByRole("button", { name: "Request changes" }));

    const send = screen.getByRole("button", { name: "Send change request" }) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Required change request comment"), { target: { value: "Please substantiate this claim." } });
    expect(send.disabled).toBe(false);
    fireEvent.click(send);

    await waitFor(() => expect(api.addComment).toHaveBeenCalledWith("content-1", "Please substantiate this claim."));
    await waitFor(() => expect(api.requestChanges).toHaveBeenCalledWith("content-1"));
  });

  it("saves a named queue filter and lets users customise visible columns", async () => {
    vi.mocked(api.queue).mockResolvedValueOnce([{
      id: "content-1", title: "Test draft", current_version_no: 1, status: "in_review",
    }]);
    renderQueue();
    const name = await screen.findByRole("textbox", { name: "Name this view" });
    fireEvent.change(screen.getByRole("combobox", { name: "Status" }), { target: { value: "in_review" } });
    fireEvent.change(name, { target: { value: "Current reviews" } });
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));

    expect(screen.getByRole("option", { name: "Current reviews" })).toBeTruthy();
    fireEvent.click(screen.getByText("Columns"));
    fireEvent.click(screen.getByRole("checkbox", { name: "Status" }));
    expect((screen.getByRole("checkbox", { name: "Status" }) as HTMLInputElement).checked).toBe(false);
  });
});
