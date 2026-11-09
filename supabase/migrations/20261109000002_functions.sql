-- Plataforma 3D MVP: SQL functions (credits, approval, versions, worker queue, daily limit)
-- and the internal review view.
--
-- Errors are raised with the code as message (PostgREST returns it in `message`):
--   not_authenticated, forbidden, not_found, invalid_state, insufficient_credits,
--   max_versions, daily_limit.
-- "Service role only" functions refuse calls from anon/authenticated JWTs and their EXECUTE
-- privilege is revoked from those roles. auth.uid()/auth.role() read the request JWT claims,
-- so they keep returning the caller inside SECURITY DEFINER functions.

-- ------------------------------------------------------------------ helpers

create function public.daily_piece_limit()
returns int
language sql
immutable
set search_path = ''
as $$ select 3 $$;

create function public.credit_balance(p_user uuid)
returns int
language plpgsql
stable
security definer
set search_path = public
as $$
begin
  if auth.role() in ('anon', 'authenticated') and p_user is distinct from auth.uid() then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  return coalesce((select sum(delta) from credit_ledger where user_id = p_user), 0)::int;
end;
$$;

-- Pieces created since 00:00 Europe/Madrid.
create function public.pieces_created_today(p_user uuid)
returns int
language plpgsql
stable
security definer
set search_path = public
as $$
begin
  if auth.role() in ('anon', 'authenticated') and p_user is distinct from auth.uid() then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  return (
    select count(*)::int from pieces
    where user_id = p_user
      and created_at >= (date_trunc('day', now() at time zone 'Europe/Madrid')
                         at time zone 'Europe/Madrid')
  );
end;
$$;

-- ------------------------------------------------------------------ daily limit
-- Applies only to clients (authenticated JWT); the worker and the admin (service role)
-- can insert or re-queue freely.

create function public.enforce_daily_piece_limit()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if auth.role() = 'authenticated' then
    -- Serialise concurrent inserts of the same user so the count is exact.
    perform pg_advisory_xact_lock(hashtextextended('pieces:' || new.user_id::text, 0));
    if (
      select count(*) from pieces
      where user_id = new.user_id
        and created_at >= (date_trunc('day', now() at time zone 'Europe/Madrid')
                           at time zone 'Europe/Madrid')
    ) >= daily_piece_limit() then
      raise exception 'daily_limit' using hint = 'Máximo de piezas por día alcanzado';
    end if;
  end if;
  return new;
end;
$$;

create trigger pieces_enforce_daily_limit
  before insert on public.pieces
  for each row execute function public.enforce_daily_piece_limit();

-- ------------------------------------------------------------------ client actions

