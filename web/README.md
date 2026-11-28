# Gopalan AI — web app (v3)

The new website, built from the approved v3 mockups. It replaces the v1 site
in `../src/` at launch; until then both exist side by side.

- **Next.js 16** (App Router, TypeScript), **Tailwind CSS 4**
- **Style A** (earthy & trustworthy): tokens in [`src/app/globals.css`](src/app/globals.css),
  font **Mukta** (Latin + Devanagari)
- **English + Hindi**: every page lives under `/en/…` and `/hi/…`
- **Installable** web app (manifest + icons)
- Talks to the v2 API ([`../api`](../api)) and Supabase ([`../supabase`](../supabase))

## Run locally

```bash
cd web
npm install
cp .env.example .env.local   # Windows: copy .env.example .env.local
npm run dev
```

Open http://localhost:3000. You're redirected to `/en` or `/hi`.

| Command | What it does |
|---|---|
| `npm run dev` | Development server |
| `npm run build` | Production build |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript check |

## Languages

- Texts live in [`src/dictionaries/en.json`](src/dictionaries/en.json) and
  [`hi.json`](src/dictionaries/hi.json) with the same keys. Add a key to both.
- [`src/proxy.ts`](src/proxy.ts) sends `/` and any path without a language to
  `/en/…` or `/hi/…`: the saved choice (cookie `lang`) first, then the
  browser's language.
- The EN / हिं switch in the header keeps the current page.

## Structure

```
src/
  app/
    [lang]/layout.tsx      header, language switch, bottom navigation
    [lang]/page.tsx        Home
    [lang]/[section]/      "coming soon" pages, replaced as v3 issues land
    manifest.ts            installable app
    icon.png, apple-icon.png
  components/              icons, language switch, bottom navigation
  dictionaries/            en.json, hi.json
  i18n.ts                  locales + dictionary loader
  proxy.ts                 language redirect
```

## Settings

`web/.env.local` (from [`.env.example`](.env.example)). Only **public** values
(`NEXT_PUBLIC_…`): API URL, Supabase URL, Supabase publishable key. They are
built into the app, so rebuild after changing them.

## Sign-in and talking to the API

- **Sign-in** uses Supabase Auth in the browser ([`src/lib/supabase.ts`](src/lib/supabase.ts)):
  email + password, sign up with name, sign out. The session stays on the
  device and refreshes itself. [`src/lib/session.tsx`](src/lib/session.tsx)
  provides `useSession()` to every page.
- **Account** page (`/[lang]/account`): name, phone, app language (saved to the
  `profiles` table; the database refuses role changes) and sign out.
- **API client** ([`src/lib/api.ts`](src/lib/api.ts)): typed functions for
  every v2 API endpoint (`analyze`, `recompute`, animals, history, saving).
  Calls that need an account send the user's access token automatically;
  trying an analysis needs none. Errors come back as `ApiError` with a status,
  a code and a readable message.
- **Email confirmation:** Supabase sends a confirmation email on sign-up
  (Authentication → Sign In / Providers → Email). The link returns to
  `/[lang]/sign-in`. Supabase's built-in email sender allows only a few emails
  per hour; set up custom SMTP in Supabase before launch.
- **Phone sign-in (OTP)** needs an SMS provider configured in Supabase
  (Authentication → Sign In / Providers → Phone). The screen says "coming soon"
  until then.
- The API must allow the website's origin: `http://localhost:3000` is in the
  API's defaults; add the live domain via `GOPALAN_ALLOWED_ORIGINS` at launch.
