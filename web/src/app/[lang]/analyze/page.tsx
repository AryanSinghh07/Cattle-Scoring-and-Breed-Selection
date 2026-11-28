import { notFound } from "next/navigation";
import { getDictionary, hasLocale } from "@/i18n";
import { AnalyzeFlow } from "./analyze-flow";

export default async function AnalyzePage({ params }: PageProps<"/[lang]/analyze">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const t = (await getDictionary(lang)).analyze;
  return <AnalyzeFlow lang={lang} t={t} />;
}
