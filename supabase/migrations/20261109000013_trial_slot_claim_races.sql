-- Fix round 2 of the anonymous trial.
--
--   * `claim_trial_slot(ip_hash, limit)`: atomic per-network cap (advisory lock per hash,
--     count of the last 24 h, insert if under the limit). Returns the new row id, or null
--     when the cap is reached; `release_trial_slot(id)` gives it back if the piece is not
--     created. Both service role only.
--   * `claim_anonymous_pieces(from, to, pieces)` now moves only the listed pieces that are
--     not `queued`/`generating` (rechecked under lock here; the web moved their photo files
--     just before) and returns the ids it moved; the caller moves the files of the others back.

create function public.claim_trial_slot(p_ip_hash text, p_limit int default 3)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id bigint;
begin
  if auth.role() in ('anon', 'authenticated') then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('trial_ip:' || p_ip_hash, 0));
  if (
    select count(*) from trial_ips
    where ip_hash = p_ip_hash and created_at > now() - interval '24 hours'
  ) >= p_limit then
    return null;
  end if;
  insert into trial_ips (ip_hash) values (p_ip_hash) returning id into v_id;
  return v_id;
end;
$$;

create function public.release_trial_slot(p_id bigint)
returns void
language sql
security definer
set search_path = public
as $$ delete from trial_ips where id = p_id $$;

revoke execute on function public.claim_trial_slot(text, int) from public, anon, authenticated;
revoke execute on function public.release_trial_slot(bigint) from public, anon, authenticated;
grant execute on function public.claim_trial_slot(text, int) to service_role;
grant execute on function public.release_trial_slot(bigint) to service_role;

drop function public.claim_anonymous_pieces(uuid, uuid);

create function public.claim_anonymous_pieces(p_from uuid, p_to uuid, p_pieces uuid[])
returns uuid[]
language plpgsql
security definer
set search_path = public
as $$
declare
  v_moved uuid[];
begin
  if auth.role() in ('anon', 'authenticated') then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  if p_from is null or p_to is null or p_from = p_to then
    return '{}';
  end if;
  if not exists (select 1 from auth.users where id = p_from and is_anonymous) then
    raise exception 'not_anonymous';
  end if;
  if not exists (select 1 from profiles where id = p_to) then
    raise exception 'not_found';
  end if;

  -- Lock the listed pieces and keep those the worker is not about to read.
  select coalesce(array_agg(id), '{}') into v_moved
  from (
    select id from pieces
    where id = any(coalesce(p_pieces, '{}'))
      and user_id = p_from
      and status not in ('queued', 'generating')
    for update
  ) ok;

  update pieces set user_id = p_to where id = any(v_moved);
  -- After the owner change, so `check_piece_photo` accepts the new `{user_id}/…` prefix.
  update piece_photos ph
  set storage_path = p_to::text || substr(ph.storage_path, length(p_from::text) + 1)
  where ph.piece_id = any(v_moved)
    and ph.storage_path like p_from::text || '/%';
  update credit_ledger set user_id = p_to where user_id = p_from;
  update purchases set user_id = p_to where user_id = p_from;
  return v_moved;
end;
$$;

revoke execute on function public.claim_anonymous_pieces(uuid, uuid, uuid[]) from public, anon, authenticated;
grant execute on function public.claim_anonymous_pieces(uuid, uuid, uuid[]) to service_role;
