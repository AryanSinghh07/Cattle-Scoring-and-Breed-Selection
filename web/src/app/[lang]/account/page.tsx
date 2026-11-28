import { notFound } from "next/navigation";
import { getDictionary, hasLocale } from "@/i18n";
import { AccountView } from "./account-view";

export default async function AccountPage({ params }: PageProps<"/[lang]/account">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const t = (await getDictionary(lang)).auth;
  return (
    <>
      <h1 className="text-2xl font-extrabold">{t.account}</h1>
      <AccountView lang={lang} t={t} />
    </>
  );
}
