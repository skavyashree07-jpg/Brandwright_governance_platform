"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  Bell, Building2, ChartNoAxesCombined, ChevronDown, CircleHelp, ClipboardList,
  Command, Contrast, FileClock, FileText, LayoutDashboard, LogOut, Menu, Moon,
  PanelLeftClose, PanelLeftOpen, PenLine, Search, Settings2, ShieldCheck, Sun, Users,
} from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, Brand, CONNECTION_LOST_EVENT, CONNECTION_RESTORED_EVENT, tk, UNAUTHORIZED_EVENT, User, Role, DemoRole, errText } from "@/lib/api";
import { Badge, Button, CommandPalette, CommandPaletteItem, Dialog, Drawer } from "@/components/ui";

const UserContext = createContext<User | null>(null);
type BrandContextValue = {
  activeBrand: Brand | null;
  activeBrandId: string | null;
  brands: Brand[];
  setActiveBrand: (brandId: string | null) => void;
};
const BrandContext = createContext<BrandContextValue | null>(null);
export const useUser = () => {
  const user = useContext(UserContext);
  if (!user) throw new Error("useUser must be used inside the authenticated application shell.");
  return user;
};
export const useBrand = () => {
  const context = useContext(BrandContext);
  if (!context) throw new Error("useBrand must be used inside the authenticated application shell.");
  return context;
};

