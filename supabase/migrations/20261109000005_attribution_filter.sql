-- handle_new_user: keep only known attribution keys (anyone with the anon key can send
-- arbitrary `data` to /auth/v1/otp). Each value is coerced to text and cut to 200 chars;
-- JSON nulls and every other key are dropped; nothing left -> null.

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
    where key in ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'ref')
      and jsonb_typeof(value) <> 'null';
  end if;

  insert into public.profiles (id, email, attribution)
  values (new.id, new.email, v_attribution)
  on conflict (id) do nothing;
  return new;
end;
$$;

revoke execute on function public.handle_new_user() from public, anon, authenticated;
