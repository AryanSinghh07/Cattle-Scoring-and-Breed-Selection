import Link from "next/link";
import type { Dictionary } from "@/i18n";
import { LeafIcon } from "./icons";

/** Footer on tablets and PCs. */
export function SiteFooter({ lang, t }: { lang: string; t: Dictionary }) {
  const col = "flex flex-col gap-2";
  const link = "text-[15px] text-ground/85 no-underline hover:text-white";
  return (
    <footer className="mt-12 hidden bg-forest-dark text-ground md:block print:hidden">
      <div className="mx-auto grid max-w-6xl grid-cols-[2fr_1fr_1fr] gap-10 px-8 py-12">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-ground text-forest-dark">
              <LeafIcon />
            </span>
            <span className="text-xl font-extrabold">{t.common.appName}</span>
          </div>
          <p className="max-w-sm text-[15px] leading-relaxed text-ground/85">{t.footer.tagline}</p>
          <p className="text-sm text-ground/70">{t.footer.note}</p>
        </div>
        <div className={col}>
          <h2 className="mb-1 text-sm font-bold uppercase tracking-wide text-ground/70">{t.footer.app}</h2>
          <Link className={link} href={`/${lang}/analyze`}>{t.nav.analyze}</Link>
          <Link className={link} href={`/${lang}/reminders`}>{t.nav.reminders}</Link>
          <Link className={link} href={`/${lang}/help`}>{t.nav.help}</Link>
          <Link className={link} href={`/${lang}/sign-in`}>{t.auth.signInTitle}</Link>
        </div>
        <div className={col}>
          <h2 className="mb-1 text-sm font-bold uppercase tracking-wide text-ground/70">{t.footer.learn}</h2>
          <Link className={link} href={`/${lang}/breeds`}>{t.home.breedGuide}</Link>
          <Link className={link} href={`/${lang}/health`}>{t.home.healthHelp}</Link>
          <Link className={link} href={`/${lang}/guide`}>{t.home.photoGuide}</Link>
          <Link className={link} href={`/${lang}/marker`}>{t.home.printMarker}</Link>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-8 py-4 text-sm text-ground/70">
          <span>{t.footer.rights}</span>
          <span>
            <Link className={link} href="/en" hrefLang="en" lang="en">English</Link>
            {" · "}
            <Link className={link} href="/hi" hrefLang="hi" lang="hi">हिन्दी</Link>
          </span>
        </div>
      </div>
    </footer>
  );
}
