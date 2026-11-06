import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CommandPalette } from "@/components/ui";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function showModal() { this.open = true; };
  HTMLDialogElement.prototype.close = function close() { this.open = false; };
});

afterEach(cleanup);

describe("Command palette", () => {
  it("supports keyboard search and action execution", async () => {
    const action = vi.fn().mockResolvedValue(undefined);
    render(<CommandPalette open onClose={vi.fn()} loading items={[
      { label: "Dashboard", href: "/dashboard", group: "Pages" },
      { label: "Run evaluation", group: "Actions", onSelect: action },
    ]} />);

    expect(screen.getByRole("status").textContent).toContain("Searching");
    const search = screen.getByRole("combobox");
    fireEvent.change(search, { target: { value: "evaluation" } });
    expect(screen.getByRole("option", { name: /Run evaluation/ })).toBeTruthy();
    fireEvent.keyDown(search, { key: "Enter" });
    await waitFor(() => expect(action).toHaveBeenCalledOnce());
  });

  it("shows a clear error when an action fails", async () => {
    render(<CommandPalette open onClose={vi.fn()} items={[
      { label: "Run evaluation", onSelect: async () => { throw new Error("Evaluation unavailable"); } },
    ]} />);
    fireEvent.click(screen.getByRole("option", { name: /Run evaluation/ }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("Evaluation unavailable");
  });
});
