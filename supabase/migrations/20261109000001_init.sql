-- Plataforma 3D MVP: types, tables, triggers and row level security.
-- Source of truth for the hosted project oyntcaxzskzntiyzxquy (see supabase/README.md).

create type public.piece_kind as enum (
  'mesa', 'mesita', 'aparador', 'estanteria', 'cabecero', 'panel',
  'sofa', 'sillon', 'silla', 'jarron', 'lampara', 'otro'
);

create type public.piece_status as enum (
  'queued', 'generating', 'review', 'ready', 'approved', 'needs_photos', 'rejected', 'failed'
);

create type public.credit_reason as enum ('purchase', 'consume', 'grant', 'refund', 'plan');

-- ------------------------------------------------------------------ tables

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  is_admin boolean not null default false,
  attribution jsonb,
  plan text, -- hook for the monthly plan (phase 2); null = pay per piece
  created_at timestamptz not null default now()
);

create table public.pieces (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  name text not null,
  kind public.piece_kind not null,
  width_cm numeric not null check (width_cm > 0),
  height_cm numeric not null check (height_cm > 0),
  depth_cm numeric not null check (depth_cm > 0),
  rectilinear boolean, -- null = "no sé"
  notes text,
  status public.piece_status not null default 'queued',
  attempt int not null default 1 check (attempt between 1 and 3),
  route text,
  claimed_at timestamptz,
  error text,
  review_note text,
  reject_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index pieces_queue_idx on public.pieces (status, created_at);
create index pieces_user_idx on public.pieces (user_id, created_at desc);

create table public.piece_photos (
  id uuid primary key default gen_random_uuid(),
  piece_id uuid not null references public.pieces (id) on delete cascade,
  storage_path text not null, -- bucket photos: {user_id}/{piece_id}/{n}.jpg
  position int not null default 1,
  created_at timestamptz not null default now()
);

create index piece_photos_piece_idx on public.piece_photos (piece_id, position);

create table public.piece_models (
  id uuid primary key default gen_random_uuid(),
  piece_id uuid not null references public.pieces (id) on delete cascade,
  attempt int not null,
  provider text,
  candidate int not null default 0,
  preview_path text, -- bucket previews: {piece_id}/{attempt}/model_preview.glb
  glb_path text,     -- bucket models:   {piece_id}/{attempt}/model_web.glb
  usdz_path text,    -- bucket models:   {piece_id}/{attempt}/model.usdz
  render_paths jsonb, -- bucket renders: {front,left,back,three_quarter,contact} -> path
  meta jsonb,
  max_error numeric,
  cost_usd numeric,
  selected boolean not null default false,
  created_at timestamptz not null default now()
);

create index piece_models_piece_idx on public.piece_models (piece_id, attempt desc, created_at desc);

create table public.credit_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  delta int not null check (delta <> 0),
  reason public.credit_reason not null,
  piece_id uuid references public.pieces (id) on delete set null,
  stripe_session_id text unique,
  created_at timestamptz not null default now()
);

create index credit_ledger_user_idx on public.credit_ledger (user_id, created_at desc);

create table public.purchases (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  stripe_session_id text not null unique,
  pack text not null, -- pieza_1 | pieza_10 | pieza_30
  credits int not null,
  amount_cents int not null,
  status text not null,
  created_at timestamptz not null default now()
);

create index purchases_user_idx on public.purchases (user_id, created_at desc);

-- ------------------------------------------------------------------ triggers

create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, email, attribution)
  values (new.id, new.email, new.raw_user_meta_data -> 'attribution')
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger pieces_set_updated_at
  before update on public.pieces
  for each row execute function public.set_updated_at();

-- ------------------------------------------------------------------ row level security
-- Clients (anon key + user JWT) only read their own rows and insert queued pieces and
-- their photos. Everything else goes through SQL functions or the service role, which
-- bypasses RLS.

alter table public.profiles enable row level security;
alter table public.pieces enable row level security;
alter table public.piece_photos enable row level security;
alter table public.piece_models enable row level security;
alter table public.credit_ledger enable row level security;
alter table public.purchases enable row level security;

create policy "profiles: read own" on public.profiles
  for select to authenticated using (id = (select auth.uid()));

create policy "profiles: update own" on public.profiles
  for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

-- Column privileges: a user may only touch his attribution, never is_admin/plan/email.
revoke insert, update, delete on public.profiles from anon, authenticated;
grant update (attribution) on public.profiles to authenticated;

create policy "pieces: read own" on public.pieces
  for select to authenticated using (user_id = (select auth.uid()));

-- The service role bypasses RLS; this policy is for clients only.
create policy "pieces: insert own queued" on public.pieces
  for insert to authenticated
  with check (user_id = (select auth.uid()) and status = 'queued');

-- Column privileges: clients set only the form fields (worker/admin columns stay at their
-- defaults); `id` is allowed so the web can pick the uuid before uploading photos.
revoke insert, update, delete on public.pieces from anon, authenticated;
grant insert (id, user_id, name, kind, width_cm, height_cm, depth_cm, rectilinear, notes, status)
  on public.pieces to authenticated;

create policy "piece_photos: read own" on public.piece_photos
  for select to authenticated
  using (exists (
    select 1 from public.pieces p
    where p.id = piece_id and p.user_id = (select auth.uid())
  ));

create policy "piece_photos: insert own on queued piece" on public.piece_photos
  for insert to authenticated
  with check (
    storage_path like (select auth.uid())::text || '/' || piece_id::text || '/%'
    and exists (
      select 1 from public.pieces p
      where p.id = piece_id and p.user_id = (select auth.uid()) and p.status = 'queued'
    )
  );

revoke update, delete on public.piece_photos from anon, authenticated;

-- Models are shown to the client only after internal review (ready or later).
create policy "piece_models: read own once reviewed" on public.piece_models
  for select to authenticated
  using (exists (
    select 1 from public.pieces p
    where p.id = piece_id
      and p.user_id = (select auth.uid())
      and p.status in ('ready', 'approved', 'rejected')
  ));

revoke insert, update, delete on public.piece_models from anon, authenticated;

create policy "credit_ledger: read own" on public.credit_ledger
  for select to authenticated using (user_id = (select auth.uid()));

revoke insert, update, delete on public.credit_ledger from anon, authenticated;

create policy "purchases: read own" on public.purchases
  for select to authenticated using (user_id = (select auth.uid()));

revoke insert, update, delete on public.purchases from anon, authenticated;
