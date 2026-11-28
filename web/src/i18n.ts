import "server-only";

export const locales = ["en", "hi"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";

const dictionaries = {
  en: () => import("./dictionaries/en.json").then((m) => m.default),
  hi: () => import("./dictionaries/hi.json").then((m) => m.default),
};

export type Dictionary = Awaited<ReturnType<(typeof dictionaries)["en"]>>;

export const hasLocale = (value: string): value is Locale =>
  (locales as readonly string[]).includes(value);

export const getDictionary = async (locale: Locale): Promise<Dictionary> => dictionaries[locale]();
