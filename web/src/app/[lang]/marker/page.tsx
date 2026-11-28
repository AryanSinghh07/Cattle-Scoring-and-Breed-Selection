import { notFound } from "next/navigation";
import { getDictionary, hasLocale } from "@/i18n";
import { MarkerSheet } from "./marker-sheet";

export default async function MarkerPage({ params }: PageProps<"/[lang]/marker">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const t = (await getDictionary(lang)).marker;
  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-2xl font-extrabold md:text-4xl print:hidden">{t.title}</h1>
      <MarkerSheet t={t} />
    </div>
  );
}
