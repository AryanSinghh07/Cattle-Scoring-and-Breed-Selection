# Supabase: database, login and photo storage

| Path | What it is |
|---|---|
| `migrations/20261127000000_initial_schema.sql` | Tables, security rules and the photo bucket |
| `migrations/20261128000000_review_queue.sql` | `review_queue()` / `review_queue_size()`: consented analyses nobody has reviewed yet (reviewers/admins only) |
| `tests/rls_check.sql` | Security self-check (leaves no data behind) |

Migrations run **in file-name order**. Each one runs once.

## What the schema contains

| Table | Holds | Who can see it |
|---|---|---|
| `profiles` | One row per user: name, phone, language, **role** (`farmer`, `reviewer`, `admin`) | The user; admins |
| `animals` | A farmer's cows and buffaloes (tag, name, species, breed, sex, birth date) | The owner; admins |
| `analyses` | A saved analysis: final body points, measurements, BCS, breed, model versions, photo paths | The owner; reviewers/admins only if the owner gave **photo consent** |
| `reviews` | A reviewer's confirmation or correction of BCS and breed | The reviewer; the analysis owner; admins |

Rules that the database enforces itself, not just the app:

- A profile is created automatically when someone signs up.
- Users can't change their own role. Roles are changed by an admin in SQL.
- **Photos can only be stored when `photo_consent` is true.**
- BCS values must be between 1 and 5 in 0.25 steps.
- A farmer can only link analyses to their own animals.
- Anonymous visitors can't read any table. Trying an analysis without
  login happens in the API only and nothing is saved.

Photo bucket `animal-photos`: **private**, max 10 MB, JPEG/PNG/WEBP. Files are
stored as `<user id>/<analysis id>/<view>.jpg`; users can only access their
own folder, and reviewers/admins can read photos (which exist only with consent).

## Apply it to your project (one time)

1. Open the [Supabase dashboard](https://supabase.com/dashboard), select the
   project, then **SQL Editor → New query**.
2. Paste the whole content of
   `migrations/20261127000000_initial_schema.sql` and click **Run**.
   Expected: *Success. No rows returned.*
   Then do the same for each later migration, in order
   (`20261128000000_review_queue.sql`). Already applied the first one? Run
   only the new ones.
3. **New query** again, paste `tests/rls_check.sql`, click **Run**.
   Expected result: **`All security checks passed`**.
   If a check fails, it stops with `FAIL: …`. The script rolls back, so
   it never leaves test users or data behind.
4. Check **Table Editor**: `profiles`, `animals`, `analyses`, `reviews` exist.
   **Storage**: the `animal-photos` bucket exists and is private.

## Make yourself an admin

1. **Authentication → Users → Add user**, then create a user with your email
   (or sign up later through the app).
2. In the SQL Editor (replace the email):

   ```sql
   update public.profiles
   set role = 'admin'
   where id = (select id from auth.users where email = 'you@example.com');
   ```

Use `'reviewer'` instead of `'admin'` for people who should review results.

## Keys: what goes where

| Key (Project Settings → API) | Where it may be used |
|---|---|
| Project URL | Website, API |
| **Publishable / anon key** | Website and app. It is public by design; the security rules above protect the data. |
| **Secret / service role key** | **Only** in server-side secrets (`api/.env`, Hugging Face Space secrets). It bypasses all security rules. Never put it in the website, in git, or in chat. |

## How the migration was tested

Before committing, the migration and the self-check were run on a fresh
PostgreSQL 16 (PGlite) with stand-ins for Supabase's `auth` and `storage`
schemas: the migration applied, all checks passed and no data remained. The
self-check was also run against four deliberately broken versions (a leaking
read policy, the consent rule removed, users allowed to change their role,
reviewers seeing non-consented analyses), and it reported each one. Running it
on the real project (step 3) is the final confirmation.
