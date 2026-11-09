# Supabase — plataforma 3D

Proyecto alojado `site-hassle` (ref `oyntcaxzskzntiyzxquy`, eu-west-1). No hay Supabase local ni Docker: las migraciones de `migrations/` son la fuente de verdad y se aplican al proyecto alojado.

## Aplicar migraciones

```sh
supabase link --project-ref oyntcaxzskzntiyzxquy
supabase db push            # --dry-run para ver qué aplicaría
```

El 2026-11-09 se aplicaron las tres migraciones con `supabase db push` (CLI 2.116): no pidió contraseña de base de datos, la CLI usa un rol de acceso temporal. Si alguna vez la pidiera y no la tienes, la alternativa es la herramienta MCP de Supabase `apply_migration` sobre el proyecto, una llamada por archivo, en orden y con el nombre del archivo sin extensión.

Tras cambiar el esquema, regenera los tipos y cópialos a la web conservando el bloque de alias del final de `platform/src/lib/database.types.ts`:

```sh
supabase gen types typescript --project-id oyntcaxzskzntiyzxquy > supabase/database.types.ts
```

## Qué hay

| Migración | Contenido |
|---|---|
| `20261109000001_init.sql` | Enums `piece_kind`, `piece_status`, `credit_reason`; tablas `profiles`, `pieces`, `piece_photos`, `piece_models`, `credit_ledger`, `purchases`; triggers `handle_new_user` y `set_updated_at`; RLS y privilegios por columna. |
| `20261109000002_functions.sql` | `credit_balance`, `pieces_created_today`, `daily_piece_limit` (3), trigger `enforce_daily_piece_limit`, `approve_piece`, `request_new_version`, `reject_piece`, `claim_next_piece`, `requeue_stale_pieces`, `grant_credits`; vista `admin_review_queue`. |
| `20261109000003_storage.sql` | Buckets `photos` (privado, 20 MB, JPEG/PNG/WebP), `previews` (público), `models` y `renders` (privados) y políticas de `photos`. |
| `20261109000004_review_queue_selected.sql` | `admin_review_queue` elige, dentro del último intento, el candidato `selected`; el cliente solo ve los `piece_models` del intento actual de la pieza. |
| `20261109000005_attribution_filter.sql` | `handle_new_user` filtra la atribución del registro: solo `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` y `ref`, como texto de 200 caracteres como máximo; el resto se descarta y, si no queda nada, `attribution` es `null` (cualquiera con la clave anónima puede mandar `data` arbitraria a `/auth/v1/otp`). |
| `20261109000006_piece_support.sql` | `pieces.support` (`patas`, `paneles`, `caja`, `no_se` o null): «¿Cómo se apoya la pieza?»; el cliente puede insertarla. |
| `20261109000007_hardening.sql` |
| `20261109000011_anonymous_trial.sql` | Prueba gratis anónima: `anonymous_daily_piece_limit()` (1) y `enforce_daily_piece_limit` con 1 pieza/día si `auth.jwt()->>'is_anonymous'`; `handle_new_user` guarda también la clave `source`; trigger `on_auth_user_email_changed` copia `auth.users.email` a `profiles.email`; `claim_anonymous_pieces(from, to)` (solo servicio) pasa piezas, filas de fotos, libro y compras de un usuario anónimo a una cuenta (la web mueve antes los objetos de `photos`). |
| `20261109000012_trial_ips.sql` | Tabla `trial_ips(ip_hash, created_at)` (solo servicio, RLS sin políticas): SHA-256 con sal de la IP de cada pieza anónima, para el tope de 3 por red en 24 h. |
| `20261109000010_claim_skip_thumb.sql` | `claim_next_piece` no cuenta la miniatura (`…/thumb.{jpg,png,webp}`) como foto: una pieza con solo la miniatura espera como una sin fotos. |
 CHECK de `pieces` iguales al formulario (nombre 2–80, notas ≤ 500, medidas 1–400); trigger `check_piece_photo` en `piece_photos` (ruta `{user_id de la pieza}/{piece_id}/{n\|thumb}.{jpg,png,webp}`, máximo 4 fotos + 1 miniatura); columnas `provider_cost_usd` y `not_before` en `pieces`; `claim_next_piece` solo reclama piezas con fotos (o de más de 10 min) y sin `not_before` futuro; `provider_spend_today()`; lectura por columnas para el cliente en `pieces` y `piece_models`; `request_new_version`/`reject_piece` devuelven `{ok, status, attempt}`; `credit_ledger.stripe_event_id` único y `purchases.stripe_payment_intent`; el cliente ya no puede actualizar `profiles.attribution`; política de subida de `photos` con la forma exacta del nombre; índice único parcial de un `selected` por pieza e intento; `admin_review_queue` recreada. |

