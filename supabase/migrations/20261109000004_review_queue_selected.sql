-- admin_review_queue: among the latest attempt's candidates prefer the `selected` one.
-- Client piece_models: only the piece's current attempt (never older versions).

create or replace view public.admin_review_queue
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

drop policy "piece_models: read own once reviewed" on public.piece_models;

create policy "piece_models: read own current attempt once reviewed" on public.piece_models
  for select to authenticated
  using (exists (
    select 1 from public.pieces p
    where p.id = piece_models.piece_id
      and p.attempt = piece_models.attempt
      and p.user_id = (select auth.uid())
      and p.status in ('ready', 'approved', 'rejected')
  ));
