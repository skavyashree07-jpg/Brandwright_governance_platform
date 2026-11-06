"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { ArrowRight, Eye, EyeOff } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, api, errText, tk, type DemoRole } from "@/lib/api";

const credentialsSchema = z.object({
  email: z.string().trim().email("Enter a valid work email address."),
  password: z.string().min(1, "Enter your password."),
});

const demoRoles: Array<{ role: DemoRole; label: string; hint: string }> = [
  { role: "creator", label: "Continue as Creator", hint: "Submit drafts and resolve findings." },
  { role: "reviewer", label: "Continue as Reviewer", hint: "Review findings and decide." },
  { role: "admin", label: "Continue as Admin", hint: "Manage guidance and governance." },
];

export default function Login() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [forgotPassword, setForgotPassword] = useState(false);
  const [notice, setNotice] = useState("");
  const [demoRoleBusy, setDemoRoleBusy] = useState<DemoRole | null>(null);
  const [demoRetryRole, setDemoRetryRole] = useState<DemoRole | null>(null);
  const showDemoLogin = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

  async function completeSignIn(accessToken: string) {
    queryClient.clear();
    tk.set(accessToken);
    const profile = await api.me();
    router.replace(profile.role === "creator" ? "/dashboard" : profile.role === "reviewer" ? "/queue" : "/insights");
  }

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const credentials = credentialsSchema.safeParse({ email, password });
    if (!credentials.success) {
      setError(credentials.error.issues[0]?.message ?? "Check your sign-in details.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const result = await api.login(credentials.data.email, credentials.data.password);
      await completeSignIn(result.access_token);
    } catch (cause) {
      setError(errText(cause));
    } finally {
      setBusy(false);
    }
  }

  async function signInToDemo(role: DemoRole) {
    setBusy(true);
    setDemoRoleBusy(role);
    setDemoRetryRole(null);
    setError("");
    try {
      const result = await api.demoLogin(role);
      await completeSignIn(result.access_token);
    } catch (cause) {
      const timedOut = cause instanceof DOMException && cause.name === "TimeoutError";
      setError(timedOut
        ? "The demo server is waking up and took too long to respond. Please retry."
        : cause instanceof ApiError && cause.status === 404
          ? "Demo sign-in is not enabled on this deployment."
        : errText(cause));
      setDemoRetryRole(timedOut ? role : null);
    } finally {
      setBusy(false);
      setDemoRoleBusy(null);
    }
  }

  return (
    <main className="login-screen">
      <section className="login-story" aria-label="Brandwright principles">
        <Link href="/" className="login-wordmark" aria-label="Brandwright home">
          Brandwright<span>.</span>
        </Link>
        <div className="login-message">
          <h1>Keep your brand clear at every <em>approval.</em></h1>
          <p>Check content against approved guidance and facts, then give people the evidence to make the final call.</p>
        </div>
        <p className="login-principle">AI explains and suggests. People make the final decision.</p>
      </section>
      <section className="login-form-wrap" aria-labelledby="login-title">
        <form className="login-form" onSubmit={signIn} noValidate>
          <h2 id="login-title">{forgotPassword ? "Password help" : "Welcome back"}</h2>
          <p className="mu">{forgotPassword ? "Get help restoring access to your account." : "Sign in to your organisation workspace."}</p>
          {notice && <p className="alert" role="status">{notice}</p>}
          <label htmlFor="e">Work email</label>
          <input
            id="e"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            aria-describedby={error ? "login-error" : undefined}
          />
          {!forgotPassword && <>
            <label htmlFor="p">Password</label>
            <div className="login-password-field">
              <input
                id="p"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-describedby={error ? "login-error" : undefined}
              />
              <button type="button" className="login-password-toggle" disabled={busy} onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>
                {showPassword ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}
              </button>
            </div>
          </>}
          {error && <p className="err" id="login-error" role="alert">{error}</p>}
          {forgotPassword
            ? <div className="login-actions">
              <p className="mu">Password recovery is not available in this API. Ask your organisation admin to reset your access.</p>
              <button type="button" className="button primary" onClick={() => { setForgotPassword(false); setNotice(""); setError(""); }}>Back to sign in</button>
            </div>
            : <>
              <button className="button primary" disabled={busy}>
                {busy ? "Signing in..." : "Sign in"}
                {!busy && <ArrowRight size={16} aria-hidden="true" />}
              </button>
              <button type="button" className="login-text-button" disabled={busy} onClick={() => { setForgotPassword(true); setError(""); setNotice(""); }}>Forgot password?</button>
              <div className="login-divider"><span>or continue with</span></div>
              <div className="login-sso-actions">
                <button type="button" className="button secondary" disabled={busy} onClick={() => setNotice("Single sign-on is a placeholder. No SSO endpoint is configured.")}>Continue with Google</button>
                <button type="button" className="button secondary" disabled={busy} onClick={() => setNotice("Single sign-on is a placeholder. No SSO endpoint is configured.")}>Continue with Microsoft</button>
              </div>
            </>}
          {!forgotPassword && showDemoLogin && (
            <section className="demo-login" aria-labelledby="demo-login-title">
              <div className="login-divider"><span>or try the demo</span></div>
              <h3 id="demo-login-title">Choose a demo role</h3>
              <div className="demo-login-options">
                {demoRoles.map(({ role, label, hint }) => (
                  <button
                    key={role}
                    type="button"
                    className="demo-login-button"
                    disabled={busy}
                    aria-describedby={`demo-hint-${role}`}
                    onClick={() => signInToDemo(role)}
                  >
                    <span>{demoRoleBusy === role ? "Signing in..." : label}</span>
                    <span id={`demo-hint-${role}`} className="demo-login-hint">{hint}</span>
                  </button>
                ))}
              </div>
              {demoRetryRole && (
                <button
                  type="button"
                  className="login-text-button"
                  disabled={busy}
                  onClick={() => signInToDemo(demoRetryRole)}
                >
                  Retry demo sign-in
                </button>
              )}
              <p className="demo-login-note">Demo environment, sample data only.</p>
            </section>
          )}
        </form>
      </section>
    </main>
  );
}
