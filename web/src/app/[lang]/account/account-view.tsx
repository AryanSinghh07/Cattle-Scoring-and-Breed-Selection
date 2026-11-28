"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { Dictionary } from "@/i18n";
import { useSession } from "@/lib/session";
import { getSupabase } from "@/lib/supabase";

type T = Dictionary["auth"];
type Profile = { full_name: string | null; phone: string | null; language: string; role: "farmer" | "reviewer" | "admin" };

const input =
  "min-h-12 w-full rounded-control border-2 border-line bg-surface px-3 text-base text-ink focus:border-forest focus:outline-none";

export function AccountView({ lang, t }: { lang: string; t: T }) {
  const router = useRouter();
  const { session } = useSession();
  const supabase = getSupabase();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  useEffect(() => {
    if (session === null) router.replace(`/${lang}/sign-in?next=/${lang}/account`);
    if (!session || !supabase) return;
    supabase
      .from("profiles")
      .select("full_name, phone, language, role")
      .eq("id", session.user.id)
      .single()
      .then(({ data }) => data && setProfile(data as Profile));
  }, [session, supabase, router, lang]);

  if (!session || !profile || !supabase) return <p className="text-muted">…</p>;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!supabase || !session || !profile) return;
    setStatus("saving");
    const { error } = await supabase
      .from("profiles")
      .update({ full_name: profile.full_name || null, phone: profile.phone || null, language: profile.language })
      .eq("id", session.user.id);
    setStatus(error ? "error" : "saved");
    if (!error && profile.language !== lang) {
      document.cookie = `lang=${profile.language}; path=/; max-age=31536000; samesite=lax`;
      router.replace(`/${profile.language}/account`);
    }
  }

  async function signOut() {
    await supabase?.auth.signOut();
    router.replace(`/${lang}`);
  }

  return (
    <>
      <section className="flex flex-col gap-1 rounded-card bg-surface p-5">
        <span className="text-sm text-muted">{t.signedInAs}</span>
        <span className="break-all text-lg font-bold">{session.user.email}</span>
        <span className="mt-1 self-start rounded-full bg-forest-soft px-3 py-0.5 text-[13px] font-bold text-forest-dark">
          {t.role}: {t.roles[profile.role]}
        </span>
      </section>

      <form onSubmit={save} className="flex flex-col gap-4 rounded-card bg-surface p-5">
        <h2 className="text-lg font-extrabold">{t.profile}</h2>
        <label className="flex flex-col gap-1.5 text-[15px] font-bold">
          {t.name}
          <input className={input} value={profile.full_name ?? ""} maxLength={80} autoComplete="name"
            onChange={(e) => { setProfile({ ...profile, full_name: e.target.value }); setStatus("idle"); }} />
        </label>
        <label className="flex flex-col gap-1.5 text-[15px] font-bold">
          {t.phone}
          <input className={input} type="tel" inputMode="tel" value={profile.phone ?? ""} maxLength={20} autoComplete="tel"
            onChange={(e) => { setProfile({ ...profile, phone: e.target.value }); setStatus("idle"); }} />
        </label>
        <label className="flex flex-col gap-1.5 text-[15px] font-bold">
          {t.language}
          <select className={input} value={profile.language}
            onChange={(e) => { setProfile({ ...profile, language: e.target.value }); setStatus("idle"); }}>
            <option value="en">English</option>
            <option value="hi">हिन्दी</option>
          </select>
        </label>
        {status === "error" && <p role="alert" className="text-thin">{t.errorGeneric}</p>}
        <button type="submit" disabled={status === "saving"} className="min-h-12 rounded-control bg-forest text-base font-bold text-white disabled:opacity-60">
          {status === "saved" ? t.saved : status === "saving" ? t.working : t.save}
        </button>
      </form>

      <button onClick={signOut} className="min-h-12 rounded-control border-2 border-line bg-surface text-base font-bold text-ink">
        {t.signOut}
      </button>
    </>
  );
}
