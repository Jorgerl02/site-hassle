# Plataforma de piezas 3D a escala real — plan de implementación del MVP

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Una web donde un cliente sube la foto y las medidas de un mueble, recibe un modelo 3D a escala real revisado internamente, lo ve con RA, lo aprueba y lo descarga, pagando por créditos (primera pieza gratis), lista para probar con anuncios.

**Architecture:** Next.js 16 (App Router, Chakra UI v3) en `platform/` sobre Supabase (Auth por enlace mágico, Postgres con RLS y funciones SQL, Storage) y Stripe Checkout; un worker Python en `src/platform_worker/` que reclama piezas en cola por PostgREST, ejecuta el harness existente (`src/harness`: validador, enrutado por reglas, E paramétrica, proveedor por API, ajuste a caja, renders, entrega GLB/USDZ) y sube los resultados; una cola de revisión interna antes de mostrar al cliente.

**Tech Stack:** Next.js 16.1, React 19.2, TypeScript, Chakra UI v3.28, `@supabase/ssr` + `@supabase/supabase-js`, Stripe Node SDK, `@google/model-viewer` 4.4.0, Playwright; Python 3.12 + `uv`, `httpx`, el harness del repo, Blender 5.2 LTS.

**Spec:** `docs/superpowers/specs/2026-11-09-plataforma-3d-mvp-design.md`

## Global Constraints

