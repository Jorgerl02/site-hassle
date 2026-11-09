-- Anonymous free trial (funnel task, «prueba gratis sin dejar el mail»).
--
--   * Anonymous sessions (Supabase `signInAnonymously`, JWT `is_anonymous = true`, role
--     `authenticated`) may create 1 piece a day; email accounts keep 3.
--   * `handle_new_user` also keeps the `source` attribution key (the `?source=` of the CTA).
--   * `profiles.email` follows `auth.users.email`: an anonymous user who adds an email
--     (`updateUser({ email })`, confirmed by link) gets it on his profile, so the worker's
--     «piece ready» email reaches him.
--   * `claim_anonymous_pieces(from, to)` (service role only) moves an anonymous user's
--     pieces, photo rows, ledger and purchases to an existing account, for the «email
--     already registered» case. The photo objects are moved by the web before calling it.

-- ------------------------------------------------------------------ daily limit

create function public.anonymous_daily_piece_limit()
returns int
language sql
immutable
set search_path = ''
as $$ select 1 $$;

grant execute on function public.anonymous_daily_piece_limit() to anon, authenticated, service_role;

create or replace function public.enforce_daily_piece_limit()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_limit int;
begin
  if auth.role() = 'authenticated' then
    v_limit := case
      when coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false) then anonymous_daily_piece_limit()
      else daily_piece_limit()
    end;
    -- Serialise concurrent inserts of the same user so the count is exact.
    perform pg_advisory_xact_lock(hashtextextended('pieces:' || new.user_id::text, 0));
    if (
      select count(*) from pieces
      where user_id = new.user_id
        and created_at >= (date_trunc('day', now() at time zone 'Europe/Madrid')
                           at time zone 'Europe/Madrid')
    ) >= v_limit then
      raise exception 'daily_limit' using hint = 'Máximo de piezas por día alcanzado';
    end if;
  end if;
  return new;
end;
$$;

revoke execute on function public.enforce_daily_piece_limit() from public, anon, authenticated;

-- ------------------------------------------------------------------ attribution `source`

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_raw jsonb := new.raw_user_meta_data -> 'attribution';
  v_attribution jsonb;
begin
  if jsonb_typeof(v_raw) = 'object' then
    select jsonb_object_agg(
             key,
             left(case jsonb_typeof(value) when 'string' then value #>> '{}' else value::text end,
                  200)
           )
    into v_attribution
    from jsonb_each(v_raw)
    where key in ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'ref', 'source')
      and jsonb_typeof(value) <> 'null';
  end if;

  insert into public.profiles (id, email, attribution)
  values (new.id, new.email, v_attribution)
  on conflict (id) do nothing;
  return new;
end;
$$;

revoke execute on function public.handle_new_user() from public, anon, authenticated;

-- ------------------------------------------------------------------ profile email sync

create function public.sync_profile_email()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.profiles set email = new.email where id = new.id and email is distinct from new.email;
  return new;
end;
$$;

revoke execute on function public.sync_profile_email() from public, anon, authenticated;

create trigger on_auth_user_email_changed
  after update of email on auth.users
  for each row
  when (old.email is distinct from new.email)
  execute function public.sync_profile_email();

-- ------------------------------------------------------------------ claim

create function public.claim_anonymous_pieces(p_from uuid, p_to uuid)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
  v_moved int;
begin
  if auth.role() in ('anon', 'authenticated') then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  if p_from is null or p_to is null or p_from = p_to then
    return 0;
  end if;
  if not exists (select 1 from auth.users where id = p_from and is_anonymous) then
    raise exception 'not_anonymous';
  end if;
  if not exists (select 1 from profiles where id = p_to) then
    raise exception 'not_found';
  end if;

  update pieces set user_id = p_to where user_id = p_from;
  get diagnostics v_moved = row_count;
  -- After the owner change, so `check_piece_photo` accepts the new `{user_id}/…` prefix.
  update piece_photos ph
  set storage_path = p_to::text || substr(ph.storage_path, length(p_from::text) + 1)
  from pieces p
  where p.id = ph.piece_id
    and p.user_id = p_to
    and ph.storage_path like p_from::text || '/%';
  update credit_ledger set user_id = p_to where user_id = p_from;
  update purchases set user_id = p_to where user_id = p_from;
  return v_moved;
end;
$$;

revoke execute on function public.claim_anonymous_pieces(uuid, uuid) from public, anon, authenticated;
grant execute on function public.claim_anonymous_pieces(uuid, uuid) to service_role;
