-- Final review hardening:
--   I-1  CHECKs on pieces mirroring the form (platform/src/lib/validation.ts); piece_photos
--        paths bound to the piece owner and at most 4 photos (+1 thumb) per piece.
--   I-4  claim_next_piece skips photo-less pieces younger than 10 min and deferred ones.
--   I-5  column-level SELECT for clients on pieces and piece_models; request_new_version and
--        reject_piece return {ok, status, attempt} instead of the row.
--   I-6/M-6 pieces.provider_cost_usd (cost of failed attempts), pieces.not_before (budget
--        deferral) and provider_spend_today() for the worker's daily budget.
--   M-2  credit_ledger.stripe_event_id (refunds idempotent by Stripe event) and
--        purchases.stripe_payment_intent (refund → purchase lookup).
--   M-3  clients can no longer update profiles.attribution (set by the signup trigger).
--   M-4  photos uploads must be {uid}/{uuid}/(n|thumb).(jpg|png|webp).
--   M-11 at most one selected model per (piece, attempt).
-- admin_review_queue is recreated at the end (it uses p.*).

-- ------------------------------------------------------------------ I-1 pieces checks

alter table public.pieces
  add constraint pieces_name_length check (char_length(btrim(name)) between 2 and 80),
  add constraint pieces_notes_length check (notes is null or char_length(notes) <= 500),
  add constraint pieces_width_range check (width_cm between 1 and 400),
  add constraint pieces_height_range check (height_cm between 1 and 400),
  add constraint pieces_depth_range check (depth_cm between 1 and 400);

-- ------------------------------------------------------------------ I-1 piece_photos

create function public.check_piece_photo()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user uuid;
  v_is_thumb boolean;
  v_count int;
begin
  -- Lock the piece: concurrent inserts of the same piece are counted exactly.
  select user_id into v_user from pieces where id = new.piece_id for update;
  if not found then
    raise exception 'not_found';
  end if;
  -- uuids only contain [0-9a-f-], so the concatenated pattern has no other metacharacter
  -- and the fixed shape rules out «..» or any other folder.
  if new.storage_path !~ ('^' || v_user::text || '/' || new.piece_id::text
                          || '/(\d+|thumb)\.(jpg|png|webp)$') then
    raise exception 'invalid_photo_path' using errcode = '23514';
  end if;
  v_is_thumb := new.storage_path ~ '/thumb\.(jpg|png|webp)$';
  select count(*) into v_count from piece_photos
  where piece_id = new.piece_id
    and id is distinct from new.id
    and (storage_path ~ '/thumb\.(jpg|png|webp)$') = v_is_thumb;
  if v_count >= (case when v_is_thumb then 1 else 4 end) then
    raise exception 'too_many_photos' using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger piece_photos_check
  before insert or update on public.piece_photos
  for each row execute function public.check_piece_photo();

revoke execute on function public.check_piece_photo() from public, anon, authenticated;

-- ------------------------------------------------------------------ I-6 / M-6 columns

alter table public.pieces
  add column provider_cost_usd numeric not null default 0 check (provider_cost_usd >= 0),
  add column not_before timestamptz;

-- ------------------------------------------------------------------ I-4 claim

create or replace function public.claim_next_piece()
returns pieces
language plpgsql
security definer
set search_path = public
as $$
declare
  v_piece pieces;
begin
  if auth.role() in ('anon', 'authenticated') then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  -- Only pieces whose photos have arrived (or old enough for the worker to mark them
  -- needs_photos) and not deferred (not_before, e.g. daily provider budget spent).
  update pieces
  set status = 'generating', claimed_at = now(), error = null
  where id = (
    select p.id from pieces p
    where p.status = 'queued'
      and (p.not_before is null or p.not_before <= now())
      and (
        exists (select 1 from piece_photos ph where ph.piece_id = p.id)
        or p.created_at < now() - interval '10 minutes'
      )
    order by p.created_at
    for update skip locked
    limit 1
  )
  returning * into v_piece;
  return v_piece;
end;
$$;

-- Today's provider spend (00:00 Europe/Madrid): models generated today plus the cost of
-- failed attempts on pieces touched today. Service role only.
create function public.provider_spend_today()
returns numeric
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_since timestamptz := date_trunc('day', now() at time zone 'Europe/Madrid')
                         at time zone 'Europe/Madrid';
begin
  if auth.role() in ('anon', 'authenticated') then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  return coalesce((select sum(cost_usd) from piece_models where created_at >= v_since), 0)
       + coalesce((select sum(provider_cost_usd) from pieces where updated_at >= v_since), 0);
end;
$$;

revoke execute on function public.provider_spend_today() from public, anon, authenticated;
grant execute on function public.provider_spend_today() to service_role;

-- ------------------------------------------------------------------ I-5 column reads

