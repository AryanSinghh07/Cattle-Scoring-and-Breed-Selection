-- Gopalan AI: review queue
--
-- Reviewers can only read their own reviews (row-level security), so they
-- can't tell on their own whether someone else already reviewed an analysis.
-- This function returns consented analyses that NO ONE has reviewed yet,
-- least confident first. Only reviewers and admins may call it.
--
-- Run once after 20261127000000_initial_schema.sql:
-- SQL Editor -> New query -> paste -> Run.

create or replace function public.review_queue(p_limit integer default 20)
returns setof public.analyses
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if not public.is_staff() then
    raise exception 'Only reviewers and admins can open the review queue'
      using errcode = 'insufficient_privilege';
  end if;

  return query
    select a.*
    from public.analyses a
    where a.photo_consent
      and not exists (select 1 from public.reviews r where r.analysis_id = a.id)
    order by a.bcs_confidence asc nulls first, a.created_at asc
    limit least(greatest(coalesce(p_limit, 20), 1), 100);
end;
$$;

comment on function public.review_queue(integer) is
  'Consented, not yet reviewed analyses, least confident first. Reviewers/admins only.';

revoke all on function public.review_queue(integer) from public, anon;
grant execute on function public.review_queue(integer) to authenticated;

-- How many consented analyses are still waiting (for the reviewer screen).
create or replace function public.review_queue_size()
returns bigint
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if not public.is_staff() then
    raise exception 'Only reviewers and admins can open the review queue'
      using errcode = 'insufficient_privilege';
  end if;
  return (
    select count(*) from public.analyses a
    where a.photo_consent and not exists (select 1 from public.reviews r where r.analysis_id = a.id)
  );
end;
$$;

revoke all on function public.review_queue_size() from public, anon;
grant execute on function public.review_queue_size() to authenticated;
