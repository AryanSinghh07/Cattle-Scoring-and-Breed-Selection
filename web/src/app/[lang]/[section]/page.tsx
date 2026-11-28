import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeftIcon } from "@/components/icons";
import { Narrow } from "@/components/narrow";
import { getDictionary, hasLocale, locales } from "@/i18n";

/**
 * Placeholder pages for sections that later v3 issues build.
 * Each section is replaced by its own route as it is implemented.
 */
const SECTIONS = {
  analyze: { en: "Analyze", hi: "जाँच", issue: 31 },
  reminders: { en: "Reminders", hi: "रिमाइंडर", issue: 34 },
  help: { en: "Help & support", hi: "मदद और सहायता", issue: 35 },
  breeds: { en: "Breed guide", hi: "नस्ल गाइड", issue: 37 },
  health: { en: "Health help", hi: "स्वास्थ्य सहायता", issue: 37 },
  guide: { en: "Photo guide", hi: "फ़ोटो गाइड", issue: 37 },
  marker: { en: "Print the marker", hi: "मार्कर प्रिंट करें", issue: 31 },
} as const;

type Section = keyof typeof SECTIONS;

export function generateStaticParams() {
  return locales.flatMap((lang) => Object.keys(SECTIONS).map((section) => ({ lang, section })));
}

export default async function ComingSoon({ params }: PageProps<"/[lang]/[section]">) {
  const { lang, section } = await params;
  if (!hasLocale(lang) || !(section in SECTIONS)) notFound();
  const t = await getDictionary(lang);
  const s = SECTIONS[section as Section];

  return (
    <Narrow>
    <section className="flex flex-col gap-3 rounded-card bg-surface p-5 md:p-8">
      <span className="self-start rounded-full bg-soil-soft px-3 py-0.5 text-[13px] font-bold text-soil">{t.common.comingSoon}</span>
      <h1 className="text-2xl font-extrabold">{s[lang]}</h1>
      <p className="text-base text-muted">{t.common.comingSoonText}</p>
      <Link href={`/${lang}`} className="mt-2 flex min-h-12 items-center gap-2 font-bold text-forest">
        <ArrowLeftIcon size={20} />
        {t.common.backHome}
      </Link>
    </section>
    </Narrow>
  );
}
