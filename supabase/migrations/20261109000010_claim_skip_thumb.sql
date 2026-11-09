-- claim_next_piece: the panel thumbnail (`…/thumb.{jpg,png,webp}`) is not a photo. A piece
-- whose only piece_photos row is a thumb waits like a photo-less one (claimed only after
-- 10 minutes, when the worker marks it needs_photos) instead of stalling the worker.

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
  update pieces
  set status = 'generating', claimed_at = now(), error = null
  where id = (
    select p.id from pieces p
    where p.status = 'queued'
      and (p.not_before is null or p.not_before <= now())
      and (
        exists (
          select 1 from piece_photos ph
          where ph.piece_id = p.id
            and ph.storage_path !~ '/thumb\.(jpg|png|webp)$'
        )
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

revoke execute on function public.claim_next_piece() from public, anon, authenticated;
grant execute on function public.claim_next_piece() to service_role;
