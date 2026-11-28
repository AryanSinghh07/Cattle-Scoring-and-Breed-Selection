import { NextResponse, type NextRequest } from "next/server";

const LOCALES = ["en", "hi"];

/** Pick the language: saved choice (cookie) first, then the browser's preference. */
function pickLocale(request: NextRequest): string {
  const saved = request.cookies.get("lang")?.value;
  if (saved && LOCALES.includes(saved)) return saved;
  const accepted = request.headers.get("accept-language") ?? "";
  const hindiFirst = accepted
    .split(",")
    .map((part) => part.split(";")[0].trim().toLowerCase())
    .find((code) => code.startsWith("hi") || code.startsWith("en"));
  return hindiFirst?.startsWith("hi") ? "hi" : "en";
}

/** Redirect paths without a language prefix (e.g. "/" → "/hi"). */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (LOCALES.some((l) => pathname === `/${l}` || pathname.startsWith(`/${l}/`))) return;
  const url = request.nextUrl.clone();
  url.pathname = `/${pickLocale(request)}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Skip Next internals, files with an extension (images, manifest, icons) and API routes.
  matcher: ["/((?!_next|api|.*\\..*).*)"],
};
