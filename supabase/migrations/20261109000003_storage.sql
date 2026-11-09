-- Plataforma 3D MVP: Storage buckets and policies.
--   photos   (private) {user_id}/{piece_id}/{n}.jpg  — client reads/writes its own prefix
--   previews (public)  {piece_id}/{attempt}/model_preview.glb — served by public URL
--   models   (private) {piece_id}/{attempt}/model_web.glb, model.usdz — service role only;
--                      the web signs URLs only for the owner's `approved` pieces
--   renders  (private) {piece_id}/{attempt}/{front|left|back|three_quarter}.png, contact.jpg
--                      — service role only
-- The service role bypasses RLS, so `models`, `renders` and writes to `previews` need no
-- policy. Public buckets serve objects by URL without RLS; no SELECT policy is added for
-- `previews` so the bucket cannot be listed through the API.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('photos', 'photos', false, 20971520, array['image/jpeg', 'image/png', 'image/webp']),
  ('previews', 'previews', true, null, null),
  ('models', 'models', false, null, null),
  ('renders', 'renders', false, null, null)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

create policy "photos: read own prefix" on storage.objects
  for select to authenticated
  using (bucket_id = 'photos' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "photos: upload own prefix" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'photos' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "photos: update own prefix" on storage.objects
  for update to authenticated
  using (bucket_id = 'photos' and (storage.foldername(name))[1] = (select auth.uid())::text)
  with check (bucket_id = 'photos' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "photos: delete own prefix" on storage.objects
  for delete to authenticated
  using (bucket_id = 'photos' and (storage.foldername(name))[1] = (select auth.uid())::text);