- Proyecto Supabase `site-hassle`, ref `oyntcaxzskzntiyzxquy`, URL `https://oyntcaxzskzntiyzxquy.supabase.co`, región eu-west-1. Claves ya en `platform/.env.local` (gitignored): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_PROJECT_REF`. No hay Docker: no existe Supabase local; las migraciones se aplican al proyecto alojado y los tests de SQL se ejecutan contra él con un esquema de prueba limpio por test (datos con prefijo `test_` borrados al final).
- Stripe: cuenta sandbox "Bloom Studio" en la CLI; `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` y `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` las pega Jorge en `platform/.env.local`; hasta entonces el código debe arrancar y los tests usar eventos construidos con `stripe.webhooks.generateTestHeaderString`.
- Paquetes de créditos (IVA incluido, EUR, `lookup_key` de Stripe entre paréntesis): 1 pieza 9 € (`pieza_1`), 10 piezas 69 € (`pieza_10`, etiqueta «Más elegido»), 30 piezas 169 € (`pieza_30`). 1 crédito = 1 pieza descargada (GLB 2K + USDZ). Ver el resultado en el visor con medidas y RA es gratis en calidad de previsualización (`model_preview.glb`, texturas 512 px, ≤ 15.000 triángulos, bucket público). Máximo 3 piezas creadas por cuenta y día (`daily_piece_limit`). Los créditos comprados no caducan. Pedir otra versión (máximo 2 por pieza), rechazar y los fallos no cuestan nada al cliente. Sin reembolsos.
- Estados de pieza (enum `piece_status`): `queued`, `generating`, `review`, `ready`, `approved`, `needs_photos`, `rejected`, `failed`. Transiciones: worker `queued→generating→review|needs_photos|failed`; admin `review→ready|queued|rejected`; cliente `ready→approved` (descargar con crédito) o `ready→queued` (otra versión, `attempt+1`, si `attempt < 3`) o `ready→rejected`.
- Rutas de Storage: bucket `photos` (privado) `{user_id}/{piece_id}/{n}.jpg`; bucket `previews` (público) `{piece_id}/{attempt}/model_preview.glb`; bucket `models` (privado, URLs firmadas tras la descarga con crédito) `{piece_id}/{attempt}/model_web.glb` y `model.usdz`; bucket `renders` (privado) `{piece_id}/{attempt}/{front|left|back|three_quarter}.png` y `contact.jpg`.
- Categorías excluidas en la entrada (texto de `docs/promesa.md`): metal, vidrio y patas finas. Tipos de pieza del formulario (`piece_kind`): `mesa`, `mesita`, `aparador`, `estanteria`, `cabecero`, `panel`, `sofa`, `sillon`, `silla`, `jarron`, `lampara`, `otro`; `lampara` y cualquier nota con «metal», «cromo», «vidrio», «cristal» se rechazan en el worker con `needs_photos` y el motivo.
- Todo texto visible en español con tipografía cuidada (espacio antes de %, coma decimal, «1.000»); código, identificadores y comentarios en inglés. Sin conectores, MCP, plugins ni plan mensual (solo el gancho `credit_ledger.reason = 'plan'`).
- Build antes de cualquier push: `pnpm --dir platform build`, `uv run pytest -q`, `pnpm --dir platform lint`, `uv run ruff check .`. Nada se despliega a producción sin autorización explícita de Jorge.
- Documentación consultada con Context7 antes de escribir código de Next.js 16, Chakra UI v3, `@supabase/ssr`, Stripe Node y model-viewer; anotar en el informe de cada tarea qué se leyó.

## Review Focus

1. Un cliente pulsa «Descargar» dos veces seguidas (doble clic o dos pestañas): solo debe consumirse un crédito y el estado quedar `approved` una vez → test de `approve_piece` concurrente en Tarea 1.
2. El webhook de Stripe llega dos veces para la misma sesión: los créditos se abonan una sola vez → test de idempotencia por `stripe_session_id` en Tarea 5.
3. Fotos que superan 20 MB o no son imagen (PDF, HEIC sin convertir): el formulario debe rechazarlas antes de subir y el worker marcar `needs_photos` sin fallar → tests en Tareas 4 y 3.
4. El worker muere a mitad de una pieza (`generating` huérfana): al arrancar, las piezas `generating` con `claimed_at` de más de 30 minutos vuelven a `queued` → test en Tarea 3.
5. Un usuario intenta abrir la pieza de otro por URL o aprobarla: RLS y las funciones SQL deben negarlo → tests de RLS en Tarea 1 y de página 404 en Tarea 4.

---

### Task 1: Esquema de datos, funciones SQL, RLS y Storage en Supabase

**Files:**
- Create: `supabase/config.toml` (raíz del repo; solo `project_id = "site-hassle"`), `supabase/migrations/20261109000001_init.sql`, `supabase/migrations/20261109000002_functions.sql`, `supabase/migrations/20261109000003_storage.sql`, `supabase/README.md`
- Test: `tests/test_supabase_schema.py` (pytest + `httpx` contra el proyecto alojado por PostgREST `rpc/…` y `auth/v1/admin/users`; se salta si no existe `SUPABASE_SERVICE_ROLE_KEY` en `platform/.env.local` o en el entorno; usuarios `test_*` creados y borrados en una fixture). No tocar `platform/` (lo crea la Tarea 2 en paralelo).

**Interfaces:**
- Produces (tablas, todas con `id uuid default gen_random_uuid()`, `created_at timestamptz default now()`):
  - `profiles(id uuid pk references auth.users, email text, is_admin bool default false, attribution jsonb, plan text null)`; trigger `handle_new_user` copia `email` y `raw_user_meta_data->'attribution'` al crear el usuario en `auth.users`.
  - `pieces(id, user_id uuid, name text, kind piece_kind, width_cm numeric, height_cm numeric, depth_cm numeric, rectilinear bool null, notes text, status piece_status default 'queued', attempt int default 1, route text, claimed_at timestamptz, error text, review_note text, reject_reason text, updated_at timestamptz)`; trigger `set_updated_at`.
  - `piece_photos(id, piece_id, storage_path text, position int)`.
  - `piece_models(id, piece_id, attempt int, provider text, candidate int, preview_path text, glb_path text, usdz_path text, render_paths jsonb, meta jsonb, max_error numeric, cost_usd numeric, selected bool default false)`.
  - `credit_ledger(id, user_id, delta int, reason credit_reason, piece_id uuid null, stripe_session_id text null unique)` con `credit_reason` enum `purchase|consume|grant|refund|plan`.
  - `purchases(id, user_id, stripe_session_id text unique, pack text, credits int, amount_cents int, status text)`.
  - Funciones (SECURITY DEFINER, `search_path = public`): `credit_balance(p_user uuid) returns int`; `claim_next_piece() returns pieces` (solo service role; `UPDATE … WHERE id = (SELECT id FROM pieces WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *`, pone `generating` y `claimed_at`); `requeue_stale_pieces(p_minutes int default 30) returns int`; `approve_piece(p_piece_id uuid) returns jsonb` (exige `auth.uid()` dueño y `status='ready'`; exige `credit_balance ≥ 1` e inserta `consume −1` con `piece_id`; pone `approved`; devuelve `{ok, balance}`; error `insufficient_credits` o `invalid_state`; si ya está `approved` devuelve `{ok, already: true}` sin consumir); `pieces_created_today(p_user uuid) returns int` y trigger `enforce_daily_piece_limit` (3) en insert de `pieces`; `request_new_version(p_piece_id uuid) returns pieces` (`ready→queued`, `attempt+1`, error `max_versions` si `attempt >= 3`); `reject_piece(p_piece_id uuid, p_reason text) returns pieces` (`ready→rejected`); `grant_credits(p_user uuid, p_delta int, p_reason credit_reason, p_session text) returns int` (solo service role, idempotente por `p_session`).
  - RLS: `profiles` select/update propio; `pieces`, `piece_photos`, `piece_models`, `credit_ledger`, `purchases` select propio; insert en `pieces`/`piece_photos` solo propio con `status='queued'`; todo lo demás por service role. Políticas de Storage: `photos` lectura/escritura propia por prefijo `{user_id}/`; `previews` lectura pública; `models` y `renders` solo service role (la web firma URLs de `models` solo para piezas `approved` del dueño).
  - Vista `admin_review_queue` (security_invoker=false, solo service role): piezas en `review` con su último `piece_models`.

- [ ] **Step 1: Escribir los tests SQL** en `tests/test_supabase_schema.py` (httpx con la clave de servicio; crea dos usuarios `test_a@…`, `test_b@…` por `POST /auth/v1/admin/users`, obtiene sus JWT por `POST /auth/v1/token?grant_type=password`, los borra al final): `approve_piece` sin saldo → `insufficient_credits`; tras `grant_credits(+1,'purchase','sess_1')` aprueba y el saldo queda 0; segunda llamada sobre la misma pieza → `{already: true}` sin consumir; cuarta pieza creada el mismo día → error `daily_limit`; `grant_credits` repetido con `sess_1` no suma; `request_new_version` tres veces → `max_versions`; `claim_next_piece` devuelve la más antigua y la segunda llamada otra distinta; `requeue_stale_pieces` recupera una `generating` con `claimed_at` de hace 40 min; con el cliente anónimo autenticado como `b`, `select` de piezas de `a` devuelve 0 filas y `approve_piece` de una pieza de `a` falla; dos llamadas simultáneas a `approve_piece` (Promise.all) consumen un solo crédito.
- [ ] **Step 2: Ejecutar los tests y comprobar que fallan** (`uv run pytest tests/test_supabase_schema.py -q`; esperado: fallos por tablas/funciones inexistentes).
- [ ] **Step 3: Escribir las tres migraciones** con los tipos, tablas, triggers, funciones, RLS, buckets (`insert into storage.buckets`) y políticas del bloque Interfaces.
- [ ] **Step 4: Aplicarlas al proyecto** con `supabase link --project-ref oyntcaxzskzntiyzxquy` y `supabase db push` (o, si pide contraseña de base de datos y no está, con la herramienta MCP de Supabase `apply_migration` sobre `oyntcaxzskzntiyzxquy`, una llamada por archivo y en el mismo orden). Anotar en el README cuál se usó.
- [ ] **Step 5: Ejecutar los tests y comprobar que pasan**; `supabase gen types typescript --project-id oyntcaxzskzntiyzxquy > supabase/database.types.ts` (la Tarea 4 lo copia a `platform/src/lib/`).
- [ ] **Step 6: Commit** (`git add supabase tests/test_supabase_schema.py`).

### Task 2: Aplicación web: base, tema, acceso y landing

**Files:**
- Create: `platform/` con `pnpm create next-app@latest` (sin Turbopack si da problemas con Chakra) (TypeScript, App Router, `src/`, sin Tailwind, ESLint), `platform/src/app/layout.tsx`, `platform/src/app/page.tsx` (landing), `platform/src/app/entrar/page.tsx`, `platform/src/app/auth/callback/route.ts`, `platform/src/app/panel/page.tsx` (lista mínima; Tarea 4 la completa), `platform/src/lib/supabase/{client,server,admin}.ts`, `platform/src/lib/pricing.ts`, `platform/src/lib/attribution.ts`, `platform/src/middleware.ts` (refresco de sesión y cookie `attribution`), `platform/src/components/ui/provider.tsx` (Chakra v3), `platform/src/theme.ts`, `platform/src/components/landing/{Hero,Examples,HowItWorks,Pricing,Faq}.tsx`, `platform/public/examples/*` (copias de `outputs/contact/p01.jpg, p02, p05, p07, p08, p14, p15` recortadas y los `outputs/deliver/p05|p15/model_web.glb` + `model.usdz`), `platform/.env.example`, `platform/README.md`
- Test: `platform/tests/unit/pricing.test.ts`, `platform/tests/unit/attribution.test.ts`, `platform/tests/e2e/landing.spec.ts` (Playwright: carga, títulos, CTA lleva a `/entrar`, bloque de precios muestra «9 €», «69 €», «169 €»)

**Interfaces:**
- Produces: `PACKS: readonly Pack[]` con `{ id: 'pieza_1'|'pieza_10'|'pieza_30', credits, priceCents, label, perPieceCents, highlighted }` y `formatEur(cents): string` («69 €», «6,90 €»); `parseAttribution(searchParams: URLSearchParams): Attribution | null` y `ATTRIBUTION_COOKIE = 'sh_attr'`; `createClient()` (browser), `createServerClient()` (cookies, RSC y server actions), `createAdminClient()` (service role, solo servidor, `server-only`); `requireUser()` que redirige a `/entrar` si no hay sesión y devuelve `{ user, profile }`.
- Consumes: nada de otras tareas (corre en paralelo con la 1 y la 3). Crear `platform/src/lib/database.types.ts` como stub tipado a mano con `profiles` y `pieces` mínimos; la Tarea 4 lo sustituye por el generado en `supabase/database.types.ts`.

- [ ] **Step 1: Tests unitarios de `pricing` y `attribution`** (`vitest`): `formatEur(6900) === '69 €'`, `formatEur(690) === '6,90 €'`, `formatEur(563) === '5,63 €'`, `PACKS[1].highlighted === true`; `parseAttribution(new URLSearchParams('utm_source=meta&utm_campaign=t1&ref=x'))` devuelve las tres claves y `null` sin ninguna.
- [ ] **Step 2: Ejecutarlos y ver que fallan.**
- [ ] **Step 3: Crear la app, el tema de Chakra v3** (paleta neutra cálida, tipografía con `next/font`: una serif para titulares y una sans para texto), proveedor, `layout.tsx` con metadata en español (`title`, `description`, `openGraph`), y los clientes de Supabase con `@supabase/ssr` según su documentación actual.
- [ ] **Step 4: Acceso por enlace mágico**: `/entrar` con formulario de correo (server action `signInWithOtp` con `emailRedirectTo` a `/auth/callback`, `data: { attribution }` leído de la cookie); `/auth/callback` intercambia el código y redirige a `/panel`; `requireUser()`.
- [ ] **Step 5: Landing** con las cinco secciones y los ejemplos reales (dos de ellos con `model-viewer` cargado solo al entrar en viewport); `middleware.ts` guarda `sh_attr` si vienen `utm_*`/`ref`.
- [ ] **Step 6: Tests pasan**, `pnpm build` verde, Lighthouse móvil de `/` ≥ 90 en rendimiento y SEO (`pnpm dlx lighthouse http://localhost:3000 --preset=desktop` no; usar `--form-factor=mobile`), anotar las cifras en el informe.
- [ ] **Step 7: Commit.**

### Task 3: Worker Python: reclamar piezas, generar con el harness y subir resultados

**Files:**
- Create: `src/platform_worker/__init__.py`, `src/platform_worker/db.py`, `src/platform_worker/storage.py`, `src/platform_worker/providers/{__init__,base,fake,tripo,fal}.py`, `src/platform_worker/pipeline.py`, `src/platform_worker/cli.py`, `src/platform_worker/intake.py`
- Modify: `pyproject.toml` (script `platform-worker = "platform_worker.cli:app"`), `.env.example` (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `PROVIDER=fake|tripo|fal`, `TRIPO_API_KEY`, `FAL_KEY`)
- Test: `tests/test_platform_worker_db.py`, `tests/test_platform_worker_pipeline.py`, `tests/test_platform_worker_intake.py`, `tests/fixtures/platform/*`

**Interfaces:**
- Consumes: funciones SQL de Tarea 1 por PostgREST (`POST /rest/v1/rpc/claim_next_piece`, `rpc/requeue_stale_pieces`), tablas por REST, Storage por `POST /storage/v1/object/{bucket}/{path}` con `x-upsert: true`; del harness: `harness.prep.clean.validate_input`, `harness.prep.requirements.explain`, `harness.variants.f_router.rule_classify`, `harness.variants.e_parametric`, `harness.post.blender_post.postprocess`, `harness.eval.geometry`, `harness.eval.render.render_views`, `harness.post.deliver.deliver`, `harness.core.models.Piece`.
- Produces: `WorkerDB(url, service_key)` con `claim_next() -> dict | None`, `requeue_stale(minutes=30) -> int`, `update_piece(id, **fields)`, `insert_model(row) -> dict`, `list_photos(piece_id) -> list[dict]`; `Storage.download(bucket, path, dst)`, `Storage.upload(bucket, path, src, content_type)`; `Provider` protocolo `generate(images: list[Path], dst_glb: Path, *, seed=None) -> GenerationOutcome` (misma firma que los clientes del harness) con `FakeProvider` (copia un GLB de fixture), `TripoProvider` (reusa `harness.clients.tripo.TripoClient`), `FalProvider` (`fal-ai/trellis` o `fal-ai/hunyuan3d/v3`, `httpx`, cola `queue.fal.run`, documentado por Context7/`fal.ai/docs`); `intake.check(piece_row, photo_paths) -> list[str]` (requisitos de foto + categorías excluidas por `kind`/`notes`); `pipeline.process_piece(db, storage, piece_row, *, provider, workdir, blender_bin) -> str` que devuelve el estado final (`review|needs_photos|failed`) y escribe `piece_models` con `render_paths`, `meta` (post, geometry, provider, candidate), `max_error`, `cost_usd`; CLI `platform-worker run [--once] [--poll-seconds 10] [--provider fake]` y `platform-worker piece <id>`.

- [ ] **Step 1: Tests** con `pytest-httpx` para `WorkerDB`/`Storage` (rutas y cabeceras exactas de PostgREST y Storage: `apikey`, `Authorization: Bearer`, `Prefer: return=representation`), para `intake.check` (lámpara → excluida; nota «cromo» → excluida; cabecero 3 cm → ok y `rectilinear` true) y para `process_piece` con `FakeProvider`, Blender simulado (monkeypatch de `postprocess`, `render_views`, `deliver` que escriben archivos reales en `tmp_path`) y `WorkerDB`/`Storage` falsos en memoria: pieza rectilínea → ruta E → `review` con un `piece_models`; orgánica → `FakeProvider` 2 candidatos → el de menor `max_error` queda `selected`; foto inválida → `needs_photos` con `error` en español; excepción del proveedor → `failed`; `requeue_stale` llamado al arrancar `run`.
- [ ] **Step 2: Ver que fallan.**
- [ ] **Step 3: Implementar** `db.py`, `storage.py`, `providers/`, `intake.py`, `pipeline.py` (workdir `runs/platform/{piece_id}/{attempt}/`, reutilizando el harness; en orgánicas 2 candidatos con `postprocess(fit_box=True)`; en E un candidato; renders de 4 vistas + `contact.jpg` con PIL; `deliver` → `model_web.glb` + `model.usdz` (2K, ≤ 60k) y una segunda llamada con `max_tris=15000, max_tex=512` cuyo GLB se renombra `model_preview.glb`; subida a `models`, `previews` y `renders`) y `cli.py` (typer; bucle con `--poll-seconds`; `--once`; mensajes en español; exit 2 sin `SUPABASE_SERVICE_ROLE_KEY`).
- [ ] **Step 4: Tests pasan** (`uv run pytest tests/test_platform_worker*.py -q`, y la suite completa) y prueba real: con `.env` apuntando a `oyntcaxzskzntiyzxquy`, insertar por REST una pieza `test_` rectilínea de 165×60×6 con `outputs/clean/p12_tapizado.png` subida a `photos/` y ejecutar `platform-worker run --once --provider fake`; comprobar en Storage `models/{id}/1/model_web.glb`, `previews/{id}/1/model_preview.glb` y estado `review`; borrar la pieza de prueba. Anotar tiempos.
- [ ] **Step 5: Commit.**

### Task 4: Flujo de pieza en la web: nueva pieza, estado, resultado y acciones

**Files:**
- Copy: `supabase/database.types.ts` → `platform/src/lib/database.types.ts` (sustituye el stub de la Tarea 2)
- Create: `platform/src/app/piezas/nueva/page.tsx`, `platform/src/app/piezas/nueva/actions.ts`, `platform/src/app/piezas/[id]/page.tsx`, `platform/src/app/piezas/[id]/actions.ts`, `platform/src/components/pieces/{PieceForm,PhotoDropzone,StatusSteps,ModelViewer,ResultActions,PieceCard}.tsx`, `platform/src/lib/pieces.ts`, `platform/src/lib/validation.ts`
- Modify: `platform/src/app/panel/page.tsx` (lista con `PieceCard`, saldo, botón «Nueva pieza»)
- Test: `platform/tests/unit/validation.test.ts`, `platform/tests/e2e/piece-flow.spec.ts`

**Interfaces:**
- Consumes: `requireUser`, clientes de Supabase (Tarea 2); funciones SQL `approve_piece`, `request_new_version`, `reject_piece`, `credit_balance` (Tarea 1); rutas de Storage de Global Constraints.
- Produces: `validatePieceInput(input): { ok: true, value } | { ok: false, errors: Record<string,string> }` (nombre 2–80 chars; medidas 1–400 cm; 1–4 fotos; cada foto `image/jpeg|png|webp` ≤ 20 MB; `kind` del enum); server actions `createPiece(formData)` (sube fotos al bucket `photos` desde el cliente con URL firmada o directamente con el cliente de navegador, inserta `pieces` + `piece_photos`, redirige a `/piezas/[id]`; error `daily_limit` → mensaje «Has llegado a las 3 piezas de hoy»), `downloadPiece(id)` (llama a `approve_piece`; devuelve URLs firmadas de GLB y USDZ, 1 h), `requestNewVersion(id)`, `rejectPiece(id, reason)`; `getPieceForUser(id)` (404 si no es suya); `previewUrl(model)` pública; `signedRenderUrls(model)` 1 h.

- [ ] **Step 1: Tests de `validatePieceInput`** (casos límite de medidas, 5 fotos → error, tipo inválido, foto de 25 MB → error con mensaje en español) y el test E2E de Playwright escrito contra la app con un usuario de prueba creado por `auth.admin` y sesión inyectada por cookie: crear pieza (fixture `tests/fixtures/platform/p12.png`), ver `/piezas/[id]` en «En cola», simular el worker insertando `piece_models` + `status='ready'` por service role, ver el visor (con `model_preview.glb`) y las medidas; pulsar «Descargar» sin saldo → mensaje «Necesitas 1 crédito» con enlace a `/creditos`; tras `grant_credits(+1)` por service role, «Descargar» → estado «Descargada», enlaces GLB y USDZ firmados, saldo 0; usuario B abre `/piezas/[id]` de A → 404.
- [ ] **Step 2: Ver que fallan.**
- [ ] **Step 3: Implementar** formulario (Chakra v3, arrastrar fotos, previsualización, campos de medidas con «cm», selector de tipo, pregunta de pieza recta con tres opciones, aviso de categorías excluidas), página de pieza con `StatusSteps` (polling cada 10 s mientras no esté `ready|approved|rejected|needs_photos|failed`, con `router.refresh()`), `ModelViewer` (`<model-viewer src={preview} ar ar-modes="webxr scene-viewer quick-look" camera-controls ar-scale="fixed">`, sin `ios-src`: Quick Look genera el USDZ al vuelo desde la previsualización), `ResultActions` con los tres botones («Descargar (1 crédito)», «Pedir otra versión», «No me sirve») y sus diálogos, estados `needs_photos` (muestra `error` y botón «Corregir fotos» que vuelve al formulario con los datos), `rejected`, `failed`.
- [ ] **Step 4: Tests pasan**, `pnpm build` verde.
- [ ] **Step 5: Commit.**

### Task 5: Créditos y pagos con Stripe Checkout

**Files:**
- Create: `platform/src/app/creditos/page.tsx`, `platform/src/app/creditos/actions.ts`, `platform/src/app/api/stripe/webhook/route.ts`, `platform/src/lib/stripe.ts`, `platform/src/lib/credits.ts`, `platform/scripts/stripe-setup.ts` (crea producto «Piezas 3D» y los tres precios con `lookup_key`, idempotente)
- Test: `platform/tests/unit/webhook.test.ts`, `platform/tests/unit/credits.test.ts`, `platform/tests/e2e/credits.spec.ts`

**Interfaces:**
- Consumes: `PACKS` (Tarea 2); `grant_credits`, `credit_balance`, tabla `purchases` (Tarea 1).
- Produces: `createCheckoutSession(packId) -> url` (server action; `mode: 'payment'`, `price` por `lookup_key`, `client_reference_id = user.id`, `metadata: { pack, credits }`, `success_url = /creditos?ok=1&session_id={CHECKOUT_SESSION_ID}`, `cancel_url = /creditos`); `handleStripeEvent(event) -> { handled: boolean }` puro (sin HTTP) que en `checkout.session.completed` con `payment_status === 'paid'` inserta `purchases` y llama a `grant_credits(user, credits, 'purchase', session.id)`; `getLedger(userId) -> { balance, entries }`.

- [ ] **Step 1: Tests**: `handleStripeEvent` con un evento `checkout.session.completed` construido a mano abona créditos una vez y la segunda llamada con el mismo `session.id` no (admin client falso en memoria); evento de otro tipo → `handled: false`; la ruta del webhook rechaza una firma inválida con 400 (`stripe.webhooks.generateTestHeaderString` con un secreto de prueba); E2E: `/creditos` muestra saldo y los tres paquetes; sin claves de Stripe el botón «Comprar» muestra «Pagos no configurados» en lugar de fallar.
- [ ] **Step 2: Ver que fallan.**
- [ ] **Step 3: Implementar** con el SDK de Stripe (versión fijada, API version por defecto del SDK), `stripe-setup.ts` ejecutable con `STRIPE_SECRET_KEY`, página de créditos (saldo grande, movimientos con fecha, tres tarjetas de paquete con «Más elegido»), webhook con `request.text()` y `constructEvent`.
- [ ] **Step 4: Tests pasan**, `pnpm build`. Si `STRIPE_SECRET_KEY` existe en `.env.local`, ejecutar `stripe-setup.ts` y un pago de prueba con tarjeta `4242…` reenviando el webhook con `stripe listen --forward-to localhost:3000/api/stripe/webhook`; anotar el resultado; si no existe, anotarlo como pendiente de Jorge.
- [ ] **Step 5: Commit.**

### Task 6: Cola de revisión interna

**Files:**
- Create: `platform/src/app/admin/revision/page.tsx`, `platform/src/app/admin/revision/[id]/page.tsx`, `platform/src/app/admin/revision/actions.ts`, `platform/src/components/admin/{ReviewCard,ContactSheet}.tsx`, `platform/src/lib/admin.ts`
- Test: `platform/tests/e2e/admin-review.spec.ts`

**Interfaces:**
- Consumes: `requireUser` (Tarea 2) + `profile.is_admin`; vista `admin_review_queue`, buckets `renders` (firmados) y `models` (Tarea 1); estados de Global Constraints.
- Produces: `requireAdmin()` (404 si no es admin); server actions `showToClient(pieceId)` (`review→ready`), `regenerate(pieceId, note)` (`review→queued`, `attempt+1`, `review_note`), `rejectInternally(pieceId, reason)` (`review→rejected`, `reject_reason` visible al cliente); `markSelectedModel(pieceId, modelId)`.

- [ ] **Step 1: Test E2E**: usuario admin (creado por `auth.admin` con `is_admin=true`) ve la cola con una pieza en `review` (insertada por service role con dos `piece_models`), abre su detalle con hoja de contacto, foto original, error de escala y proveedor; elige el segundo modelo, pulsa «Mostrar al cliente» → la pieza pasa a `ready` y `selected` es el segundo; usuario no admin → 404 en `/admin/revision`.
- [ ] **Step 2: Ver que falla.**
- [ ] **Step 3: Implementar** (lista ordenada por antigüedad, visor 3D en el detalle, atajos de teclado A/R/X opcionales no requeridos).
- [ ] **Step 4: Test pasa**, `pnpm build`.
- [ ] **Step 5: Commit.**

### Task 7: Avisos, prueba de extremo a extremo real, documentación y preparación de anuncios

**Files:**
- Create: `platform/src/lib/notify.ts` (Resend si `RESEND_API_KEY`, si no no-op con log), `platform/src/app/api/internal/notify/route.ts` (llamada del worker con `WORKER_SHARED_SECRET` cuando una pieza pasa a `ready`; el worker la llama desde `pipeline.py` solo si está configurada), `platform/src/components/Analytics.tsx` (Meta Pixel y GA opcionales por env; eventos `signup`, `piece_created`, `piece_approved`, `purchase`), `platform/tests/e2e/full-flow.spec.ts`, `platform/README.md` (actualizar: despliegue en Vercel, variables, worker en el Mac, cómo pasar a producción Stripe), `docs/anuncios.md` (qué medir en la prueba: coste por registro, por pieza creada, por pieza aprobada, por compra; UTM a usar)
- Modify: `src/platform_worker/pipeline.py` (aviso al pasar a `review`/`ready` si hay `NOTIFY_URL` + secreto), `justfile` (`platform-dev`, `platform-test`, `worker`), `README.md` raíz (sección «Plataforma»)
- Test: `platform/tests/unit/notify.test.ts`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: `notifyPieceReady(pieceId)`; `full-flow.spec.ts` recorre: registro → pieza rectilínea con `p12.png` → `platform-worker run --once --provider fake` lanzado por el test (Blender real si `HARNESS_BLENDER_TEST_BIN`, si no `fake` total) → admin muestra → cliente ve el visor gratis → descarga bloqueada sin saldo → (si hay Stripe) compra y descarga; si no, crédito abonado por service role y descarga.

- [ ] **Step 1: Tests** de `notify` (sin clave → no-op y `{ sent: false }`; con clave → `httpx`/fetch simulado con el cuerpo esperado) y `full-flow.spec.ts`.
- [ ] **Step 2: Ver que fallan.**
- [ ] **Step 3: Implementar** avisos, analítica, documentación y recetas.
- [ ] **Step 4: Todo verde**: `pnpm --dir platform test`, `pnpm --dir platform test:e2e`, `uv run pytest -q`, `pnpm --dir platform build`, lint y ruff. Lighthouse móvil de `/` ≥ 90. Recorrido manual con p07 o p15 real hasta el visor y anotar capturas en `outputs/platform/`.
- [ ] **Step 5: Commit.**
