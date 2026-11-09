-- Anti-abuse of the anonymous trial: one row per anonymous piece with the client's IP
-- hashed (SHA-256 with a server salt; the IP itself is never stored). The web refuses an
-- anonymous piece once an IP hash has 3 rows in the last 24 h. Service role only.

create table public.trial_ips (
  id bigint generated always as identity primary key,
  ip_hash text not null check (ip_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);

create index trial_ips_hash_created_idx on public.trial_ips (ip_hash, created_at desc);

alter table public.trial_ips enable row level security;
-- No policies: anon/authenticated cannot read or write it; the web uses the service role.
revoke all on public.trial_ips from anon, authenticated;
