"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { ArrowRight, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, errText, tk } from "@/lib/api";

const credentialsSchema = z.object({
  email: z.string().trim().min(1, "Enter your email."),
  password: z.string().min(1, "Enter your password."),
});

export default function Login() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function completeSignIn(accessToken: string, juryDemo = false) {
    queryClient.clear();
    tk.set(accessToken);
    const profile = await api.me();
    router.replace(juryDemo ? "/workspace" : profile.role === "creator" ? "/dashboard" : profile.role === "reviewer" ? "/queue" : "/insights");
  }

  async function exploreAsJury() {
    setBusy(true);
    setError("");
    try {
      const result = await api.juryDemoLogin();
      await completeSignIn(result.access_token, true);
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 404 ? "Jury demo access is not currently enabled." : errText(cause));
    } finally {
      setBusy(false);
    }
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
          <h2 id="login-title">Welcome to Brandwright</h2>
          <p className="mu">Sign in with your account, or explore the demo without credentials.</p>
          <button type="button" className="button primary jury-demo-entry" disabled={busy} onClick={() => void exploreAsJury()}>
            <ShieldCheck size={17} aria-hidden="true" />
            {busy ? "Opening jury demo..." : "Explore as Jury"}
          </button>
          <p className="jury-demo-note">No registration needed. Explore safely with fictional sample data.</p>
          <div className="login-divider" aria-hidden="true"><span>or sign in</span></div>
          <label htmlFor="e">Email</label>
          <input
            id="e"
            type="text"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            aria-describedby={error ? "login-error" : undefined}
          />
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
          {error && <p className="err" id="login-error" role="alert">{error}</p>}
          <button className="button primary" disabled={busy}>
            {busy ? "Signing in..." : "Enter workspace"}
            {!busy && <ArrowRight size={16} aria-hidden="true" />}
          </button>
          <p className="demo-login-note">Demo workspace with sample data only.</p>
        </form>
      </section>
    </main>
  );
}
