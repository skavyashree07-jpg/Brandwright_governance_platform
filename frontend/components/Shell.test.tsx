import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Shell from "./Shell";
import { api } from "@/lib/api";

const mocks = vi.hoisted(() => ({
  api: {
    me: vi.fn(),
    brands: vi.fn(),
    queue: vi.fn(),
    jurySwitchRole: vi.fn(),
    contentList: vi.fn(),
    rules: vi.fn(),
    facts: vi.fn(),
  },
  replace: vi.fn(),
  token: "jury-token",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/insights",
  useRouter: () => ({ replace: mocks.replace, push: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  api: mocks.api,
  ApiError: class extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  },
  CONNECTION_LOST_EVENT: "connection-lost",
  CONNECTION_RESTORED_EVENT: "connection-restored",
  UNAUTHORIZED_EVENT: "unauthorized",
  errText: (error: unknown) => error instanceof Error ? error.message : "Request failed",
  tk: {
    get: () => mocks.token,
    set: (token: string) => { mocks.token = token; },
    clear: () => { mocks.token = ""; },
  },
}));

afterEach(() => {
  cleanup();
  localStorage.clear();
  mocks.token = "jury-token";
  vi.clearAllMocks();
});

function renderShell() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <Shell><p>Workspace content</p></Shell>
    </QueryClientProvider>,
  );
}

describe("Jury demo shell", () => {
  it("switches the active brand without discarding the brand list", async () => {
    const admin = {
      id: "admin-id",
      email: "admin@demo.brandwright.app",
      role: "admin",
      organisation_id: "demo-org",
      jury_demo: false,
    };
    const brands = [
      { id: "brand-one", name: "Brand One", status: "active", created_at: "", updated_at: "" },
      { id: "brand-two", name: "Brand Two", status: "active", created_at: "", updated_at: "" },
    ];
    localStorage.setItem("bw_tour_complete:demo-org:admin-id", "true");
    mocks.api.me.mockResolvedValue(admin);
    mocks.api.brands.mockResolvedValue(brands);
    mocks.api.queue.mockResolvedValue([]);
    renderShell();

    const selector = await screen.findByRole("combobox", { name: "Active brand" }) as HTMLSelectElement;
    await waitFor(() => expect(selector.value).toBe("brand-one"));
    const initialQueueRequests = mocks.api.queue.mock.calls.length;
    fireEvent.change(selector, { target: { value: "brand-two" } });

    await waitFor(() => expect(selector.value).toBe("brand-two"));
    await waitFor(() => expect(mocks.api.queue.mock.calls.length).toBeGreaterThan(initialQueueRequests));
    expect(localStorage.getItem("bw_active_brand:demo-org:admin-id")).toBe("brand-two");
    expect(mocks.api.brands).toHaveBeenCalledTimes(1);
  });

  it("switches the authenticated role and opens its existing workspace", async () => {
    const admin = {
      id: "admin-id",
      email: "admin@demo.brandwright.app",
      role: "admin",
      organisation_id: "demo-org",
      jury_demo: true,
    };
    const reviewer = {
      id: "reviewer-id",
      email: "reviewer@demo.brandwright.app",
      role: "reviewer",
      organisation_id: "demo-org",
      jury_demo: true,
    };
    localStorage.setItem("bw_tour_complete:demo-org:admin-id", "true");
    localStorage.setItem("bw_tour_complete:demo-org:reviewer-id", "true");
    mocks.api.me.mockResolvedValueOnce(admin).mockResolvedValueOnce(admin).mockResolvedValueOnce(reviewer);
    mocks.api.queue.mockResolvedValue([]);
    mocks.api.brands.mockResolvedValue([]);
    mocks.api.jurySwitchRole.mockResolvedValue({ access_token: "reviewer-token", token_type: "bearer" });
    renderShell();

    expect(await screen.findByText("Jury Demo Mode")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Exit Demo" })).toBeTruthy();
    const rolePicker = screen.getByRole("combobox", { name: "Switch demo role" }) as HTMLSelectElement;
    expect(rolePicker.value).toBe("admin");
    fireEvent.change(rolePicker, { target: { value: "reviewer" } });

    await waitFor(() => expect(mocks.api.jurySwitchRole).toHaveBeenCalledWith("reviewer"));
    await waitFor(() => expect(rolePicker.value).toBe("reviewer"));
    expect(mocks.token).toBe("reviewer-token");
    expect(mocks.replace).toHaveBeenCalledWith("/queue");
  });

  it("opens the creator workspace when switching to Creator", async () => {
    const admin = {
      id: "admin-id",
      email: "admin@demo.brandwright.app",
      role: "admin",
      organisation_id: "demo-org",
      jury_demo: true,
    };
    const creator = {
      id: "creator-id",
      email: "creator@demo.brandwright.app",
      role: "creator",
      organisation_id: "demo-org",
      jury_demo: true,
    };
    localStorage.setItem("bw_tour_complete:demo-org:admin-id", "true");
    localStorage.setItem("bw_tour_complete:demo-org:creator-id", "true");
    mocks.api.me.mockResolvedValueOnce(admin).mockResolvedValueOnce(admin).mockResolvedValueOnce(creator);
    mocks.api.queue.mockResolvedValue([]);
    mocks.api.brands.mockResolvedValue([]);
    mocks.api.jurySwitchRole.mockResolvedValue({ access_token: "creator-token", token_type: "bearer" });
    renderShell();

    await screen.findByText("Jury Demo Mode");
    fireEvent.change(screen.getByRole("combobox", { name: "Switch demo role" }), { target: { value: "creator" } });

    await waitFor(() => expect(mocks.api.jurySwitchRole).toHaveBeenCalledWith("creator"));
    expect(mocks.replace).toHaveBeenCalledWith("/workspace");
  });

  it("does not show jury controls when the server profile is not a jury session", async () => {
    const normalUser = {
      id: "user-id",
      email: "user@brandwright.test",
      role: "admin",
      organisation_id: "org-id",
      jury_demo: false,
    };
    localStorage.setItem("bw_tour_complete:org-id:user-id", "true");
    mocks.api.me.mockResolvedValue(normalUser);
    mocks.api.queue.mockResolvedValue([]);
    mocks.api.brands.mockResolvedValue([]);
    renderShell();

    await screen.findByText("Workspace content");
    expect(screen.queryByText("Jury Demo Mode")).toBeNull();
    expect(screen.queryByRole("combobox", { name: "Switch demo role" })).toBeNull();
  });
});