type ThemeMode = "system" | "light" | "dark" | "high-contrast";
type NavigationItem = {
  href: string;
  label: string;
  description: string;
  roles: Role[];
  icon: typeof PenLine;
  badge?: "queue";
};
const NAVIGATION_GROUPS: { label: string; items: NavigationItem[] }[] = [
  { label: "Work", items: [
    { href: "/dashboard", label: "Dashboard", description: "Your recent work", roles: ["creator"], icon: LayoutDashboard },
    { href: "/workspace", label: "Creator workspace", description: "Check a draft", roles: ["creator", "admin"], icon: PenLine },
    { href: "/submissions", label: "Submissions", description: "Your content and statuses", roles: ["creator"], icon: FileText },
    { href: "/queue", label: "Review queue", description: "Review submitted work", roles: ["reviewer", "manager", "admin"], icon: ClipboardList, badge: "queue" },
  ] },
  { label: "Governance", items: [
    { href: "/insights", label: "Governance insights", description: "Health, trust, and drift", roles: ["manager", "admin"], icon: ChartNoAxesCombined },
    { href: "/brand-knowledge", label: "Brand knowledge", description: "Guidelines, facts and assets", roles: ["manager", "admin"], icon: FileText },
  ] },
  { label: "Administration", items: [
    { href: "/brands", label: "Brand management", description: "Create and manage brands", roles: ["admin"], icon: Building2 },
    { href: "/audit-log", label: "Audit log", description: "Organisation activity", roles: ["manager", "admin"], icon: FileClock },
    { href: "/team", label: "Team", description: "Members and roles", roles: ["manager", "admin"], icon: Users },
    { href: "/settings", label: "Settings", description: "Organisation preferences", roles: ["manager", "admin"], icon: Settings2 },
  ] },
  { label: "System", items: [
    { href: "/design-system", label: "Design system", description: "Tokens and components", roles: ["creator", "reviewer", "manager", "admin"], icon: Contrast },
    { href: "/notifications", label: "Notifications", description: "Queue and fact alerts", roles: ["creator", "reviewer", "manager", "admin"], icon: Bell },
  ] },
];
const ATTENTION_DESCRIPTIONS: Record<string, string> = {
  "/dashboard": "Your recent work",
  "/workspace": "Run a pre-publication check on a draft",
  "/queue": "Check submissions and open findings",
  "/insights": "Review guideline health and fact drift",
  "/brand-knowledge": "Manage approved brand sources",
  "/audit-log": "Inspect recorded organisation actions",
  "/team": "Manage team access",
  "/settings": "Configure your workspace",
  "/notifications": "Your review and fact alerts",
  "/submissions": "Your recent submissions",
  "/design-system": "Review interface components and tokens",
};
const THEME_OPTIONS: { value: ThemeMode; label: string; icon: typeof Sun }[] = [
  { value: "system", label: "System theme", icon: Contrast },
  { value: "light", label: "Light theme", icon: Sun },
  { value: "dark", label: "Dark theme", icon: Moon },
  { value: "high-contrast", label: "High contrast", icon: Contrast },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const queryClient = useQueryClient();
  const isPublic = path === "/" || path === "/login";
  const [user, setUser] = useState<User | null>(null);
  const [bootError, setBootError] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);
  const [tourStep, setTourStep] = useState(0);
  const [tourStorageError, setTourStorageError] = useState("");
  const [offline, setOffline] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [switchingRole, setSwitchingRole] = useState(false);
  const [roleSwitchError, setRoleSwitchError] = useState("");
  const [theme, setTheme] = useState<ThemeMode>("system");
  const [themeReady, setThemeReady] = useState(false);
  const [activeBrandId, setActiveBrandId] = useState<string | null>(null);
  const brandsQuery = useQuery({
    queryKey: ["brands", user?.organisation_id],
    queryFn: () => api.brands(),
    enabled: !!user,
  });
  const brands = brandsQuery.data ?? [];
  const activeBrand = brands.find(brand => brand.id === activeBrandId) ?? null;

  const { data: queueItems = [] } = useQuery({
    queryKey: ["shell-queue-count", user?.organisation_id, activeBrandId],
    queryFn: api.queue,
    enabled: !!user && ["reviewer", "manager", "admin"].includes(user.role),
    refetchInterval: 30_000,
  });
  const queueCount = queueItems.length;
  const commandContent = useQuery({ queryKey: ["command-content", user?.organisation_id, activeBrandId], queryFn: api.contentList, enabled: commandOpen && user?.role === "creator" });
  const commandQueue = useQuery({ queryKey: ["command-queue", user?.organisation_id, activeBrandId], queryFn: api.queue, enabled: commandOpen && !!user && ["reviewer", "manager", "admin"].includes(user.role) });
  const commandRules = useQuery({ queryKey: ["command-rules", user?.organisation_id, activeBrandId], queryFn: () => api.rules(), enabled: commandOpen && !!user });
  const commandFacts = useQuery({ queryKey: ["command-facts", user?.organisation_id, activeBrandId], queryFn: () => api.facts(), enabled: commandOpen && !!user });

  useEffect(() => {
    if (!user || !brandsQuery.data) return;
    const preferenceKey = `bw_active_brand:${user.organisation_id}:${user.id}`;
    const saved = localStorage.getItem(preferenceKey);
    const selected = saved === "all" ? null : brandsQuery.data.find(brand => brand.id === saved) ?? brandsQuery.data[0] ?? null;
    setActiveBrandId(selected?.id ?? null);
    if (selected) localStorage.setItem("bw_active_brand_id", selected.id);
    else localStorage.removeItem("bw_active_brand_id");
  }, [brandsQuery.data, user]);

  const setActiveBrand = useCallback((brandId: string | null) => {
    if (!user) return;
    const selected = brandId ? brands.find(brand => brand.id === brandId) : null;
    if (brandId && !selected) return;
    setActiveBrandId(selected?.id ?? null);
    localStorage.setItem(`bw_active_brand:${user.organisation_id}:${user.id}`, selected?.id ?? "all");
    if (selected) localStorage.setItem("bw_active_brand_id", selected.id);
    else localStorage.removeItem("bw_active_brand_id");
  }, [brands, user]);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem("bw_sidebar_collapsed") === "true");
      const savedTheme = localStorage.getItem("bw_theme") as ThemeMode | null;
      if (savedTheme && THEME_OPTIONS.some(option => option.value === savedTheme)) setTheme(savedTheme);
    } finally {
      setThemeReady(true);
    }
  }, []);

  useEffect(() => {
    if (!themeReady) return;
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("bw_theme", theme);
  }, [theme, themeReady]);

  useEffect(() => {
    const handleUnauthorized = () => {
      tk.clear();
      queryClient.clear();
      setUser(null);
      router.replace("/login");
    };
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, [queryClient, router]);
  async function switchJuryRole(role: DemoRole) {
    if (!user?.jury_demo || switchingRole) return;
    const previousToken = tk.get();
    setSwitchingRole(true);
    setRoleSwitchError("");
    try {
      const result = await api.jurySwitchRole(role);
      tk.set(result.access_token);
      const profile = await api.me();
      if (!profile.jury_demo) throw new Error("The API did not confirm the jury demo session.");
      queryClient.clear();
      setUser(profile);
      router.replace(role === "creator" ? "/workspace" : role === "reviewer" ? "/queue" : "/insights");
    } catch (cause) {
      if (previousToken && !(cause instanceof ApiError && cause.status === 401)) tk.set(previousToken);
      setRoleSwitchError(errText(cause));
    } finally {
      setSwitchingRole(false);
    }
  }

  useEffect(() => {
    const showOffline = () => setOffline(true);
    const recover = () => {
      setOffline(wasOffline => {
        if (wasOffline) void queryClient.invalidateQueries();
        return false;
      });
    };
    if (typeof navigator !== "undefined" && !navigator.onLine) setOffline(true);
    window.addEventListener("offline", showOffline);
    window.addEventListener("online", recover);
    window.addEventListener(CONNECTION_LOST_EVENT, showOffline);
    window.addEventListener(CONNECTION_RESTORED_EVENT, recover);
    return () => {
      window.removeEventListener("offline", showOffline);
      window.removeEventListener("online", recover);
      window.removeEventListener(CONNECTION_LOST_EVENT, showOffline);
      window.removeEventListener(CONNECTION_RESTORED_EVENT, recover);
    };
  }, [queryClient]);

  useEffect(() => {
    if (!user || isPublic) return;
    try {
      const key = `bw_tour_complete:${user.organisation_id}:${user.id}`;
      if (localStorage.getItem(key) !== "true") setTourOpen(true);
    } catch { setTourStorageError("The first-time tour could not check browser storage. You can still start or close it from Help."); }
  }, [isPublic, user]);

  useEffect(() => {
    if (isPublic || user) return;
    if (!tk.get()) { router.replace("/login"); return; }
    let active = true;
    api.me().then(profile => {
      if (active) { setUser(profile); setBootError(""); }
    }).catch(error => {
      if (!active) return;
      if (error instanceof ApiError && error.status === 401) {
        tk.clear(); queryClient.clear(); router.replace("/login");
      } else setBootError("We could not connect to the Brandwright API. Check the backend and reload.");
    });
    return () => { active = false; };
  }, [isPublic, user, router, queryClient]);

  const groups = useMemo(() => user
    ? NAVIGATION_GROUPS.map(group => ({ ...group, items: group.items.filter(item => item.roles.includes(user.role)) })).filter(group => group.items.length)
    : [], [user]);
  const links = useMemo(() => groups.flatMap(group => group.items), [groups]);
  const activeLink = links.find(link => path.startsWith(link.href));
  const protectedRoutes: { prefix: string; roles: Role[] }[] = [
    { prefix: "/dashboard", roles: ["creator"] },
    { prefix: "/workspace", roles: ["creator", "admin"] },
    { prefix: "/submissions", roles: ["creator"] },
    { prefix: "/queue", roles: ["reviewer", "manager", "admin"] },
    { prefix: "/insights", roles: ["manager", "admin"] },
    { prefix: "/brand-knowledge", roles: ["manager", "admin"] },
    { prefix: "/audit-log", roles: ["manager", "admin"] },
    { prefix: "/team", roles: ["manager", "admin"] },
    { prefix: "/settings", roles: ["manager", "admin"] },
  ];
  const routeGuard = protectedRoutes.find(route => path.startsWith(route.prefix));
  const denied = !!user && !!routeGuard && !routeGuard.roles.includes(user.role);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target;
      const editing = target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
      if (event.key === "?" && !editing) {
        event.preventDefault();
        setShortcutsOpen(true);
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(open => !open);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const toggleSidebar = useCallback(() => {
    setCollapsed(value => {
      localStorage.setItem("bw_sidebar_collapsed", String(!value));
      return !value;
    });
  }, []);
  const signOut = useCallback(() => {
    tk.clear();
    queryClient.clear();
    setUser(null);
    router.replace("/login");
  }, [queryClient, router]);
  const cycleTheme = useCallback(() => {
    setTheme(value => THEME_OPTIONS[(THEME_OPTIONS.findIndex(option => option.value === value) + 1) % THEME_OPTIONS.length].value);
  }, []);
  const themeOption = THEME_OPTIONS.find(option => option.value === theme) ?? THEME_OPTIONS[0];
  const ThemeIcon = themeOption.icon;
  const commandItems: CommandPaletteItem[] = [
    ...links.map(item => ({ label: item.label, description: item.description, href: item.href, group: "Pages" })),
    ...(user && ["creator", "admin"].includes(user.role) ? [{ label: "New review", description: "Open the creator workspace", href: "/workspace", group: "Actions" }] : []),
    ...(user && ["manager", "admin"].includes(user.role) ? [{
      label: "Run evaluation",
      description: "Run the labelled trust evaluation",
      group: "Actions",
      onSelect: async () => { await api.runTrust(); router.push("/insights"); },
    }] : []),
    ...(!user ? [] : (user.role === "creator" ? commandContent.data ?? [] : commandQueue.data ?? [])
      .filter(item => user.role !== "creator" || item.creator_id === user.id)
      .slice(0, 100)
      .map(item => ({ label: item.title || "Untitled submission", description: `${item.status.replace(/_/g, " ")} · version ${item.current_version_no}`, keywords: item.id, href: user.role === "creator" ? `/submissions/${item.id}` : `/queue/${item.id}`, group: "Submissions" }))),
    ...(commandRules.data ?? []).slice(0, 100).map(rule => ({ label: `${rule.clause_number}: ${rule.text}`, description: `${rule.category} guideline`, href: "/brand-knowledge", group: "Rules" })),
    ...(commandFacts.data ?? []).slice(0, 100).map(fact => ({ label: fact.text, description: `Approved fact${fact.owner ? ` · ${fact.owner}` : ""}`, href: "/brand-knowledge", group: "Facts" })),
  ];
  const searchError = [commandContent.error, commandQueue.error, commandRules.error, commandFacts.error].find(Boolean);
  const tourSteps = [
    { title: "Your work, in one place", text: "Create a review, track submissions, and see items waiting for action from your role." },
    { title: "Find anything quickly", text: "Use Ctrl or Cmd + K to search pages, submissions, rules, and facts, or run available actions." },
    { title: "People decide", text: "The review engine explains and suggests. People make every final approval and content decision." },
  ];
  function finishTour() {
    try {
      if (user) localStorage.setItem(`bw_tour_complete:${user.organisation_id}:${user.id}`, "true");
    } catch (cause) {
      setTourStorageError(cause instanceof Error ? `The tour was closed, but completion could not be saved: ${cause.message}` : "The tour was closed, but browser storage is unavailable.");
    }
    setTourOpen(false);
    setTourStep(0);
  }
  async function retryConnection() {
    setRetrying(true);
    try { await queryClient.invalidateQueries(); }
    finally { setRetrying(false); }
  }

  if (isPublic) return <>{children}</>;
  if (bootError) return <main className="boot-state"><p className="alert error">{bootError}</p><button className="button primary" onClick={() => location.reload()}>Retry connection</button></main>;
  if (!user) return <main className="boot-state" role="status">Loading your secure workspace…</main>;

  const Navigation = ({ onNavigate }: { onNavigate?: () => void }) => <nav className="shell-navigation" aria-label="Application navigation">
    {groups.map(group => <section className="shell-nav-group" key={group.label} aria-label={group.label}>
      <h2 className="shell-nav-heading">{group.label}</h2>
      {group.items.map(item => {
        const Icon = item.icon;
        const count = item.badge === "queue" ? queueCount : 0;
        return <Link key={item.href} href={item.href} onClick={onNavigate} className={`shell-nav-link ${path.startsWith(item.href) ? "is-active" : ""}`} aria-current={path.startsWith(item.href) ? "page" : undefined} aria-label={collapsed ? `${item.label}${count ? `, ${count} open` : ""}` : undefined} title={collapsed ? item.label : undefined}>
          <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
          <span className="shell-nav-label">{item.label}</span>
          {count > 0 && <Badge tone="warning">{count}</Badge>}
        </Link>;
      })}
    </section>)}
  </nav>;

  return <UserContext.Provider value={user}>
    <BrandContext.Provider value={{ activeBrand, activeBrandId, brands, setActiveBrand }}>
    <a className="skip-link" href="#main">Skip to content</a>
    <div className={`app-frame ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="app-rail" aria-label="Workspace sidebar">
        <div className="shell-brand-row">
          <Link href="/" className="rail-brand" aria-label={collapsed ? "Brandwright home" : undefined}><span className="brand-monogram" aria-hidden="true">B</span><span className="shell-brand-name">Brandwright</span></Link>
          <Button className="sidebar-collapse-button" variant="ghost" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-pressed={collapsed} onClick={toggleSidebar}>
            {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          </Button>
        </div>
        <Navigation />
        <div className="rail-bottom">
          <div className="rail-session"><ShieldCheck size={14} aria-hidden="true" /><span className="shell-nav-label">Authenticated session</span></div>
          <div className="rail-user">
            <span className="avatar" aria-hidden="true">{user.email.slice(0, 1).toUpperCase()}</span>
            <span className="rail-user-copy"><strong>{user.email}</strong><small>{user.jury_demo ? "Jury Demo · " : ""}{user.role}</small></span>
            <Button className="rail-signout" variant="ghost" onClick={signOut} title={user.jury_demo ? "Exit demo" : "Sign out"} aria-label={user.jury_demo ? "Exit demo" : "Sign out"}><LogOut size={17} /></Button>
          </div>
        </div>
      </aside>

      <div className="app-main">
        {user.jury_demo && <section className="jury-demo-bar" aria-label="Jury demo controls">
          <div className="jury-demo-status">
            <ShieldCheck size={17} aria-hidden="true" />
            <span><strong>Jury Demo Mode</strong><small>Fictional demo organisation · {user.role}</small></span>
          </div>
          <label className="jury-role-picker">
            <span>Explore as</span>
            <select
              aria-label="Switch demo role"
              value={user.role}
              disabled={switchingRole}
              onChange={event => void switchJuryRole(event.target.value as DemoRole)}
            >
              <option value="admin">Admin</option>
              <option value="reviewer">Reviewer</option>
              <option value="creator">Creator</option>
            </select>
          </label>
          {switchingRole && <span className="jury-switching" role="status">Switching role…</span>}
          {roleSwitchError && <p className="jury-demo-error" role="alert">{roleSwitchError}</p>}
          <Button variant="secondary" size="sm" onClick={signOut}>Exit Demo</Button>
        </section>}
        {offline && <div className="connection-banner" role="status"><span>Connection lost. Some information may be out of date.</span><Button variant="secondary" size="sm" loading={retrying} onClick={() => void retryConnection()}>Retry</Button></div>}
        {tourStorageError && <div className="connection-banner" role="status"><span>{tourStorageError}</span><Button variant="ghost" size="sm" onClick={() => setTourStorageError("")}>Dismiss</Button></div>}
        <header className="app-topbar">
          <div className="topbar-leading">
            <Button className="mobile-menu-button" variant="ghost" aria-label="Open navigation menu" onClick={() => setMobileOpen(true)}><Menu size={19} /></Button>
            <div className="topbar-heading">
              <span className="topbar-kicker">BRAND GOVERNANCE</span>
              <span className="topbar-title">{activeLink?.label ?? "Workspace"}</span>
            </div>
          </div>
          <div className="topbar-actions">
            {brands.length > 0 && <div className="brand-switcher">
              <label htmlFor="active-brand">Active brand</label>
              <select id="active-brand" value={activeBrandId ?? "all"} onChange={event => setActiveBrand(event.target.value === "all" ? null : event.target.value)}>
                <option value="all">All brands / shared data</option>
                {brands.map(brand => <option value={brand.id} key={brand.id}>{brand.name}</option>)}
              </select>
              {activeBrand && <Link href={`/brands/${activeBrand.id}`} className="brand-view-link">View identity</Link>}
            </div>}
            {brandsQuery.isError && <span className="brand-switcher-error" role="status">Brands unavailable</span>}
            <Button className="search-trigger" variant="secondary" onClick={() => setCommandOpen(true)} aria-label="Search K">
              <Search size={16} aria-hidden="true" /><span>Search</span><kbd aria-hidden="true"><Command size={11} /> K</kbd>
            </Button>
            <div className="shell-popover-wrap">
              <Button variant="ghost" aria-label="Notifications" aria-expanded={notificationOpen} aria-controls="notification-panel" onClick={() => setNotificationOpen(value => !value)}>
                <Bell size={18} aria-hidden="true" />{queueCount > 0 && <span className="notification-count">{queueCount}</span>}
              </Button>
              {notificationOpen && <section className="shell-popover" id="notification-panel" aria-label="Notifications">
                <h2>Notifications</h2>
                {queueCount > 0 && <Link href="/queue" onClick={() => setNotificationOpen(false)}><Badge tone="warning">{queueCount} open</Badge><span>Submissions are waiting in your review queue.</span></Link>}
                {queueCount === 0 && <p>No new notifications.</p>}
              </section>}
            </div>
            <Button variant="ghost" onClick={cycleTheme} aria-label={`Theme: ${themeOption.label}. Change theme`} title={`Theme: ${themeOption.label}`}><ThemeIcon size={18} aria-hidden="true" /></Button>
            <details className="shell-menu">
              <summary aria-label="Help menu"><CircleHelp size={18} aria-hidden="true" /><span className="sr-only">Help menu</span></summary>
              <div className="shell-menu-panel">
                <Link href="/design-system">Design system and accessibility</Link>
                <p>AI explains and suggests. People make the final decision.</p>
                <button onClick={() => { setTourStep(0); setTourOpen(true); }}>Start product tour</button>
                <button onClick={() => setShortcutsOpen(true)}>Keyboard shortcuts (?)</button>
              </div>
            </details>
            <details className="shell-menu user-menu">
              <summary aria-label="User and organisation menu"><span className="avatar">{user.email.slice(0, 1).toUpperCase()}</span><ChevronDown size={14} aria-hidden="true" /></summary>
              <div className="shell-menu-panel user-menu-panel">
                <div className="menu-identity"><strong>{user.email}</strong><span>{user.role}</span></div>
                <div className="menu-organisation"><Building2 size={15} aria-hidden="true" /><span>Organisation</span><strong>{user.organisation_id}</strong><small>Organisation switching is not available in this API.</small></div>
                <button onClick={signOut}><LogOut size={15} aria-hidden="true" />{user.jury_demo ? "Exit demo" : "Sign out"}</button>
              </div>
            </details>
          </div>
        </header>
        <div className="app-workarea">
          <motion.main id="main" tabIndex={-1} className="app-content" key={path} initial={reduceMotion ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduceMotion ? 0 : 0.18, ease: "easeOut" }}>
            <nav className="shell-breadcrumbs" aria-label="Page breadcrumb"><ol><li><Link href={links[0]?.href ?? "/"}>Workspace</Link></li><li aria-current="page">{activeLink?.label ?? "Workspace"}</li></ol></nav>
            {denied ? <section className="pn access-denied" role="alert"><h1>Access restricted</h1><p>Your {user.role} role cannot open this page. Contact an organisation manager if you need access.</p><Link className="btn" href={links[0]?.href ?? "/"}>Return to your workspace</Link></section> : children}
          </motion.main>
        </div>
        <footer className="app-footer"><span>Brandwright</span><span>AI explains and suggests. People make the final decision.</span></footer>
        <nav className="mobile-bottom-nav" aria-label="Quick navigation">
          {links.slice(0, 3).map(item => {
            const Icon = item.icon;
            const count = item.badge === "queue" ? queueCount : 0;
            return <Link key={item.href} href={item.href} aria-current={path.startsWith(item.href) ? "page" : undefined} onClick={() => setMobileOpen(false)}>
              <Icon size={18} aria-hidden="true" /><span>{item.label.replace("Governance ", "")}</span>{count > 0 && <span className="mobile-nav-count">{count}</span>}
            </Link>;
          })}
          <button onClick={() => setMobileOpen(true)} aria-label="More navigation"><Menu size={18} /><span>More</span></button>
        </nav>
      </div>
    </div>
    <Drawer open={mobileOpen} onClose={() => setMobileOpen(false)} title="Workspace navigation">
      <Navigation onNavigate={() => setMobileOpen(false)} />
      <div className="mobile-drawer-user"><span>{user.email}</span><span>{user.jury_demo ? "Jury Demo · " : ""}{user.role}</span><Button onClick={signOut} variant="secondary">{user.jury_demo ? "Exit demo" : "Sign out"}</Button></div>
    </Drawer>
    <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} items={commandItems} loading={commandContent.isFetching || commandQueue.isFetching || commandRules.isFetching || commandFacts.isFetching} error={searchError ? "Some search results could not be loaded. Close and retry, or navigate to the relevant page." : undefined} />
    <Dialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} title="Keyboard shortcuts">
      <dl className="shortcut-list">
        <div><dt><kbd>Ctrl</kbd> / <kbd>Cmd</kbd> + <kbd>K</kbd></dt><dd>Open search and actions</dd></div>
        <div><dt><kbd>?</kbd></dt><dd>Show this shortcut guide</dd></div>
        <div><dt><kbd>J</kbd> / <kbd>K</kbd></dt><dd>Move through review queue items</dd></div>
        <div><dt><kbd>A</kbd></dt><dd>Focus the approval action for the open review</dd></div>
        <div><dt><kbd>R</kbd></dt><dd>Focus the request-changes action for the open review</dd></div>
        <div><dt><kbd>Esc</kbd></dt><dd>Close the current dialog or palette</dd></div>
      </dl>
    </Dialog>
    <Dialog open={tourOpen} onClose={finishTour} title={tourSteps[tourStep].title}>
      <div className="product-tour">
        <p>{tourSteps[tourStep].text}</p>
        <p className="mu">Tour {tourStep + 1} of {tourSteps.length}</p>
        <div className="product-actions">
          <Button variant="ghost" onClick={finishTour}>Skip tour</Button>
          {tourStep > 0 && <Button onClick={() => setTourStep(step => step - 1)}>Back</Button>}
          <Button variant="primary" onClick={() => tourStep === tourSteps.length - 1 ? finishTour() : setTourStep(step => step + 1)}>{tourStep === tourSteps.length - 1 ? "Finish" : "Next"}</Button>
        </div>
      </div>
    </Dialog>
    </BrandContext.Provider>
  </UserContext.Provider>;
}
