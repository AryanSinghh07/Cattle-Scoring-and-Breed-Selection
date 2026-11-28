import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BookIcon, CameraIcon, HeartIcon, MarkerIcon, PhotoIcon } from "@/components/icons";
import { getDictionary, hasLocale } from "@/i18n";
import hero from "../../../public/images/cattle.jpg";

export default async function Home({ params }: PageProps<"/[lang]">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const t = (await getDictionary(lang)).home;

  const quick = [
    { href: `/${lang}/breeds`, label: t.breedGuide, Icon: BookIcon },
    { href: `/${lang}/health`, label: t.healthHelp, Icon: HeartIcon },
    { href: `/${lang}/guide`, label: t.photoGuide, Icon: PhotoIcon },
    { href: `/${lang}/marker`, label: t.printMarker, Icon: MarkerIcon },
  ];

  return (
    <>
      <section className="overflow-hidden rounded-card bg-surface shadow-[0_1px_2px_rgba(30,42,30,0.08)]">
        <Image src={hero} alt={t.heroAlt} priority placeholder="blur" className="h-44 w-full object-cover" sizes="(max-width: 576px) 100vw, 576px" />
        <div className="flex flex-col gap-2.5 p-4 pt-4 sm:p-5">
          <h1 className="text-[26px] font-extrabold leading-tight">{t.heroTitle}</h1>
          <p className="text-base leading-snug text-muted">{t.heroText}</p>
          <Link
            href={`/${lang}/analyze`}
            className="mt-1 flex min-h-14 items-center justify-center gap-2.5 rounded-control bg-forest text-lg font-bold text-white no-underline hover:bg-forest-dark"
          >
            <CameraIcon size={22} />
            {t.cta}
          </Link>
        </div>
      </section>

      <section className="flex flex-col gap-2 rounded-card bg-surface p-4">
        <h2 className="text-[19px] font-bold">{t.signInTitle}</h2>
        <p className="text-[15px] leading-snug text-muted">{t.signInText}</p>
        <Link
          href={`/${lang}/sign-in`}
          className="flex min-h-12 items-center justify-center rounded-control border-2 border-forest text-base font-bold text-forest no-underline"
        >
          {t.signIn}
        </Link>
      </section>

      <section aria-labelledby="quick-links" className="flex flex-col gap-2.5">
        <h2 id="quick-links" className="sr-only">{t.quickLinks}</h2>
        <div className="grid grid-cols-2 gap-2.5">
          {quick.map(({ href, label, Icon }) => (
            <Link
              key={href}
              href={href}
              className="flex min-h-[72px] flex-col gap-1.5 rounded-2xl bg-surface p-3.5 text-base font-semibold text-ink no-underline"
            >
              <Icon size={22} className="text-forest" />
              {label}
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
