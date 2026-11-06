import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ReviewProgress } from "./ReviewProgress";

afterEach(cleanup);

describe("ReviewProgress", () => {
  it("renders newly received findings incrementally", () => {
    const { rerender } = render(
      <ReviewProgress
        status="running"
        stage="deterministic_checks"
        message="Checking deterministic rules."
        findings={[]}
      />,
    );
    expect(screen.getByText("0 findings received so far.")).toBeTruthy();

    rerender(
      <ReviewProgress
        status="running"
        stage="claim_verification"
        message="Claim verification completed."
        findings={[{
          id: "finding-1",
          category: "claim",
          explanation: "This claim needs an approved source.",
        }]}
      />,
    );

    expect(screen.getByText("1 finding received so far.")).toBeTruthy();
    expect(screen.getByText("New claim finding: This claim needs an approved source.")).toBeTruthy();
  });
});
