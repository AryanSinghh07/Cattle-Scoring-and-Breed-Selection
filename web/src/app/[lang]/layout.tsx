import type { Metadata, Viewport } from "next";
import { Mukta } from "next/font/google";
import Link from "next/link";
import { notFound } from "next/navigation";
import "../globals.css";
import { AccountButton } from "@/components/account-button";
import { BottomNav } from "@/components/bottom-nav";
import { DesktopNav } from "@/components/desktop-nav";
import { LeafIcon } from "@/components/icons";
import { LanguageSwitch } from "@/components/language-switch";
import { SiteFooter } from "@/components/site-footer";
import { getDictionary, hasLocale, locales } from "@/i18n";
import { SessionProvider } from "@/lib/session";

const mukta = Mukta({
  subsets: ["latin", "devanagari"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-mukta",
  display: "swap",
});

// Only /en and /hi exist; anything else hits notFound() below.
export function generateStaticParams() {
  return locales.map((lang) => ({ lang }));
}

export async function generateMetadata({ params }: LayoutProps<"/[lang]">): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const t = await getDictionary(lang);
  return {
    title: t.meta.title,
    description: t.meta.description,
    alternates: { languages: { en: "/en", hi: "/hi" } },
  };
}

export const viewport: Viewport = {
  themeColor: "#2f5d3a",
  width: "device-width",
  initialScale: 1,
};

export default async function LangLayout({ children, params }: LayoutProps<"/[lang]">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const t = await getDictionary(lang);

  return (
    <html lang={lang} className={`${mukta.variable} h-full antialiased`}>
      <body className="flex min-h-dvh flex-col">
        <SessionProvider>
          <header className="sticky top-0 z-20 print:hidden border-b border-transparent bg-ground/90 backdrop-blur md:border-line">
            <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3 md:px-8">
              <Link href={`/${lang}`} className="flex items-center gap-2.5 text-ink no-underline">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-forest text-ground">
                  <LeafIcon />
                </span>
                <span className="text-xl font-extrabold tracking-tight">{t.common.appName}</span>
              </Link>
              <DesktopNav lang={lang} labels={t.nav} />
              <div className="flex items-center gap-2">
                <LanguageSwitch current={lang} label={t.common.language} />
                <AccountButton lang={lang} labels={{ account: t.auth.account, signIn: t.auth.signInTitle }} />
              </div>
            </div>
          </header>

          <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 px-4 pb-5 pt-1 md:px-8 md:pt-8">{children}</main>

          <SiteFooter lang={lang} t={t} />
          <div className="md:hidden print:hidden">
            <BottomNav lang={lang} labels={t.nav} />
          </div>
        </SessionProvider>
      </body>
    </html>
  );
}
