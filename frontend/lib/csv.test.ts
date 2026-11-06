import { afterEach, describe, expect, it, vi } from "vitest";
import { downloadCsv } from "./csv";

describe("CSV export", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

  it("quotes values and neutralizes spreadsheet formulas", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const createObjectURL = vi.fn().mockReturnValue("blob:test");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    vi.stubGlobal("Blob", class TestBlob { constructor(public parts: BlobPart[]) {} });
    vi.useFakeTimers();

    downloadCsv("report.csv", ["Title"], [["=HYPERLINK(\"bad\")"]]);

    expect(click).toHaveBeenCalledOnce();
    const blob = createObjectURL.mock.calls[0][0] as unknown as { parts: BlobPart[] };
    const text = String(blob.parts[0]);
    expect(text).toContain(`"'=HYPERLINK(""bad"")"`);
    await vi.advanceTimersByTimeAsync(1000);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test");
  });
});
