"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { fetchToken, loginWithEmailPassword, setToken } from "@/lib/api";
import { AvanzaBrandLogo } from "@/components/avanza-brand-logo";
import { getSupabase, isSupabaseConfigured } from "@/lib/supabase";

export default function LoginPage() {
  const r = useRouter();
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const hasSupabase = isSupabaseConfigured();

  async function signInSupabase(e: React.FormEvent) {
    e.preventDefault();
    const sb = getSupabase();
    if (!sb) return;
    setLoading(true);
    setErr(null);
    try {
      const { data, error } = await sb.auth.signInWithPassword({ email, password });
      if (error) throw error;
      const access = data.session?.access_token;
      if (!access) throw new Error("No session from Supabase");
      setToken(access);
      r.push("/dashboard");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  async function signInLocal(e?: React.FormEvent) {
    e?.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      const t = await fetchToken();
      setToken(t);
      r.push("/dashboard");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  async function signInLocalEmail(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      await loginWithEmailPassword(email, password);
      r.push("/dashboard");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-avbg px-4">
      <div className="w-full max-w-sm rounded border border-avline bg-slate-900/50 p-6">
        <div className="mb-6 flex flex-col items-center text-center">
          <AvanzaBrandLogo size="md" centered />
          <div className="mt-2 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
            ME AI
          </div>
          <div className="mt-2 max-w-xs text-[10px] font-medium normal-case tracking-normal text-slate-500">
            API Health & SLA Monitor with AI Incident Summarizer
          </div>
        </div>
        <h1 className="text-base font-medium text-slate-200">Sign In</h1>
        <p className="mt-1 text-xs text-slate-500">
          Sign in to your account to continue.
        </p>

        {hasSupabase ? (
          <form onSubmit={signInSupabase} className="mt-4 space-y-2">
            <input
              type="email"
              required
              autoComplete="email"
              placeholder="Email"
              className="w-full rounded border border-avline bg-slate-950/60 px-2 py-1.5 text-sm text-slate-200"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <input
              type="password"
              required
              autoComplete="current-password"
              placeholder="Password"
              className="w-full rounded border border-avline bg-slate-950/60 px-2 py-1.5 text-sm text-slate-200"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded bg-blue-600 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {loading ? "…" : "Sign in"}
            </button>
          </form>
        ) : (
          <>
            <p className="mt-2 text-xs text-slate-500">
              With the local SQLite API, use the seeded demo account (same email/password as
              Supabase after you create the user there), or a token below.
            </p>
            <form onSubmit={signInLocalEmail} className="mt-4 space-y-2">
              <input
                type="email"
                required
                autoComplete="email"
                placeholder="Email"
                className="w-full rounded border border-avline bg-slate-950/60 px-2 py-1.5 text-sm text-slate-200"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <input
                type="password"
                required
                autoComplete="current-password"
                placeholder="Password"
                className="w-full rounded border border-avline bg-slate-950/60 px-2 py-1.5 text-sm text-slate-200"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded bg-blue-600 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {loading ? "…" : "Sign in (local SQLite user)"}
              </button>
            </form>
            <p className="mt-3 text-xs text-slate-600">
              Set <code className="text-slate-400">NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
              <code className="text-slate-400">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> to use
              cloud Auth instead. The backend must have{" "}
              <code className="text-slate-400">SUPABASE_JWT_SECRET</code> for JWT verification.
            </p>
          </>
        )}

        <div className="my-4 border-t border-avline pt-4 text-center text-xs text-slate-500">
          Or continue without a password
        </div>
        <button
          type="button"
          disabled={loading}
          onClick={() => void signInLocal()}
          className="w-full rounded border border-slate-600 bg-slate-800 py-2 text-sm font-semibold text-slate-200 disabled:opacity-50"
        >
          {loading ? "…" : "Continue with local JWT (no password)"}
        </button>
        {err && <p className="mt-2 text-xs text-rose-400">{err}</p>}
        <p className="mt-4 text-center text-xs text-slate-600">
          <Link href="/dashboard" className="text-blue-400 hover:underline">
            Skip to dashboard
          </Link>{" "}
          (auto-fetches token if needed)
        </p>
      </div>
    </div>
  );
}