### Quién puede qué

- **Cliente** (clave anónima + JWT del usuario): lee sus filas de `profiles`, `pieces`, `piece_photos`, `credit_ledger` y `purchases`; lee `piece_models` de sus piezas solo cuando están en `ready`, `approved` o `rejected` (nunca en revisión) y solo los del intento actual (`attempt` de la pieza). **Lectura por columnas:** de `pieces` solo `id, user_id, name, kind, width_cm, height_cm, depth_cm, rectilinear, support, notes, status, attempt, error, reject_reason, created_at, updated_at` (nunca `review_note`, `route`, `claimed_at`, `provider_cost_usd`, `not_before`); de `piece_models` solo `id, piece_id, attempt, preview_path, glb_path, usdz_path, render_paths, selected, created_at` (nunca `meta`, `cost_usd`, `provider`). Un `select=*` con la sesión del cliente devuelve error: pide siempre columnas explícitas (también con `Prefer: return=representation`). Inserta piezas propias en `queued` (solo las columnas del formulario: `id`, `user_id`, `name`, `kind`, medidas, `rectilinear`, `support`, `notes`, `status`; `user_id` toma `auth.uid()` por defecto) y fotos de piezas propias en `queued` con `storage_path` `{user_id}/{piece_id}/{n}.{jpg,png,webp}` (máximo 4, más `thumb`). No puede actualizar `profiles` (la atribución la pone el trigger al registrarse). Todo cambio de estado pasa por `approve_piece`, `request_new_version` y `reject_piece`.
- **Worker y admin** (clave de servicio, se salta RLS): todo lo demás, incluidas `claim_next_piece`, `requeue_stale_pieces`, `grant_credits` y la vista `admin_review_queue`, que el cliente no puede ejecutar ni leer.

### Funciones

Los errores se lanzan con el código como mensaje; PostgREST lo devuelve en `message`: `not_authenticated`, `forbidden`, `not_found` (pieza inexistente o de otro usuario), `invalid_state`, `insufficient_credits`, `max_versions`, `daily_limit`.

| Función | Quién | Qué hace |
|---|---|---|
| `credit_balance(p_user)` → int | cliente (solo su saldo), servicio | Suma de `credit_ledger.delta`. |
| `pieces_created_today(p_user)` → int | cliente (solo suyas), servicio | Piezas creadas desde las 00:00 de Europe/Madrid. |
| `daily_piece_limit()` → int | todos | 3. |
| `approve_piece(p_piece_id)` → jsonb | cliente dueño | `ready → approved` consumiendo 1 crédito (`consume −1` con `piece_id`); devuelve `{ok, balance}`; si ya estaba `approved`, `{ok, already: true, balance}` sin consumir. Bloqueo por usuario (`pg_advisory_xact_lock`): dos clics o dos piezas a la vez nunca gastan más de lo que hay. |
| `request_new_version(p_piece_id)` → jsonb | cliente dueño | `ready → queued`, `attempt + 1`; devuelve `{ok, status, attempt}`; `max_versions` si `attempt ≥ 3` (también cuenta un «Regenerar» del admin). |
| `reject_piece(p_piece_id, p_reason)` → jsonb | cliente dueño | `ready → rejected` con `reject_reason` (500 caracteres como máximo); devuelve `{ok, status, attempt}`. |
| `claim_next_piece()` → pieces | servicio | Toma la pieza `queued` más antigua que ya tenga alguna fila en `piece_photos` (o tenga más de 10 min, para que el worker la pase a `needs_photos`) y cuyo `not_before` haya pasado (`FOR UPDATE SKIP LOCKED`), y la pasa a `generating` con `claimed_at`. Con la cola vacía devuelve una fila con todas las columnas a `null` (comprobar `id`). Pensada para **un solo worker**. |
| `provider_spend_today()` → numeric | servicio | USD gastados hoy (desde las 00:00 de Madrid) en proveedores: `piece_models.cost_usd` de hoy más `pieces.provider_cost_usd` de las piezas tocadas hoy (aproximación: ese coste acumula todos los intentos fallidos de la pieza). |

