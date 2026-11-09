# Supabase — plataforma 3D

Proyecto alojado `site-hassle` (ref `oyntcaxzskzntiyzxquy`, eu-west-1). No hay Supabase local ni Docker: las migraciones de `migrations/` son la fuente de verdad y se aplican al proyecto alojado.

## Aplicar migraciones

```sh
supabase link --project-ref oyntcaxzskzntiyzxquy
supabase db push            # --dry-run para ver qué aplicaría
```

El 2026-11-09 se aplicaron las tres migraciones con `supabase db push` (CLI 2.116): no pidió contraseña de base de datos, la CLI usa un rol de acceso temporal. Si alguna vez la pidiera y no la tienes, la alternativa es la herramienta MCP de Supabase `apply_migration` sobre el proyecto, una llamada por archivo, en orden y con el nombre del archivo sin extensión.

Tras cambiar el esquema, regenera los tipos (la Tarea 4 los copia a `platform/src/lib/`):

```sh
supabase gen types typescript --project-id oyntcaxzskzntiyzxquy > supabase/database.types.ts
```

## Qué hay

| Migración | Contenido |
|---|---|
| `20261109000001_init.sql` | Enums `piece_kind`, `piece_status`, `credit_reason`; tablas `profiles`, `pieces`, `piece_photos`, `piece_models`, `credit_ledger`, `purchases`; triggers `handle_new_user` y `set_updated_at`; RLS y privilegios por columna. |
| `20261109000002_functions.sql` | `credit_balance`, `pieces_created_today`, `daily_piece_limit` (3), trigger `enforce_daily_piece_limit`, `approve_piece`, `request_new_version`, `reject_piece`, `claim_next_piece`, `requeue_stale_pieces`, `grant_credits`; vista `admin_review_queue`. |
| `20261109000003_storage.sql` | Buckets `photos` (privado, 20 MB, JPEG/PNG/WebP), `previews` (público), `models` y `renders` (privados) y políticas de `photos`. |

### Quién puede qué

- **Cliente** (clave anónima + JWT del usuario): lee sus filas de `profiles`, `pieces`, `piece_photos`, `credit_ledger` y `purchases`; lee `piece_models` de sus piezas solo cuando están en `ready`, `approved` o `rejected` (nunca en revisión). Inserta piezas propias en `queued` (solo las columnas del formulario: `id`, `user_id`, `name`, `kind`, medidas, `rectilinear`, `notes`, `status`; `user_id` toma `auth.uid()` por defecto) y fotos de piezas propias en `queued` con `storage_path` `{user_id}/{piece_id}/…`. De `profiles` solo puede actualizar `attribution`. Todo cambio de estado pasa por `approve_piece`, `request_new_version` y `reject_piece`.
- **Worker y admin** (clave de servicio, se salta RLS): todo lo demás, incluidas `claim_next_piece`, `requeue_stale_pieces`, `grant_credits` y la vista `admin_review_queue`, que el cliente no puede ejecutar ni leer.

### Funciones

Los errores se lanzan con el código como mensaje; PostgREST lo devuelve en `message`: `not_authenticated`, `forbidden`, `not_found` (pieza inexistente o de otro usuario), `invalid_state`, `insufficient_credits`, `max_versions`, `daily_limit`.

| Función | Quién | Qué hace |
|---|---|---|
| `credit_balance(p_user)` → int | cliente (solo su saldo), servicio | Suma de `credit_ledger.delta`. |
| `pieces_created_today(p_user)` → int | cliente (solo suyas), servicio | Piezas creadas desde las 00:00 de Europe/Madrid. |
| `daily_piece_limit()` → int | todos | 3. |
| `approve_piece(p_piece_id)` → jsonb | cliente dueño | `ready → approved` consumiendo 1 crédito (`consume −1` con `piece_id`); devuelve `{ok, balance}`; si ya estaba `approved`, `{ok, already: true, balance}` sin consumir. Bloqueo por usuario (`pg_advisory_xact_lock`): dos clics o dos piezas a la vez nunca gastan más de lo que hay. |
| `request_new_version(p_piece_id)` → pieces | cliente dueño | `ready → queued`, `attempt + 1`; `max_versions` si `attempt ≥ 3`. |
| `reject_piece(p_piece_id, p_reason)` → pieces | cliente dueño | `ready → rejected` con `reject_reason`. |
| `claim_next_piece()` → pieces | servicio | Toma la pieza `queued` más antigua (`FOR UPDATE SKIP LOCKED`) y la pasa a `generating` con `claimed_at`. Con la cola vacía devuelve una fila con todas las columnas a `null` (comprobar `id`). |
| `requeue_stale_pieces(p_minutes = 30)` → int | servicio | Devuelve a `queued` las `generating` con `claimed_at` más antiguo que `p_minutes`; devuelve cuántas. |
| `grant_credits(p_user, p_delta, p_reason, p_session)` → int | servicio | Inserta en el libro; idempotente por `p_session` (`stripe_session_id` único); con `p_session` nulo siempre suma. Devuelve el saldo. |

El trigger `enforce_daily_piece_limit` solo actúa con JWT `authenticated`: el worker y el admin (servicio) pueden crear o reencolar sin límite.

### Storage

| Bucket | Ruta | Acceso |
|---|---|---|
| `photos` | `{user_id}/{piece_id}/{n}.jpg` | Privado; el usuario lee, sube, sobrescribe y borra bajo su prefijo `{user_id}/`. |
| `previews` | `{piece_id}/{attempt}/model_preview.glb` | Público por URL; sin política de lectura, así que no se puede listar. Escribe el servicio. |
| `models` | `{piece_id}/{attempt}/model_web.glb`, `model.usdz` | Solo servicio; la web firma URLs para piezas `approved` del dueño. |
| `renders` | `{piece_id}/{attempt}/{front,left,back,three_quarter}.png`, `contact.jpg` | Solo servicio (admin con URLs firmadas). |

## Tests

```sh
uv run pytest tests/test_supabase_schema.py -q
```

Van contra el proyecto alojado con las claves de `platform/.env.local` (o del entorno) y se saltan si no hay `SUPABASE_SERVICE_ROLE_KEY`. Crean dos usuarios `test_*` por ejecución (Auth limita los inicios de sesión por IP), vacían sus piezas y créditos antes de cada test y los borran al final (en cascada).
