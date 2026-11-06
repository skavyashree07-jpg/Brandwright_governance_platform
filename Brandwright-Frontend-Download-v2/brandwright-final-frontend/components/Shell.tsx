"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, ApiError, tk, User, Role } from "@/lib/api";

const UserContext = createContext<User | null>(null);
export const useUser = () => {
  const user = useContext(UserContext);
  if (!user) throw new Error("useUser must be used inside the authenticated application shell.");
  return user;
};

const LINKS: { href: string; label: string; roles: Role[]; icon: string }[] = [
  { href: "/workspace", label: "Creator workspace", roles: ["creator", "admin"], icon: "✎" },
  { href: "/queue", label: "Review queue", roles: ["reviewer", "manager", "admin"], icon: "▤" },
  { href: "/insights", label: "Governance insights", roles: ["manager", "admin"], icon: "◫" },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const isPublic = path === "/" || path === "/login";
  const [user, setUser] = useState<User | null>(null);
  const [bootError, setBootError] = useState("");

  useEffect(() => {
    if (isPublic || user) return;
    if (!tk.get()) { router.replace("/login"); return; }
    let active = true;
    api.me().then((profile) => {
      if (active) { setUser(profile); setBootError(""); }
    }).catch((error) => {
      if (!active) return;
      if (error instanceof ApiError && error.status === 401) {
        tk.clear(); router.replace("/login");
      } else setBootError("We could not connect to the Brandwright API. Check the backend and reload.");
    });
    return () => { active = false; };
  }, [isPublic, user, router]);

  const links = useMemo(() => user ? LINKS.filter((link) => link.roles.includes(user.role)) : [], [user]);
  const activeLink = links.find((link) => path.startsWith(link.href));
  useEffect(() => {
    if (user && !activeLink && links.length) router.replace(links[0].href);
  }, [user, activeLink, links, router]);

  if (isPublic) return <>{children}</>;
  if (bootError) return <main className="boot-state"><p className="alert error">{bootError}</p><button className="button primary" onClick={() => location.reload()}>Retry connection</button></main>;
  if (!user || !activeLink) return <main className="boot-state" role="status">Loading your secure workspace…</main>;

  return (
    <UserContext.Provider value={user}>
      <a className="skip-link" href="#main">Skip to content</a>
      <div className="app-frame">
        <aside className="app-rail" aria-label="Application navigation">
          <Link href="/" className="rail-brand" aria-label="Brandwright home">B<span>.</span></Link>
          <div className="rail-caption">WORKSPACE</div>
          {links.map((link) => (
            <Link key={link.href} href={link.href} className={`rail-link ${path.startsWith(link.href) ? "active" : ""}`}>
              <span className="rail-icon" aria-hidden="true">{link.icon}</span>
              <span>{link.label}</span>
            </Link>
          ))}
          <div className="rail-bottom">
            <div className="avatar">{user.email.slice(0, 1).toUpperCase()}</div>
            <button className="rail-signout" onClick={() => { tk.clear(); setUser(null); router.replace("/login"); }} title="Sign out" aria-label="Sign out">↗</button>
          </div>
        </aside>
        <div className="app-main">
          <header className="app-topbar">
            <div>
              <div className="topbar-kicker">BRAND GOVERNANCE PLATFORM</div>
              <div className="topbar-title">{activeLink.label}</div>
            </div>
            <div className="account-chip">
              <span className="status-dot" />
              <span>{user.email}</span>
              <span className="role-pill">{user.role}</span>
            </div>
          </header>
          <div className="app-workarea">
            <main id="main" tabIndex={-1} className="app-content">
              {children}
            </main>
            <aside className="app-context-panel" aria-label="Workspace system information">
              <section className="context-card telemetry-card">
                <div className="context-heading"><h2>System telemetry</h2><span className="context-live"><i /> Connected</span></div>
                <div className="telemetry-grid">
                  <div><span>API status</span><strong>Connected</strong></div>
                  <div><span>Session</span><strong>Authenticated</strong></div>
                  <div><span>Workspace role</span><strong>{user.role}</strong></div>
                  <div><span>Environment</span><strong>Brandwright</strong></div>
                </div>
                <p className="context-note">Connection status is based on the authenticated workspace session. Performance metrics are not exposed by the demo API.</p>
              </section>
              <section className="context-card attention-card">
                <div className="context-heading"><h2>Requires attention</h2><span className="attention-mark">!</span></div>
                {links.some((link) => link.href === "/queue") && <Link href="/queue" className="attention-link"><span className="attention-icon">▤</span><span><strong>Reviewer queue</strong><small>Check submitted content and open findings</small></span><b>→</b></Link>}
                {links.some((link) => link.href === "/workspace") && <Link href="/workspace" className="attention-link"><span className="attention-icon">✎</span><span><strong>Creator workspace</strong><small>Run a pre-publication check on a draft</small></span><b>→</b></Link>}
                {links.some((link) => link.href === "/insights") && <Link href="/insights" className="attention-link"><span className="attention-icon">◫</span><span><strong>Governance insights</strong><small>Review guideline health and fact drift</small></span><b>→</b></Link>}
                <div className="attention-foot">AI explains and suggests. People make the final decision.</div>
              </section>
            </aside>
          </div>
          <footer className="app-footer"><span>Brandwright</span><span>AI explains and suggests. Humans decide.</span></footer>
        </div>
      </div>
    </UserContext.Provider>
  );
}
