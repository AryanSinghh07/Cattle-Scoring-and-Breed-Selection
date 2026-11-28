import type { Metadata, Viewport } from "next";
import { Mukta } from "next/font/google";
import Link from "next/link";
import { notFound } from "next/navigation";
import "../globals.css";
import { BottomNav } from "@/components/bottom-nav";
import { LeafIcon } from "@/components/icons";
import { LanguageSwitch } from "@/components/language-switch";
import { getDictionary, hasLocale, locales } from "@/i18n";

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
        <div className="mx-auto flex w-full max-w-xl flex-1 flex-col">
          <header className="flex items-center justify-between px-4 py-3.5">
            <Link href={`/${lang}`} className="flex items-center gap-2.5 text-ink no-underline">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-forest text-ground">
                <LeafIcon />
              </span>
              <span className="text-xl font-extrabold tracking-tight">{t.common.appName}</span>
            </Link>
            <LanguageSwitch current={lang} label={t.common.language} />
          </header>
          <main className="flex flex-1 flex-col gap-4 px-4 pb-5">{children}</main>
          <BottomNav lang={lang} labels={t.nav} />
        </div>
      </body>
    </html>
  );
}
