"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type Labels = { main: string; home: string; analyze: string; breeds: string; reminders: string; help: string };

/** Navigation links in the header on tablets and PCs (the phone uses the bottom bar). */
export function DesktopNav({ lang, labels }: { lang: string; labels: Labels }) {
  const pathname = usePathname() || `/${lang}`;
  const items = [
    { href: `/${lang}`, label: labels.home, exact: true },
    { href: `/${lang}/analyze`, label: labels.analyze },
    { href: `/${lang}/breeds`, label: labels.breeds },
    { href: `/${lang}/reminders`, label: labels.reminders },
    { href: `/${lang}/help`, label: labels.help },
  ];
  return (
    <nav aria-label={labels.main} className="hidden items-center gap-1 md:flex">
      {items.map(({ href, label, exact }) => {
        const active = exact ? pathname === href : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`rounded-full px-4 py-2 text-[16px] no-underline transition-colors ${
              active ? "bg-forest-soft font-bold text-forest-dark" : "font-semibold text-ink hover:bg-[#ece4d4]"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
