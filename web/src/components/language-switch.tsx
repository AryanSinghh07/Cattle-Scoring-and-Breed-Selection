"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LANGS = [
  { code: "en", label: "EN", name: "English" },
  { code: "hi", label: "हिं", name: "हिन्दी" },
] as const;

/** EN / हिं pill. Keeps the current page and remembers the choice in a cookie. */
export function LanguageSwitch({ current, label }: { current: string; label: string }) {
  const pathname = usePathname() || `/${current}`;
  const rest = pathname.replace(/^\/(en|hi)(?=\/|$)/, "");

  return (
    <nav aria-label={label} className="flex rounded-full bg-[#e9e1d1] p-[3px]">
      {LANGS.map((l) => {
        const active = l.code === current;
        return (
          <Link
            key={l.code}
            href={`/${l.code}${rest}`}
            hrefLang={l.code}
            lang={l.code}
            aria-label={l.name}
            aria-current={active ? "true" : undefined}
            onClick={() => {
              document.cookie = `lang=${l.code}; path=/; max-age=31536000; samesite=lax`;
            }}
            className={`flex min-h-10 min-w-12 items-center justify-center rounded-full px-3 text-[15px] font-bold ${
              active ? "bg-forest text-white" : "text-ink"
            }`}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
