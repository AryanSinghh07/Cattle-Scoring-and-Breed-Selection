import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowRightIcon,
  BellIcon,
  BookIcon,
  CameraIcon,
  CheckIcon,
  CowIcon,
  GaugeIcon,
  HeartIcon,
  LeafIcon,
  MarkerIcon,
  PhotoIcon,
  PointsIcon,
} from "@/components/icons";
import { getDictionary, hasLocale } from "@/i18n";
import cowPhoto from "../../../public/images/red-sindhi.jpg";

// Real output of the v2 detector on this photo (percent of width/height; orange = "please check").
const POINTS = [
  { x: 9.2, y: 23.2, check: false },
  { x: 52.8, y: 17.2, check: false },
  { x: 52.8, y: 61.5, check: false },
  { x: 88.5, y: 85.2, check: false },
  { x: 33.6, y: 77.2, check: true },
  { x: 33.6, y: 92.8, check: false },
  { x: 36.9, y: 31.6, check: true },
  { x: 52.8, y: 53.0, check: true },
];

export default async function Home({ params }: PageProps<"/[lang]">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const t = (await getDictionary(lang)).home;

  const steps = [
    { title: t.step1Title, text: t.step1Text, Icon: CameraIcon },
    { title: t.step2Title, text: t.step2Text, Icon: PointsIcon },
    { title: t.step3Title, text: t.step3Text, Icon: GaugeIcon },
  ];
  const features = [
    { title: t.f1Title, text: t.f1Text, Icon: GaugeIcon, tint: "bg-forest-soft text-forest", soon: false },
    { title: t.f2Title, text: t.f2Text, Icon: CowIcon, tint: "bg-soil-soft text-soil", soon: false },
    { title: t.f3Title, text: t.f3Text, Icon: LeafIcon, tint: "bg-[#e3ecd9] text-[#3f6b2a]", soon: true },
    { title: t.f4Title, text: t.f4Text, Icon: BellIcon, tint: "bg-[#e3ecf5] text-[#1e4e79]", soon: true },
  ];
  const guides = [
    { href: `/${lang}/breeds`, label: t.breedGuide, Icon: BookIcon },
    { href: `/${lang}/health`, label: t.healthHelp, Icon: HeartIcon },
    { href: `/${lang}/guide`, label: t.photoGuide, Icon: PhotoIcon },
    { href: `/${lang}/marker`, label: t.printMarker, Icon: MarkerIcon },
  ];

  return (
    <div className="flex flex-col gap-12 md:gap-20">
      {/* Hero */}
      <section className="grid items-center gap-6 md:grid-cols-[1.05fr_1fr] md:gap-12">
        <div className="order-2 flex flex-col gap-4 md:order-1 md:gap-6">
          <span className="self-start rounded-full bg-soil-soft px-3.5 py-1 text-[13px] font-bold text-soil md:text-sm">{t.eyebrow}</span>
          <h1 className="text-[30px] font-extrabold leading-[1.1] tracking-tight md:text-5xl lg:text-[58px]">
            {t.heroTitleDesktop}
          </h1>
          <p className="max-w-xl text-base leading-relaxed text-muted md:text-lg">{t.heroLead}</p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link
              href={`/${lang}/analyze`}
              className="flex min-h-14 items-center justify-center gap-2.5 rounded-control bg-forest px-7 text-lg font-bold text-white no-underline shadow-[0_6px_20px_rgba(47,93,58,0.35)] transition hover:-translate-y-0.5 hover:bg-forest-dark"
            >
              <CameraIcon size={22} />
              {t.cta}
            </Link>
            <a
              href="#how"
              className="flex min-h-14 items-center justify-center gap-2 rounded-control border-2 border-line bg-surface px-6 text-lg font-bold text-ink no-underline transition hover:border-forest"
            >
              {t.howItWorksCta}
              <ArrowRightIcon size={20} />
            </a>
          </div>
          <ul className="flex flex-wrap gap-x-5 gap-y-2 text-[15px] font-semibold text-muted">
            {[t.trust1, t.trust2, t.trust3].map((item) => (
              <li key={item} className="flex items-center gap-1.5">
                <CheckIcon size={18} className="text-ok" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative order-1 md:order-2">
          <div aria-hidden="true" className="absolute -inset-3 -z-10 rounded-[32px] bg-gradient-to-br from-forest-soft to-soil-soft md:-inset-5" />
          <div className="relative overflow-hidden rounded-3xl shadow-[0_20px_50px_rgba(30,42,30,0.18)]">
            <Image src={cowPhoto} alt={t.exampleAlt} priority placeholder="blur" className="block h-auto w-full" sizes="(min-width: 768px) 50vw, 100vw" />
            <div aria-hidden="true" className="absolute left-[36.9%] top-[31.6%] h-[21.4%] w-[15.9%] rounded border-2 border-dashed border-check-dot" />
            {POINTS.map((p, i) => (
              <span
                key={i}
                aria-hidden="true"
                className={`absolute h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white shadow md:h-4 md:w-4 ${p.check ? "bg-check-dot" : "bg-ok"}`}
                style={{ left: `${p.x}%`, top: `${p.y}%` }}
              />
            ))}
          </div>
          <div className="absolute -bottom-6 left-3 hidden w-60 flex-col gap-2 rounded-2xl bg-surface p-4 shadow-[0_12px_30px_rgba(30,42,30,0.18)] sm:flex md:-left-8">
            <span className="text-[12px] font-bold uppercase tracking-wide text-muted">{t.exampleLabel}</span>
            <div className="flex items-baseline justify-between">
              <span className="text-sm text-muted">{t.exampleBcs}</span>
              <span className="text-2xl font-extrabold">2.5 <span className="text-base text-thin">{t.exampleThin}</span></span>
            </div>
            <div aria-hidden="true" className="relative mt-1 grid h-2 grid-cols-5 gap-0.5 overflow-hidden rounded-full">
              <span className="bg-[#c2410c]" /><span className="bg-check-dot" /><span className="bg-[#4d8b3f]" /><span className="bg-[#8fb36b]" /><span className="bg-[#a8a29e]" />
            </div>
          </div>
          <div className="absolute -top-4 right-3 hidden items-center gap-2 rounded-full bg-surface px-3.5 py-2 text-sm font-bold shadow-[0_8px_24px_rgba(30,42,30,0.15)] sm:flex md:-right-4">
            <PointsIcon size={18} className="text-forest" />
            {t.examplePoints}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="flex scroll-mt-24 flex-col gap-6">
        <div className="flex flex-col gap-1 text-center">
          <h2 className="text-[26px] font-extrabold md:text-4xl">{t.howTitle}</h2>
          <p className="text-base text-muted md:text-lg">{t.howText}</p>
        </div>
        <ol className="grid gap-4 md:grid-cols-3 md:gap-6">
          {steps.map(({ title, text, Icon }, i) => (
            <li key={title} className="relative flex flex-col gap-3 rounded-card bg-surface p-6 md:p-7">
              <span className="absolute right-5 top-4 text-5xl font-extrabold text-forest-soft" aria-hidden="true">{i + 1}</span>
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-forest text-white">
                <Icon size={24} />
              </span>
              <h3 className="text-xl font-bold">{title}</h3>
              <p className="text-[15px] leading-relaxed text-muted">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Features */}
      <section className="flex flex-col gap-6">
        <h2 className="text-center text-[26px] font-extrabold md:text-4xl">{t.featuresTitle}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {features.map(({ title, text, Icon, tint, soon }) => (
            <div key={title} className="flex flex-col gap-3 rounded-card border border-line bg-surface p-6 transition hover:-translate-y-0.5 hover:shadow-[0_12px_30px_rgba(30,42,30,0.10)]">
              <div className="flex items-start justify-between gap-2">
                <span className={`flex h-12 w-12 items-center justify-center rounded-2xl ${tint}`}>
                  <Icon size={24} />
                </span>
                {soon && <span className="rounded-full bg-soil-soft px-2.5 py-0.5 text-[12px] font-bold text-soil">{t.comingSoon}</span>}
              </div>
              <h3 className="text-lg font-bold">{title}</h3>
              <p className="text-[15px] leading-relaxed text-muted">{text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Guides */}
      <section aria-labelledby="guides" className="flex flex-col gap-4">
        <h2 id="guides" className="text-xl font-extrabold md:text-2xl">{t.guidesTitle}</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
          {guides.map(({ href, label, Icon }) => (
            <Link
              key={href}
              href={href}
              className="group flex min-h-[72px] items-center justify-between gap-2 rounded-2xl bg-surface p-4 text-base font-semibold text-ink no-underline transition hover:bg-forest-soft"
            >
              <span className="flex items-center gap-3">
                <Icon size={22} className="shrink-0 text-forest" />
                {label}
              </span>
              <ArrowRightIcon size={18} className="hidden text-muted transition group-hover:translate-x-0.5 md:block" />
            </Link>
          ))}
        </div>
      </section>

      {/* Sign-in banner */}
      <section className="relative overflow-hidden rounded-3xl bg-forest px-6 py-8 text-white md:px-12 md:py-12">
        <LeafIcon aria-hidden="true" size={220} className="absolute -right-10 -top-10 text-white/10" />
        <div className="relative flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
          <div className="flex max-w-xl flex-col gap-2">
            <h2 className="text-2xl font-extrabold md:text-3xl">{t.bannerTitle}</h2>
            <p className="text-base leading-relaxed text-white/85 md:text-lg">{t.bannerText}</p>
          </div>
          <Link
            href={`/${lang}/sign-in`}
            className="flex min-h-14 shrink-0 items-center justify-center rounded-control bg-white px-7 text-lg font-bold text-forest-dark no-underline transition hover:bg-ground"
          >
            {t.bannerCta}
          </Link>
        </div>
      </section>
    </div>
  );
}