| `requeue_stale_pieces(p_minutes = 30)` → int | servicio | Devuelve a `queued` las `generating` con `claimed_at` más antiguo que `p_minutes`; devuelve cuántas. |
| `grant_credits(p_user, p_delta, p_reason, p_session)` → int | servicio | Inserta en el libro; idempotente por `p_session` (`stripe_session_id` único); con `p_session` nulo siempre suma. Devuelve el saldo. |

El trigger `enforce_daily_piece_limit` solo actúa con JWT `authenticated`: el worker y el admin (servicio) pueden crear o reencolar sin límite. Ojo: las piezas creadas por el servicio a nombre de un usuario sí cuentan para su cupo diario (el recuento incluye todas sus piezas del día).

La vista `admin_review_queue` usa `p.*`: Postgres fija la lista de columnas al crearla, así que hay que recrearla (en una migración nueva, con `create or replace view` añadiendo las columnas al final o `drop` + `create`) cada vez que `pieces` gane columnas; si no, no aparecerán.

### Storage

| Bucket | Ruta | Acceso |
|---|---|---|
| `photos` | `{user_id}/{piece_id}/{n}.{jpg,png,webp}`, `thumb.jpg` | Privado; el usuario lee y borra bajo su prefijo `{user_id}/`, y sube o sobrescribe solo nombres con la forma exacta `{su uid}/{uuid}/{n\|thumb}.{jpg,png,webp}`. |

| `previews` | `{piece_id}/{attempt}/model_preview.glb` | Público por URL; sin política de lectura, así que no se puede listar. Escribe el servicio. |
| `models` | `{piece_id}/{attempt}/model_web.glb`, `model.usdz` | Solo servicio; la web firma URLs para piezas `approved` del dueño. |
| `renders` | `{piece_id}/{attempt}/{front,left,back,three_quarter}.png`, `contact.jpg` | Solo servicio (admin con URLs firmadas). |

## Tests

```sh
uv run pytest tests/test_supabase_schema.py -q
```

Van contra el proyecto alojado con las claves de `platform/.env.local` (o del entorno) y se saltan si no hay `SUPABASE_SERVICE_ROLE_KEY`. Crean dos usuarios `test_*` por ejecución (Auth limita los inicios de sesión por IP), vacían sus piezas y créditos antes de cada test y los borran al final (en cascada).

## Auth: enlace mágico

- **Dos plantillas**, ambas en español y con rutas relativas a la raíz del repo (desde donde se ejecuta la CLI):
  - `[auth.email.template.confirmation]` → `supabase/templates/confirmation.html`: el **primer** inicio de sesión (alta) recibe el correo «Confirm signup», no el de enlace mágico. Enlace `{{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=signup`.
  - `[auth.email.template.magic_link]` → `supabase/templates/magic_link.html`: los inicios de sesión siguientes. Enlace `{{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=magiclink`.
  
  `/auth/callback` verifica el `token_hash` con `verifyOtp`, sin depender del verificador PKCE, así que el enlace funciona en cualquier navegador o dispositivo. Se aplican con `supabase config push --project-ref oyntcaxzskzntiyzxquy`.
- **Requisito: SMTP propio para las dos.** Con el plan gratuito y el correo por defecto de Supabase, el `config push` responde 400 «Email template modification is not available for free tier projects using the default email provider» (probado el 2026-11-09 con las dos plantillas). Configura SMTP (p. ej. Resend con dominio verificado → Dashboard → Authentication → SMTP, o `[auth.email.smtp]` en `config.toml`) y repite el push. Mientras tanto se envían las plantillas por defecto en inglés (PKCE, `?code=`, solo en el mismo navegador), que el callback también acepta; por eso la web aún dice «ábrelo en este mismo navegador/dispositivo». Cuando las plantillas estén aplicadas, quita esa indicación de `platform/src/app/entrar/SignInForm.tsx`.

- **`{{ .SiteURL }}`** es `site_url` de `[auth]`: en producción debe ser el dominio público (ver `platform/README.md`, Despliegue), o los enlaces irán a `localhost`.
- **Límite de envío:** el SMTP por defecto de Supabase solo envía unos pocos correos de Auth por hora (Dashboard → Authentication → Rate Limits); con SMTP propio el límite se sube allí. Supabase también limita las verificaciones por IP (los e2e reintentan ante 429).
- `config push` sube **todo** `config.toml`: revisa el diff que imprime antes de confirmar (los valores ausentes en el archivo toman los de la CLI por defecto).
