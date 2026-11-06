import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Login from "./page";
import { api, tk } from "@/lib/api";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/lib/api", () => ({
  ApiError: class extends Error { status = 0; },
  api: { login: vi.fn(), demoLogin: vi.fn(), me: vi.fn() },
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
  it("supports password visibility, password help, and clearly marked SSO placeholders", () => {
    const { container } = renderLogin();
    const password = container.querySelector<HTMLInputElement>("#p")!;
    expect(password.type).toBe("password");
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(password.type).toBe("text");

    fireEvent.click(screen.getByRole("button", { name: "Forgot password?" }));
    expect(screen.getByRole("heading", { name: "Password help" })).toBeTruthy();
    expect(screen.getByText(/Password recovery is not available in this API/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Back to sign in" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue with Google" }));
    expect(screen.getByRole("status").textContent).toContain("No SSO endpoint is configured");
  });

  it("hides demo access unless the public demo flag is enabled", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "false");
    renderLogin();
    expect(screen.queryByRole("button", { name: /Continue as Creator/ })).toBeNull();
  });

  it("signs in as the selected demo role and redirects using the profile role", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "true");
    vi.mocked(api.demoLogin).mockResolvedValue({ access_token: "demo-token", token_type: "bearer" });
    vi.mocked(api.me).mockResolvedValue({
      id: "creator-id",
      email: "creator@demo.brandwright.app",
      role: "creator",
      organisation_id: "demo-org",
    });
    renderLogin();

    fireEvent.click(screen.getByRole("button", { name: /Continue as Creator/ }));

    await waitFor(() => expect(api.demoLogin).toHaveBeenCalledWith("creator"));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(tk.set).toHaveBeenCalledWith("demo-token");
    expect(screen.getByText("Demo environment, sample data only.")).toBeTruthy();
  });

  it("disables demo role buttons while signing in and shows request errors", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "true");
    let rejectDemo!: (error: Error) => void;
    vi.mocked(api.demoLogin).mockReturnValue(new Promise((_, reject) => { rejectDemo = reject; }));
    renderLogin();

    fireEvent.click(screen.getByRole("button", { name: /Continue as Reviewer/ }));
    const demoButtons = Array.from(document.querySelectorAll<HTMLButtonElement>(".demo-login-button"));
    expect(demoButtons[1].textContent).toContain("Signing in...");
    expect(demoButtons.every(button => button.disabled)).toBe(true);

    rejectDemo(new Error("Demo unavailable"));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Demo unavailable");
  });

  it("offers a retry when demo sign-in times out", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "true");
    vi.mocked(api.demoLogin).mockRejectedValue(new DOMException("Timed out", "TimeoutError"));
    renderLogin();

    fireEvent.click(screen.getByRole("button", { name: /Continue as Admin/ }));

    expect(await screen.findByText(/demo server is waking up/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retry demo sign-in" })).toBeTruthy();
  });
});
