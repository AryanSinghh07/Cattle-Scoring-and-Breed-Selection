-- Gopalan AI: security self-check
--
-- Creates three throw-away users (farmer A, farmer B, reviewer R) inside a
-- transaction, checks who can see what, then ROLLS BACK so nothing stays in
-- the database. Any failed check stops the script with "FAIL: ...".
--
-- Run in the Supabase dashboard after ALL migrations in supabase/migrations:
-- SQL Editor -> New query -> paste -> Run.
-- Expected last result: "All security checks passed".

begin;

-- Throw-away users (the sign-up trigger creates their profiles)
insert into auth.users (id, email, aud, role, raw_user_meta_data)
values
  ('00000000-0000-4000-8000-0000000000a1', 'rls-check-a@example.invalid', 'authenticated', 'authenticated', '{"full_name": "Farmer A"}'),
  ('00000000-0000-4000-8000-0000000000b1', 'rls-check-b@example.invalid', 'authenticated', 'authenticated', '{"full_name": "Farmer B"}'),
  ('00000000-0000-4000-8000-0000000000c1', 'rls-check-r@example.invalid', 'authenticated', 'authenticated', '{"full_name": "Reviewer R"}');

do $$
begin
  if (select count(*) from public.profiles where id in (
        '00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-0000000000b1', '00000000-0000-4000-8000-0000000000c1')) <> 3 then
    raise exception 'FAIL: profiles were not created on sign-up';
  end if;
end $$;

update public.profiles set role = 'reviewer' where id = '00000000-0000-4000-8000-0000000000c1';

-- ---- Act as farmer A ---------------------------------------------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub": "00000000-0000-4000-8000-0000000000a1", "role": "authenticated"}', true);

insert into public.animals (id, species, name, tag_id)
values ('00000000-0000-4000-8000-00000000aa01', 'cow', 'Gauri', 'A-1');

insert into public.analyses (id, animal_id, photo_consent, photos, points, bcs_score, bcs_confidence)
values
  ('00000000-0000-4000-8000-00000000ab01', '00000000-0000-4000-8000-00000000aa01', false, '{}', '{"side": {}}', 3.25, 0.5),
  ('00000000-0000-4000-8000-00000000ab02', '00000000-0000-4000-8000-00000000aa01', true,
   '{"side": "00000000-0000-4000-8000-0000000000a1/x/side.jpg"}', '{"side": {}}', 2.75, 0.4);

do $$
begin
  if (select count(*) from public.animals) <> 1 then raise exception 'FAIL: A should see exactly 1 animal'; end if;
  if (select count(*) from public.analyses) <> 2 then raise exception 'FAIL: A should see own 2 analyses'; end if;

  begin
    insert into public.analyses (points, photo_consent, photos) values ('{}', false, '{"side": "p.jpg"}');
    raise exception 'FAIL: photos were accepted without consent';
  exception when check_violation then null;
  end;

  begin
    insert into public.analyses (points, bcs_score) values ('{}', 3.1);
    raise exception 'FAIL: BCS 3.1 accepted (must be 0.25 steps)';
  exception when check_violation then null;
  end;

  begin
    update public.profiles set role = 'admin' where id = auth.uid();
    raise exception 'FAIL: a farmer changed their own role';
  exception when insufficient_privilege then null;
  end;

  begin
    insert into public.reviews (analysis_id, decision, bcs_score)
    values ('00000000-0000-4000-8000-00000000ab02', 'confirmed', 2.75);
    raise exception 'FAIL: a farmer was able to write a review';
  exception when insufficient_privilege then null;
  end;

  begin
    perform * from public.review_queue(10);
    raise exception 'FAIL: a farmer opened the review queue';
  exception when insufficient_privilege then null;
  end;
end $$;

-- ---- Act as farmer B ---------------------------------------------------------
select set_config('request.jwt.claims', '{"sub": "00000000-0000-4000-8000-0000000000b1", "role": "authenticated"}', true);

do $$
begin
  if (select count(*) from public.animals) <> 0 then raise exception 'FAIL: B can see A''s animals'; end if;
  if (select count(*) from public.analyses) <> 0 then raise exception 'FAIL: B can see A''s analyses'; end if;
  if (select count(*) from public.profiles) <> 1 then raise exception 'FAIL: B can see other profiles'; end if;

  update public.animals set name = 'hacked' where id = '00000000-0000-4000-8000-00000000aa01';
  if found then raise exception 'FAIL: B changed A''s animal'; end if;

  begin
    insert into public.analyses (animal_id, points) values ('00000000-0000-4000-8000-00000000aa01', '{}');
    raise exception 'FAIL: B attached an analysis to A''s animal';
  exception when insufficient_privilege then null;
  end;

  begin
    insert into public.animals (owner_id, species) values ('00000000-0000-4000-8000-0000000000a1', 'cow');
    raise exception 'FAIL: B created an animal owned by A';
  exception when insufficient_privilege then null;
  end;
end $$;

-- ---- Act as reviewer R -------------------------------------------------------
select set_config('request.jwt.claims', '{"sub": "00000000-0000-4000-8000-0000000000c1", "role": "authenticated"}', true);

do $$
begin
  if (select count(*) from public.analyses) <> 1 then
    raise exception 'FAIL: reviewer should see only the 1 consented analysis';
  end if;
  if (select count(*) from public.animals) <> 0 then raise exception 'FAIL: reviewer can see animals'; end if;

  if (select count(*) from public.review_queue(10)) <> 1
     or (select q.id from public.review_queue(10) q) <> '00000000-0000-4000-8000-00000000ab02' then
    raise exception 'FAIL: review queue should list only the 1 consented analysis';
  end if;
  if public.review_queue_size() <> 1 then raise exception 'FAIL: review queue size should be 1'; end if;

  insert into public.reviews (analysis_id, decision, bcs_score, notes)
  values ('00000000-0000-4000-8000-00000000ab02', 'corrected', 3.0, 'rls check');

  if (select count(*) from public.review_queue(10)) <> 0 then
    raise exception 'FAIL: a reviewed analysis is still in the queue';
  end if;

  begin
    insert into public.reviews (analysis_id, decision) values ('00000000-0000-4000-8000-00000000ab01', 'confirmed');
    raise exception 'FAIL: reviewer reviewed an analysis without consent';
  exception when insufficient_privilege then null;
  end;
end $$;

-- ---- Back to farmer A: can see the review of their analysis -------------------
select set_config('request.jwt.claims', '{"sub": "00000000-0000-4000-8000-0000000000a1", "role": "authenticated"}', true);

do $$
begin
  if (select count(*) from public.reviews) <> 1 then raise exception 'FAIL: owner cannot see the review of their analysis'; end if;
end $$;

-- ---- Anonymous visitors see nothing ------------------------------------------
reset role;
set local role anon;
select set_config('request.jwt.claims', '{"role": "anon"}', true);

do $$
begin
  begin
    perform 1 from public.analyses limit 1;
    raise exception 'FAIL: anonymous visitors can read analyses';
  exception when insufficient_privilege then null;
  end;

  begin
    perform * from public.review_queue(10);
    raise exception 'FAIL: anonymous visitors can open the review queue';
  exception when insufficient_privilege then null;
  end;
end $$;

reset role;
rollback;

select 'All security checks passed' as result;