-- Download with credit: ready -> approved, consumes 1 credit once.
create function public.approve_piece(p_piece_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid uuid := auth.uid();
  v_status piece_status;
  v_balance int;
begin
  if v_uid is null then
    raise exception 'not_authenticated' using errcode = '42501';
  end if;
  -- One credit operation per user at a time (double click, two tabs, two pieces).
  perform pg_advisory_xact_lock(hashtextextended('credits:' || v_uid::text, 0));

  select status into v_status from pieces
  where id = p_piece_id and user_id = v_uid
  for update;
  if not found then
    raise exception 'not_found';
  end if;

  v_balance := credit_balance(v_uid);
  if v_status = 'approved' then
    return jsonb_build_object('ok', true, 'already', true, 'balance', v_balance);
  end if;
  if v_status <> 'ready' then
    raise exception 'invalid_state';
  end if;
  if v_balance < 1 then
    raise exception 'insufficient_credits';
  end if;

  insert into credit_ledger (user_id, delta, reason, piece_id)
  values (v_uid, -1, 'consume', p_piece_id);
  update pieces set status = 'approved' where id = p_piece_id;

  return jsonb_build_object('ok', true, 'balance', v_balance - 1);
end;
$$;

-- Ask for another version: ready -> queued, attempt + 1 (at most 3 attempts in total).
create function public.request_new_version(p_piece_id uuid)
returns pieces
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid uuid := auth.uid();
  v_piece pieces;
begin
  if v_uid is null then
    raise exception 'not_authenticated' using errcode = '42501';
  end if;
  select * into v_piece from pieces
  where id = p_piece_id and user_id = v_uid
  for update;
  if not found then
    raise exception 'not_found';
  end if;
  if v_piece.status <> 'ready' then
    raise exception 'invalid_state';
  end if;
  if v_piece.attempt >= 3 then
    raise exception 'max_versions';
  end if;

  update pieces
  set status = 'queued', attempt = attempt + 1, claimed_at = null, error = null
  where id = p_piece_id
  returning * into v_piece;
  return v_piece;
end;
$$;

-- "No me sirve": ready -> rejected with the client's reason.
create function public.reject_piece(p_piece_id uuid, p_reason text)
returns pieces
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid uuid := auth.uid();
  v_piece pieces;
begin
  if v_uid is null then
    raise exception 'not_authenticated' using errcode = '42501';
  end if;
  select * into v_piece from pieces
  where id = p_piece_id and user_id = v_uid
  for update;
  if not found then
    raise exception 'not_found';
  end if;
  if v_piece.status <> 'ready' then
    raise exception 'invalid_state';
  end if;

  update pieces
  set status = 'rejected', reject_reason = nullif(btrim(p_reason), '')
  where id = p_piece_id
  returning * into v_piece;
  return v_piece;
end;
$$;

-- ------------------------------------------------------------------ service role only

-- Worker: take the oldest queued piece atomically (queued -> generating).
-- Returns a row with every column null when the queue is empty.
create function public.claim_next_piece()
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
  update pieces
  set status = 'generating', claimed_at = now(), error = null
  where id = (
    select id from pieces
    where status = 'queued'
    order by created_at
    for update skip locked
    limit 1
  )
  returning * into v_piece;
  return v_piece;
end;
$$;

-- Worker start-up: orphaned `generating` pieces go back to the queue.
create function public.requeue_stale_pieces(p_minutes int default 30)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count int;
begin
  if auth.role() in ('anon', 'authenticated') then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  update pieces
  set status = 'queued', claimed_at = null
  where status = 'generating'
    and claimed_at < now() - make_interval(mins => p_minutes);
  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

-- Stripe webhook / admin: add credits, idempotent by Stripe session id. Returns the balance.
create function public.grant_credits(
  p_user uuid,
  p_delta int,
  p_reason credit_reason,
  p_session text default null
)
returns int
language plpgsql
security definer
set search_path = public
as $$
begin
  if auth.role() in ('anon', 'authenticated') then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  insert into credit_ledger (user_id, delta, reason, stripe_session_id)
  values (p_user, p_delta, p_reason, p_session)
  on conflict (stripe_session_id) do nothing;
  return credit_balance(p_user);
end;
$$;

-- ------------------------------------------------------------------ privileges
-- Supabase grants EXECUTE on new public functions to anon/authenticated by default.

revoke execute on function public.handle_new_user() from public, anon, authenticated;
revoke execute on function public.set_updated_at() from public, anon, authenticated;
revoke execute on function public.enforce_daily_piece_limit() from public, anon, authenticated;

revoke execute on function public.credit_balance(uuid) from public, anon;
revoke execute on function public.pieces_created_today(uuid) from public, anon;
revoke execute on function public.approve_piece(uuid) from public, anon;
revoke execute on function public.request_new_version(uuid) from public, anon;
revoke execute on function public.reject_piece(uuid, text) from public, anon;
grant execute on function public.credit_balance(uuid) to authenticated, service_role;
grant execute on function public.pieces_created_today(uuid) to authenticated, service_role;
grant execute on function public.approve_piece(uuid) to authenticated, service_role;
grant execute on function public.request_new_version(uuid) to authenticated, service_role;
grant execute on function public.reject_piece(uuid, text) to authenticated, service_role;
grant execute on function public.daily_piece_limit() to anon, authenticated, service_role;

revoke execute on function public.claim_next_piece() from public, anon, authenticated;
revoke execute on function public.requeue_stale_pieces(int) from public, anon, authenticated;
revoke execute on function public.grant_credits(uuid, int, credit_reason, text)
  from public, anon, authenticated;
grant execute on function public.claim_next_piece() to service_role;
grant execute on function public.requeue_stale_pieces(int) to service_role;
grant execute on function public.grant_credits(uuid, int, credit_reason, text) to service_role;

-- ------------------------------------------------------------------ admin review queue
-- Pieces in `review` with their latest model. Runs with the owner's rights
-- (security_invoker = false), so it is reachable only by the service role.

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
  order by pm.attempt desc, pm.created_at desc
  limit 1
) m on true
where p.status = 'review'
order by p.updated_at;

revoke all on public.admin_review_queue from public, anon, authenticated;
grant select on public.admin_review_queue to service_role;
