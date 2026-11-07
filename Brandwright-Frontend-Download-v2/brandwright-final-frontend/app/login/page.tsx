
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, tk } from "@/lib/api";

export default function Login() {
  const r = useRouter();

  const [email, setE] = useState("");
  const [pw, setP] = useState("");
  const [err, setErr] = useState("");
  const [busy, setB] = useState(false);

  async function go(ev: React.FormEvent) {
    ev.preventDefault();
    setB(true);
    setErr("");

    try {
      const result = await api.login(email, pw);
      tk.set(result.access_token);
      r.replace("/workspace");
    } catch (e) {
      setErr((e as Error).message);
      setB(false);
    }
  }

  async function exploreAsJury() {
    setB(true);
    setErr("");

    try {
      const result = await api.juryDemoLogin();
      tk.set(result.access_token);
      r.replace("/workspace");
    } catch (e) {
      setErr((e as Error).message);
      setB(false);
    }
  }

  return (
    <main style={{ maxWidth: 420, marginTop: "10vh" }}>
      <form className="pn" onSubmit={go}>
        <h1>Brandwright</h1>

        <p className="mu">
          Check every claim before it is published. AI explains and suggests.
          Humans decide.
        </p>

        <label htmlFor="e">Work email</label>
        <input
          id="e"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(x) => setE(x.target.value)}
        />

        <label htmlFor="p">Password</label>
        <input
          id="p"
          type="password"
          autoComplete="current-password"
          required
          value={pw}
          onChange={(x) => setP(x.target.value)}
        />

        {err && <p className="err" role="alert">{err}</p>}

        <p>
          <button className="btn pr" type="submit" disabled={busy}>
            {busy ? "Please wait..." : "Sign in"}
          </button>
        </p>

        <div style={{ textAlign: "center", margin: "18px 0" }}>
          <span className="mu">OR</span>
        </div>

        <button
          className="btn pr"
          type="button"
          disabled={busy}
          onClick={exploreAsJury}
          style={{ width: "100%" }}
        >
          {busy ? "Please wait..." : "Explore as Jury"}
        </button>
      </form>
    </main>
  );
}
