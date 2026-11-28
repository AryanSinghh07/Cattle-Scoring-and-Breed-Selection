import { notFound } from "next/navigation";
import { Suspense } from "react";
import { getDictionary, hasLocale } from "@/i18n";
import { SignInForm } from "./sign-in-form";

export default async function SignInPage({ params }: PageProps<"/[lang]/sign-in">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const t = (await getDictionary(lang)).auth;
  return (
    <>
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-extrabold">{t.signInTitle}</h1>
        <p className="text-base text-muted">{t.intro}</p>
      </div>
      <Suspense>
        <SignInForm lang={lang} t={t} />
      </Suspense>
    </>
  );
}
