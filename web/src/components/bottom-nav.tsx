"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BellIcon, CameraIcon, HelpIcon, HomeIcon } from "./icons";

type Labels = { main: string; home: string; analyze: string; reminders: string; help: string };

export function BottomNav({ lang, labels }: { lang: string; labels: Labels }) {
  const pathname = usePathname() || `/${lang}`;
  const items = [
    { href: `/${lang}`, label: labels.home, Icon: HomeIcon, exact: true },
    { href: `/${lang}/analyze`, label: labels.analyze, Icon: CameraIcon },
    { href: `/${lang}/reminders`, label: labels.reminders, Icon: BellIcon },
    { href: `/${lang}/help`, label: labels.help, Icon: HelpIcon },
  ];

  return (
    <nav
      aria-label={labels.main}
      className="sticky bottom-0 z-10 grid grid-cols-4 border-t border-line bg-surface px-1 pb-[max(10px,env(safe-area-inset-bottom))] pt-1.5"
    >
      {items.map(({ href, label, Icon, exact }) => {
        const active = exact ? pathname === href : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex min-h-13 flex-col items-center justify-center gap-0.5 text-[13px] ${
              active ? "font-bold text-forest" : "font-semibold text-muted"
            }`}
          >
            <Icon />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
