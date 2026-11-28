"use client";

import Link from "next/link";
import { useSession } from "@/lib/session";

/** Header button: account page when signed in, sign-in page otherwise. */
export function AccountButton({ lang, labels }: { lang: string; labels: { account: string; signIn: string } }) {
  const { session, configured } = useSession();
  if (!configured || session === undefined) return <span className="h-11 w-11" aria-hidden="true" />;
  const signedIn = !!session;
  const initial = (session?.user.email ?? "?").slice(0, 1).toUpperCase();
  return (
    <Link
      href={signedIn ? `/${lang}/account` : `/${lang}/sign-in`}
      aria-label={signedIn ? labels.account : labels.signIn}
      className="flex h-11 w-11 items-center justify-center rounded-full border-2 border-line bg-surface text-base font-extrabold text-forest no-underline"
    >
      {signedIn ? (
        initial
      ) : (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" />
        </svg>
      )}
    </Link>
  );
}
