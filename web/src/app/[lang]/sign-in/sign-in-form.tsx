"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import type { Dictionary } from "@/i18n";
import { getSupabase } from "@/lib/supabase";

type T = Dictionary["auth"];
type Mode = "signIn" | "signUp";

function friendlyError(message: string, t: T): string {
  const m = message.toLowerCase();
  if (m.includes("invalid login")) return t.errorInvalid;
  if (m.includes("already registered") || m.includes("already exists")) return t.errorExists;
  if (m.includes("password") && (m.includes("least") || m.includes("short") || m.includes("weak"))) return t.errorWeak;
  if (m.includes("not confirmed")) return t.errorConfirm;
  return t.errorGeneric;
}

const input =
  "min-h-12 w-full rounded-control border-2 border-line bg-surface px-3 text-base text-ink focus:border-forest focus:outline-none";

export function SignInForm({ lang, t }: { lang: string; t: T }) {
  const router = useRouter();
  const search = useSearchParams();
  const supabase = getSupabase();
  const [mode, setMode] = useState<Mode>("signIn");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  if (!supabase) {
    return <p className="rounded-2xl bg-thin-soft p-4 text-thin">{t.notConfigured}</p>;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!supabase) return;
    setError(null);
    if (mode === "signUp" && password.length < 8) return setError(t.errorWeak);
    setBusy(true);
    try {
      if (mode === "signIn") {
        const { error: err } = await supabase.auth.signInWithPassword({ email, password });
        if (err) return setError(friendlyError(err.message, t));
        const next = search.get("next");
        router.replace(next && next.startsWith(`/${lang}`) ? next : `/${lang}`);
      } else {
        const { data, error: err } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: name.trim() || undefined }, emailRedirectTo: `${window.location.origin}/${lang}/sign-in` },
        });
        if (err) return setError(friendlyError(err.message, t));
        if (data.session) router.replace(`/${lang}`);
        else setSentTo(email);
      }
    } finally {
      setBusy(false);
    }
  }

  if (sentTo) {
    return (
      <section className="flex flex-col gap-2 rounded-card bg-forest-soft p-5" role="status">
        <h2 className="text-lg font-extrabold text-forest-dark">{t.checkEmailTitle}</h2>
        <p className="text-base text-forest-dark">{t.checkEmailText.replace("{email}", sentTo)}</p>
      </section>
    );
  }

  const tab = (m: Mode, label: string) => (
    <button
      type="button"
      onClick={() => { setMode(m); setError(null); }}
      aria-pressed={mode === m}
      className={`min-h-11 flex-1 rounded-full text-[15px] font-bold ${mode === m ? "bg-forest text-white" : "text-ink"}`}
    >
      {label}
    </button>
  );

  return (
    <form onSubmit={submit} className="flex flex-col gap-4 rounded-card bg-surface p-5" noValidate>
      <div className="flex rounded-full bg-[#e9e1d1] p-[3px]" role="group">
        {tab("signIn", t.signInTab)}
        {tab("signUp", t.signUpTab)}
      </div>

      {mode === "signUp" && (
        <label className="flex flex-col gap-1.5 text-[15px] font-bold">
          {t.name}
          <input className={input} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={80} />
        </label>
      )}
      <label className="flex flex-col gap-1.5 text-[15px] font-bold">
        {t.email}
        <input className={input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required inputMode="email" />
      </label>
      <label className="flex flex-col gap-1.5 text-[15px] font-bold">
        {t.password}
        <span className="flex gap-2">
          <input
            className={input}
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "signIn" ? "current-password" : "new-password"}
            minLength={mode === "signUp" ? 8 : undefined}
            required
            aria-describedby={mode === "signUp" ? "password-hint" : undefined}
          />
          <button type="button" onClick={() => setShowPassword((s) => !s)} className="min-h-12 shrink-0 rounded-control border-2 border-line px-3 text-[15px] font-semibold">
            {showPassword ? t.hide : t.show}
          </button>
        </span>
        {mode === "signUp" && <span id="password-hint" className="text-sm font-normal text-muted">{t.passwordHint}</span>}
      </label>

      {error && <p role="alert" className="rounded-xl bg-thin-soft px-3 py-2 text-[15px] text-thin">{error}</p>}

      <button
        type="submit"
        disabled={busy || !email || !password}
        className="min-h-14 rounded-control bg-forest text-lg font-bold text-white hover:bg-forest-dark disabled:opacity-60"
      >
        {busy ? t.working : mode === "signIn" ? t.submitSignIn : t.submitSignUp}
      </button>
      <p className="text-sm text-muted">{t.phoneLater}</p>
    </form>
  );
}
