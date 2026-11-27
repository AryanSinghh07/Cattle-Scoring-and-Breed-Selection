-- Gopalan AI: initial database schema
--
-- Tables:   profiles, animals, analyses, reviews
-- Security: row-level security on every table; users only see their own data,
--           reviewers see analyses whose owner allowed photo use, admins see all
-- Storage:  private bucket "animal-photos", files stored as <user id>/<analysis id>/<view>.<ext>
--
-- Run once in the Supabase dashboard: SQL Editor -> New query -> paste -> Run.

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- profiles: one row per user, created automatically on sign-up
-- ---------------------------------------------------------------------------

create table public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  full_name   text,
  phone       text,
  role        text not null default 'farmer' check (role in ('farmer', 'reviewer', 'admin')),
  language    text not null default 'en',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

comment on column public.profiles.role is 'farmer (default), reviewer (checks BCS/breed), admin. Change only via SQL or the service role.';

create trigger profiles_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();

-- Role of the signed-in user. SECURITY DEFINER so policies can read it
-- without recursing into the profiles policies.
create or replace function public.app_role()
returns text
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce((select p.role from public.profiles p where p.id = auth.uid()), 'anon');
$$;

create or replace function public.is_staff()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select public.app_role() in ('reviewer', 'admin');
$$;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, full_name, phone)
  values (new.id, new.raw_user_meta_data ->> 'full_name', new.phone);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- animals: a farmer's cows and buffaloes
-- ---------------------------------------------------------------------------

create table public.animals (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  tag_id      text,
  name        text,
  species     text not null check (species in ('cow', 'buffalo')),
  breed_slug  text,
  sex         text not null default 'unknown' check (sex in ('female', 'male', 'unknown')),
  birth_date  date,
  notes       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index animals_owner_idx on public.animals (owner_id);
create unique index animals_owner_tag_idx on public.animals (owner_id, tag_id) where tag_id is not null;

create trigger animals_updated_at before update on public.animals
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- analyses: one saved analysis (photos optional, only with consent)
-- ---------------------------------------------------------------------------

create table public.analyses (
  id                uuid primary key default gen_random_uuid(),
  owner_id          uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  animal_id         uuid references public.animals (id) on delete set null,
  photo_consent     boolean not null default false,
  photos            jsonb not null default '{}'::jsonb,   -- {"side": "<storage path>", ...}
  points            jsonb not null,                       -- final points per view (after user edits)
  marker            jsonb,                                -- cm per pixel per view
  measurements      jsonb,
  bcs               jsonb,                                -- full BCS result (signals, warnings)
  bcs_score         numeric(3, 2) check (bcs_score between 1 and 5 and mod(bcs_score * 4, 1) = 0),
  bcs_confidence    real check (bcs_confidence between 0 and 1),
  breed             jsonb,                                -- full breed result (top guesses)
  breed_slug        text,
  breed_confidence  real check (breed_confidence between 0 and 1),
  breed_unsure      boolean,
  model_versions    jsonb not null default '{}'::jsonb,
  created_at        timestamptz not null default now(),
  constraint photos_need_consent check (photo_consent or photos = '{}'::jsonb)
);

comment on column public.analyses.photo_consent is 'Owner allowed photos to be stored and used to improve Gopalan AI. Without it, no photos are kept.';

create index analyses_owner_idx on public.analyses (owner_id, created_at desc);
create index analyses_animal_idx on public.analyses (animal_id, created_at desc);
create index analyses_review_queue_idx on public.analyses (bcs_confidence) where photo_consent;

-- ---------------------------------------------------------------------------
-- reviews: a reviewer confirms or corrects an analysis
-- ---------------------------------------------------------------------------

create table public.reviews (
  id           uuid primary key default gen_random_uuid(),
  analysis_id  uuid not null references public.analyses (id) on delete cascade,
  reviewer_id  uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  decision     text not null check (decision in ('confirmed', 'corrected')),
  bcs_score    numeric(3, 2) check (bcs_score between 1 and 5 and mod(bcs_score * 4, 1) = 0),
  breed_slug   text,
  notes        text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (analysis_id, reviewer_id)
);

create index reviews_analysis_idx on public.reviews (analysis_id);

create trigger reviews_updated_at before update on public.reviews
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Row-level security
-- ---------------------------------------------------------------------------

alter table public.profiles enable row level security;
alter table public.animals  enable row level security;
alter table public.analyses enable row level security;
alter table public.reviews  enable row level security;

-- profiles: read and edit your own; admins read all. Users can't change their role.
create policy "profiles: read own" on public.profiles
  for select to authenticated
  using (id = (select auth.uid()) or (select public.app_role()) = 'admin');

create policy "profiles: update own" on public.profiles
  for update to authenticated
  using (id = (select auth.uid()))
  with check (id = (select auth.uid()));

revoke insert, update, delete on public.profiles from anon, authenticated;
grant update (full_name, phone, language) on public.profiles to authenticated;

-- animals: owners manage their own; admins read all
create policy "animals: owner full access" on public.animals
  for all to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

create policy "animals: admin read" on public.animals
  for select to authenticated
  using ((select public.app_role()) = 'admin');

-- analyses: owners manage their own (and may only link their own animals);
-- reviewers/admins read analyses whose owner gave consent
create policy "analyses: owner full access" on public.analyses
  for all to authenticated
  using (owner_id = (select auth.uid()))
  with check (
    owner_id = (select auth.uid())
    and (
      animal_id is null
      or exists (select 1 from public.animals a where a.id = animal_id and a.owner_id = (select auth.uid()))
    )
  );

create policy "analyses: staff read consented" on public.analyses
  for select to authenticated
  using (photo_consent and (select public.is_staff()));

-- reviews: reviewers write their own reviews of consented analyses;
-- owners can see reviews of their analyses; admins see all
create policy "reviews: staff insert" on public.reviews
  for insert to authenticated
  with check (
    reviewer_id = (select auth.uid())
    and (select public.is_staff())
    and exists (select 1 from public.analyses x where x.id = analysis_id and x.photo_consent)
  );

create policy "reviews: staff update own" on public.reviews
  for update to authenticated
  using (reviewer_id = (select auth.uid()) and (select public.is_staff()))
  with check (reviewer_id = (select auth.uid()) and (select public.is_staff()));

create policy "reviews: staff delete own" on public.reviews
  for delete to authenticated
  using (reviewer_id = (select auth.uid()) and (select public.is_staff()));

create policy "reviews: read" on public.reviews
  for select to authenticated
  using (
    reviewer_id = (select auth.uid())
    or (select public.app_role()) = 'admin'
    or exists (select 1 from public.analyses x where x.id = analysis_id and x.owner_id = (select auth.uid()))
  );

-- Anonymous visitors get no table access at all (analysis without login runs in the API only).
revoke all on public.profiles, public.animals, public.analyses, public.reviews from anon;

-- ---------------------------------------------------------------------------
-- Storage: private bucket for photos (only uploaded with consent)
-- ---------------------------------------------------------------------------

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('animal-photos', 'animal-photos', false, 10485760, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do nothing;

create policy "animal-photos: owner upload" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'animal-photos' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "animal-photos: owner read" on storage.objects
  for select to authenticated
  using (bucket_id = 'animal-photos' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "animal-photos: owner delete" on storage.objects
  for delete to authenticated
  using (bucket_id = 'animal-photos' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "animal-photos: staff read" on storage.objects
  for select to authenticated
  using (bucket_id = 'animal-photos' and (select public.is_staff()));