revoke select on public.pieces from anon, authenticated;
grant select (
  id, user_id, name, kind, width_cm, height_cm, depth_cm, rectilinear, support, notes,
  status, attempt, error, reject_reason, created_at, updated_at
) on public.pieces to authenticated;

revoke select on public.piece_models from anon, authenticated;
grant select (
  id, piece_id, attempt, preview_path, glb_path, usdz_path, render_paths, selected, created_at
) on public.piece_models to authenticated;

drop function public.request_new_version(uuid);
drop function public.reject_piece(uuid, text);

-- Ask for another version: ready -> queued, attempt + 1 (at most 3 attempts in total).
create function public.request_new_version(p_piece_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid uuid := auth.uid();
  v_status piece_status;
  v_attempt int;
begin
  if v_uid is null then
    raise exception 'not_authenticated' using errcode = '42501';
  end if;
  select status, attempt into v_status, v_attempt from pieces
  where id = p_piece_id and user_id = v_uid
  for update;
  if not found then
    raise exception 'not_found';
  end if;
  if v_status <> 'ready' then
    raise exception 'invalid_state';
  end if;
  if v_attempt >= 3 then
    raise exception 'max_versions';
  end if;

  update pieces
  set status = 'queued', attempt = attempt + 1, claimed_at = null, error = null,
      not_before = null
  where id = p_piece_id
  returning status, attempt into v_status, v_attempt;
  return jsonb_build_object('ok', true, 'status', v_status, 'attempt', v_attempt);
end;
$$;

-- "No me sirve": ready -> rejected with the client's reason.
create function public.reject_piece(p_piece_id uuid, p_reason text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid uuid := auth.uid();
  v_status piece_status;
  v_attempt int;
begin
  if v_uid is null then
    raise exception 'not_authenticated' using errcode = '42501';
  end if;
  select status, attempt into v_status, v_attempt from pieces
  where id = p_piece_id and user_id = v_uid
  for update;
  if not found then
    raise exception 'not_found';
  end if;
  if v_status <> 'ready' then
    raise exception 'invalid_state';
  end if;

  update pieces
  set status = 'rejected', reject_reason = left(nullif(btrim(p_reason), ''), 500)
  where id = p_piece_id
  returning status, attempt into v_status, v_attempt;
  return jsonb_build_object('ok', true, 'status', v_status, 'attempt', v_attempt);
end;
$$;

revoke execute on function public.request_new_version(uuid) from public, anon;
revoke execute on function public.reject_piece(uuid, text) from public, anon;
grant execute on function public.request_new_version(uuid) to authenticated, service_role;
grant execute on function public.reject_piece(uuid, text) to authenticated, service_role;

-- ------------------------------------------------------------------ M-2 refunds

alter table public.credit_ledger add column stripe_event_id text unique;
alter table public.purchases add column stripe_payment_intent text;
create index purchases_payment_intent_idx on public.purchases (stripe_payment_intent);

-- ------------------------------------------------------------------ M-3 attribution

revoke update (attribution) on public.profiles from authenticated;

-- ------------------------------------------------------------------ M-4 photos objects

drop policy "photos: upload own prefix" on storage.objects;
drop policy "photos: update own prefix" on storage.objects;

create policy "photos: upload own piece files" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'photos'
    and name ~ ('^' || (select auth.uid())::text
                || '/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
                || '/(\d+|thumb)\.(jpg|png|webp)$')
  );

create policy "photos: update own piece files" on storage.objects
  for update to authenticated
  using (bucket_id = 'photos' and (storage.foldername(name))[1] = (select auth.uid())::text)
  with check (
    bucket_id = 'photos'
    and name ~ ('^' || (select auth.uid())::text
                || '/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
                || '/(\d+|thumb)\.(jpg|png|webp)$')
  );

-- ------------------------------------------------------------------ M-11 one selected

create unique index piece_models_one_selected_idx
  on public.piece_models (piece_id, attempt) where selected;

-- ------------------------------------------------------------------ admin_review_queue
-- pieces gained support, provider_cost_usd and not_before: recreate (p.* is frozen).

drop view public.admin_review_queue;

create view public.admin_review_queue
with (security_invoker = false)
as
select
  p.*,
  pr.email as user_email,
  m.id as model_id,
  m.attempt as model_attempt,
  m.provider,
  m.candidate,
  m.preview_path,
  m.glb_path,
  m.usdz_path,
  m.render_paths,
  m.meta,
  m.max_error,
  m.cost_usd,
  m.selected,
  m.created_at as model_created_at
from public.pieces p
join public.profiles pr on pr.id = p.user_id
left join lateral (
  select * from public.piece_models pm
  where pm.piece_id = p.id
  order by pm.attempt desc, pm.selected desc, pm.created_at desc
  limit 1
) m on true
where p.status = 'review'
order by p.updated_at;

revoke all on public.admin_review_queue from public, anon, authenticated;
grant select on public.admin_review_queue to service_role;
