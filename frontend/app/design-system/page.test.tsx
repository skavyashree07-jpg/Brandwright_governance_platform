import { cleanup, render } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it } from "vitest";
import DesignSystemPage from "./page";

afterEach(cleanup);

describe("design system accessibility", () => {
  it("has no axe violations in the component catalog", async () => {
    const { container } = render(<main><DesignSystemPage /></main>);
    const results = await axe.run(container, {
      rules: {
        "color-contrast": { enabled: false },
        "label-content-name-mismatch": { enabled: false },
      },
    });

    expect(results.violations).toEqual([]);
  });
});
