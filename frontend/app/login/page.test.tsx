import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Login from "./page";
import { api, tk } from "@/lib/api";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/lib/api", () => ({
  api: { login: vi.fn(), juryDemoLogin: vi.fn(), me: vi.fn() },
  errText: (error: unknown) => error instanceof Error ? error.message : "Request failed",
  tk: { set: vi.fn() },
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "false");
});
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

function renderLogin() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><Login /></QueryClientProvider>);
}

describe("Login interactions", () => {
  it("supports password visibility", () => {
    const { container } = renderLogin();
    const password = container.querySelector<HTMLInputElement>("#p")!;
    expect(password.type).toBe("password");
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(password.type).toBe("text");
  });

  it("enters the jury demo as admin without credentials", async () => {
    vi.mocked(api.juryDemoLogin).mockResolvedValue({ access_token: "jury-token", token_type: "bearer" });
    vi.mocked(api.me).mockResolvedValue({
      id: "admin-id",
      email: "admin@demo.brandwright.app",
      role: "admin",
      organisation_id: "demo-org",
      jury_demo: true,
    });
    renderLogin();

    fireEvent.click(screen.getByRole("button", { name: "Explore as Jury" }));

    await waitFor(() => expect(api.juryDemoLogin).toHaveBeenCalledOnce());
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/workspace"));
    expect(tk.set).toHaveBeenCalledWith("jury-token");
    expect(api.login).not.toHaveBeenCalled();
  });

  it("accepts any non-empty email and password, then opens the demo workspace", async () => {
    vi.mocked(api.login).mockResolvedValue({ access_token: "demo-token", token_type: "bearer" });
    vi.mocked(api.me).mockResolvedValue({
      id: "creator-id",
      email: "creator@demo.brandwright.app",
      role: "creator",
      organisation_id: "demo-org",
    });
    renderLogin();

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "not-an-email" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "anything" } });
    fireEvent.click(screen.getByRole("button", { name: "Enter workspace" }));

    await waitFor(() => expect(api.login).toHaveBeenCalledWith("not-an-email", "anything"));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(tk.set).toHaveBeenCalledWith("demo-token");
  });

  it("requires non-empty credentials", async () => {
    renderLogin();

    fireEvent.click(screen.getByRole("button", { name: "Enter workspace" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Enter your email.");
    expect(api.login).not.toHaveBeenCalled();
  });

  it("shows login request errors", async () => {
    vi.mocked(api.login).mockRejectedValue(new Error("Demo unavailable"));
    renderLogin();

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "any-email" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "any-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Enter workspace" }));

    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Demo unavailable");
  });
});
