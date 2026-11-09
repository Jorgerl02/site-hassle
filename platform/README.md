# Pieza 3D — aplicación web

Next.js 16 (App Router) + Chakra UI v3 + Supabase (Auth por enlace mágico, Postgres, Storage). Es la web del MVP descrito en `docs/superpowers/specs/2026-11-09-plataforma-3d-mvp-design.md`; el worker que genera las piezas vive en `src/platform_worker/` (Python).

## Arrancar en local

```bash
cp .env.example .env.local   # y rellena las claves (ver abajo)
pnpm install
pnpm dev                     # http://localhost:3000
```

## Comandos

| Comando | Qué hace |
|---|---|
| `pnpm dev` | Servidor de desarrollo |
| `pnpm build` | Build de producción (obligatorio y verde antes de cualquier push) |
| `pnpm start` | Sirve el build |
| `pnpm lint` | ESLint |
| `pnpm test` | Tests unitarios (Vitest, `tests/unit`) |
| `pnpm test:e2e` | Tests de extremo a extremo (Playwright, `tests/e2e`) contra el proyecto alojado de Supabase. Hace `pnpm build` y arranca **un** servidor en el puerto 3150 (o reutiliza el que ya escuche ahí), y los ejecuta en serie (`workers: 1`): Supabase Auth responde 429 si llegan muchos inicios de sesión a la vez. `full-flow.spec.ts` lanza el worker real con Blender (≈ 45 s) |
| `pnpm stripe:setup` | Crea o actualiza en Stripe el producto y los tres precios (`pieza_1`, `pieza_10`, `pieza_30`); idempotente |

Desde la raíz del repo hay atajos de `just`: `just platform-dev`, `just platform-test`, `just platform-e2e` y `just worker`.

**Para el E2E completo, para antes el worker de producción** (`just worker`): `run --once` reclama la pieza más antigua de la cola y un worker en marcha podría llevarse la del test (o el test una pieza real).

**Recomendado: un proyecto de Supabase de staging para los e2e.** Hoy corren contra el proyecto alojado `oyntcaxzskzntiyzxquy` (usuarios `test_*` que se borran al terminar); en cuanto haya clientes reales, crea un proyecto de staging, aplica las migraciones y apunta `.env.local` de los e2e a él. El servidor de los e2e arranca siempre con `RESEND_API_KEY` vacía (`playwright.config.ts`): un test nunca manda correos.

El build de los e2e lleva ids de medición falsos (`NEXT_PUBLIC_META_PIXEL_ID`/`NEXT_PUBLIC_GA_ID`, salvo que exportes los tuyos) para que exista el aviso de cookies; todas las specs salvo `consent.spec.ts` empiezan con `sh_consent=denied` guardado. Las peticiones a Meta y Google de `consent.spec.ts` se responden en local. Antes de medir Lighthouse o servir en local, vuelve a hacer `pnpm build` sin esos ids.

Si reutilizas un servidor ya arrancado en el 3150 para los e2e, arráncalo con `WORKER_SHARED_SECRET=e2e-worker-secret` (el mismo que usa el test del recorrido completo) o el aviso del worker fallará.

Lighthouse móvil de la landing (con `pnpm start` corriendo):

```bash
pnpm dlx lighthouse http://localhost:3000 --form-factor=mobile --screenEmulation.mobile \
  --only-categories=performance,seo --output=json --output-path=/tmp/lh.json --chrome-flags="--headless"
```

## Claves (`.env.local`)

| Variable | Obligatoria | Dónde se usa |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Sí | Clientes de Supabase (navegador, servidor y proxy) |
| `SUPABASE_SERVICE_ROLE_KEY` | Sí | `createAdminClient()`, solo servidor; salta RLS |
| `NEXT_PUBLIC_SITE_URL` | **Sí en producción** | Origen público: enlaces mágicos, enlaces de los correos, `metadataBase`, canonical y sitemap. Sin ella todo apunta a `http://localhost:3000` |
| `STRIPE_SECRET_KEY` | Para cobrar | Checkout. Sin ella, `/creditos` muestra «Pagos no configurados» |
| `STRIPE_WEBHOOK_SECRET` | Para cobrar | Firma del webhook `/api/stripe/webhook` (sin ella responde 503) |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | No (reservada) | No la usa el código actual (Checkout alojado) |
| `RESEND_API_KEY` | No | Correos. Sin ella cada aviso es un no-op que se anota en el log |
| `NOTIFY_FROM_EMAIL` | Con Resend | Remitente en un dominio verificado en Resend, p. ej. `Pieza 3D <avisos@tudominio.es>`. Vacío: remitente de pruebas de Resend (solo entrega al dueño de la cuenta) |
| `ADMIN_NOTIFY_EMAIL` | No | Quién recibe «Pieza en revisión», «Pieza fallida» y «Presupuesto diario agotado» |
| `WORKER_SHARED_SECRET` | No | Activa `POST /api/internal/notify` (lo llama el worker). El mismo valor va en el `.env` de la raíz |
| `NEXT_PUBLIC_META_PIXEL_ID`, `NEXT_PUBLIC_GA_ID` | No | Meta Pixel y GA4. Vacías: no se carga ningún script de terceros ni aparece el aviso de cookies |
| `NEXT_PUBLIC_CONTACT_EMAIL` | Sí en producción | Correo de contacto de `/privacidad` (derechos RGPD) |

## Avisos por correo

- **Pieza lista (cliente):** al pulsar «Mostrar al cliente» en `/admin/revision/[id]`, la acción llama a `notifyPieceReady(pieceId)` después de responder (`after()`): «Tu pieza «…» está lista» con el enlace a `/piezas/[id]`. Lleva `Idempotency-Key: piece-ready/{id}` (Resend no lo repite en 24 h).
- **Pieza en revisión (admin):** el worker, al dejar una pieza en `review`, hace `POST {NOTIFY_URL}` con `Authorization: Bearer {WORKER_SHARED_SECRET}` y `{ pieceId, status: "review" }`; la ruta `/api/internal/notify` manda el correo a `ADMIN_NOTIFY_EMAIL`. Sin `NOTIFY_URL` o sin secreto, el worker no avisa; un aviso fallido nunca hace fallar la pieza.
- **Pieza fallida (admin):** igual, con `status: "failed"`. El detalle técnico queda en `pieces.error` y se ve en la sección «Fallidas» de `/admin/revision` («Reintentar» la devuelve a la cola en el mismo intento; «Rechazar» la cierra con un motivo para el cliente). El cliente solo ve «No hemos podido generar esta pieza. Lo revisamos y te escribimos.».
- **Presupuesto agotado (admin):** `status: "budget"`, una vez al día (`Idempotency-Key: budget/{fecha}`), cuando el worker llega a `WORKER_DAILY_BUDGET_USD`.
- Todo vive en `src/lib/notify.ts` (API REST de Resend con `fetch`, sin SDK). Ningún aviso lanza excepciones.

## Analítica para anuncios

`src/components/Analytics.tsx` (en el layout raíz) carga Meta Pixel y GA4 solo si hay id **y el visitante ha aceptado** en el aviso de cookies (`src/components/CookieConsent.tsx`, barra inferior con «Aceptar» / «Rechazar» y enlace a `/privacidad`). La elección se guarda en `localStorage` (`sh_consent` = `granted|denied` y `sh_consent_at`) durante 180 días; en `/privacidad` se puede cambiar. Sin id configurado no hay aviso. Con consentimiento, los scripts se cargan con `lazyOnload` y se envía una vista de página por navegación (origen + ruta, sin query string). Antes del consentimiento no se envía ningún evento (se pierden, no se encolan).

En Meta Events Manager, **desactiva «Automatic Advanced Matching»** del píxel: enviaría a Meta datos de formularios (como el correo de `/entrar`) sin que lo hayamos previsto en `/privacidad`. La compra lleva `eventID` = id de la sesión de Stripe para deduplicar.

Eventos del embudo (`src/lib/analytics.ts`):

| Evento | Cuándo | Meta | GA4 |
|---|---|---|---|
| `signup` | Primer inicio de sesión: `/auth/callback` redirige a `/panel?registro=1` | `CompleteRegistration` | `sign_up` |
| `piece_created` | El formulario aterriza en la nueva pieza (`/piezas/nueva` → `/piezas/[id]`) | `PieceCreated` (personalizado) | `piece_created` |
| `piece_approved` | Descarga con crédito correcta (`ResultActions`) | `PieceApproved` (personalizado) | `piece_approved` |
| `purchase` | Aviso «Pago recibido» de `/creditos?ok=1` con la sesión verificada | `Purchase` con importe y EUR | `purchase` con `transaction_id` |

Cada evento se envía una vez por navegador y clave (`localStorage`). La fuente de verdad del embudo son las tablas, no los píxeles: ver `docs/anuncios.md`.

## Estructura

- `src/app/` — rutas: `/` (landing), `/entrar` (enlace mágico), `/auth/callback`, `/panel`, `/piezas/nueva`, `/piezas/[id]`, `/creditos`, `/admin/revision` (solo `profiles.is_admin`), `/api/stripe/webhook` y `/api/internal/notify`.
- `src/proxy.ts` — en Next.js 16 `middleware.ts` se llama `proxy.ts`. Refresca la sesión de Supabase en cada petición y guarda `utm_*` y `ref` en la cookie `sh_attr` (90 días, último clic).
- `src/lib/supabase/` — `createClient()` (navegador), `createServerClient()` (cookies; RSC, server actions y route handlers), `createAdminClient()` (service role, `server-only`).
- `src/lib/auth.ts` — `requireUser()` redirige a `/entrar` sin sesión y devuelve `{ user, profile }`.
- `src/lib/pricing.ts` — paquetes de créditos (`PACKS`) y `formatEur()` (espacio de no separación antes de «€»).
- `src/lib/format.ts` — `formatDimensions(ancho, alto, fondo)` → «50 × 48,5 × 50 cm» y `formatCm()`.
- `src/lib/attribution.ts` — lectura de UTM y de la cookie de atribución; al registrarse se envía como `data.attribution` y el trigger `handle_new_user` la copia a `profiles.attribution`.
- `src/lib/database.types.ts` — tipos generados de Supabase más un bloque de alias al final (`Profile`, `Piece`…); consérvalo al regenerar.
- `src/lib/pieces.ts` — etiquetas de estado (`PIECE_STATUS_LABEL`), lecturas de la pieza del cliente y URLs firmadas.
- `src/lib/notify.ts`, `src/lib/analytics.ts` — avisos por correo y eventos del embudo.
- `src/theme.ts` — tema de Chakra (paleta arena y arcilla; Fraunces para titulares, Inter para texto).
- `public/examples/` — fotos y GLB del piloto que enseña la landing. Los USDZ no se versionan: Quick Look en iOS genera el USDZ a partir del GLB.

## Decisiones y trampas

- **Registro de Emotion para SSR** (`src/components/ui/emotion-registry.tsx`, envuelve a `Provider` en el layout): recoge los estilos que Emotion genera al renderizar en el servidor y los inserta en `<head>` con `useServerInsertedHTML`. Sin él, Emotion dejaba `<style data-emotion>` dentro de `<body>`, el HTML del servidor no coincidía con el del cliente y React tiraba el árbol y lo volvía a pintar (error #418 en todas las páginas). Un e2e comprueba que `/`, `/entrar` y `/panel` hidratan sin errores.
- **Cache Components sigue desactivado** (`next.config.ts`). El error de hidratación que congelaba la página está resuelto por el registro, pero activarlo exige además quitar `export const dynamic` de los route handlers y poner cada lectura de cookies tras `Suspense`; no se ha probado a fondo para el MVP. Hay un test e2e («stays responsive after hydration») que lo vigila si se vuelve a activar.
- **Cabeceras:** todas las páginas salen con `X-Frame-Options: DENY` y `Content-Security-Policy: frame-ancestors 'none'` (`next.config.ts`): nadie puede meter la web en un iframe.
- **Lecturas por columna:** con la sesión del cliente, `pieces` y `piece_models` solo se pueden leer por las columnas del cliente (ver `supabase/README.md`); un `select("*")` falla. Usa las listas de `src/lib/pieces.ts`.
- `model-viewer` se carga con `import()` solo cuando la tarjeta del ejemplo se acerca a la pantalla, y usa `ar-scale="fixed"` para que la realidad aumentada respete el tamaño real.
- **Enlace mágico:** las plantillas del repo (`supabase/templates/confirmation.html` para el alta, `type=signup`, y `supabase/templates/magic_link.html` para los siguientes inicios de sesión; en `supabase/config.toml`) mandan un `token_hash`; la de enlace mágico es `{{ .SiteURL }}/auth/callback?token_hash=…&type=magiclink`, que `/auth/callback` verifica con `verifyOtp` y funciona en cualquier navegador. **No están aplicadas todavía (ninguna de las dos):** Supabase no deja cambiar plantillas
 en el plan gratuito con su SMTP por defecto (`supabase config push` responde 400). Hasta configurar SMTP propio, el correo usa la plantilla por defecto con PKCE (`?code=`, mismo navegador), que el callback también acepta. Ver `supabase/README.md`.

## El worker en el Mac

El worker (Python, en la raíz del repo) reclama las piezas en cola, genera el modelo con el harness y Blender, y las deja en `review`:

```bash
# en la raíz del repo; .env con SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY y BLENDER_BIN
uv run platform-worker run                     # bucle; Ctrl+C para parar (o: just worker)
uv run platform-worker run --once              # una pieza y termina
uv run platform-worker piece <id>              # reintento manual de una pieza
```

- `PROVIDER` vacío: solo se generan piezas rectilíneas (ruta E paramétrica); las orgánicas quedan como fallidas con el motivo. Para orgánicas, `PROVIDER=tripo` (con `TRIPO_API_KEY`) o `PROVIDER=fal` (con `FAL_KEY`). `fake` es solo para pruebas.
- Aviso al admin: `NOTIFY_URL=https://<dominio>/api/internal/notify` y `WORKER_SHARED_SECRET` (el mismo de Vercel) en el `.env` de la raíz.
- **Un solo worker.** La cola aguantaría dos (`FOR UPDATE SKIP LOCKED`), pero el presupuesto diario y la limpieza de huérfanas suponen un único proceso.
- Mientras el Mac esté apagado, las piezas esperan en `queued`. El worker renueva `claimed_at` antes de cada llamada al proveedor y de cada entrega; al arrancar (y cada 10 vueltas) devuelve a la cola las piezas en `generating` sin latido desde hace más de 90 min.
- **Presupuesto diario del proveedor:** `WORKER_DAILY_BUDGET_USD` (20 por defecto). Antes de cada llamada al proveedor suma lo gastado hoy (hora de Madrid: `cost_usd` de los modelos de hoy más `pieces.provider_cost_usd`, el coste de los intentos fallidos); si se pasa, la pieza orgánica vuelve a `queued` con «Presupuesto diario agotado; se reintenta mañana» y `not_before` = medianoche de Madrid, y el admin recibe un aviso al día. Las rectilíneas (ruta E) no gastan y siguen.
- Piezas excluidas (lámparas, metal, cromo, vidrio): `rejected` con el motivo en `reject_reason`, sin coste.
- Fotos: el worker usa solo las 4 primeras por `position` y rechaza (pieza `failed`) cualquier ruta que no esté directamente bajo `{user_id}/{piece_id}/`.
- Para dejarlo corriendo: una ventana de terminal con `just worker`, o un `launchd` (pendiente; no incluido).

## Stripe: de pruebas a producción

En pruebas (sandbox):

1. Pega `STRIPE_SECRET_KEY=sk_test_…` en `.env.local` y ejecuta `pnpm stripe:setup` (crea «Piezas 3D» y los precios `pieza_1` 9 €, `pieza_10` 69 €, `pieza_30` 169 €, IVA incluido).
2. `stripe listen --forward-to localhost:3000/api/stripe/webhook` y pega el `whsec_…` que imprime como `STRIPE_WEBHOOK_SECRET`; reinicia `pnpm dev`.
3. `/creditos` → «Comprar» → tarjeta `4242 4242 4242 4242` → vuelves a `/creditos?ok=1…` con el saldo sumado y una fila «Compra».

Para producción:

1. Activa la cuenta de Stripe (datos fiscales y bancarios) y, si toca, Stripe Tax o el IVA en los precios (los precios ya son `tax_behavior: inclusive`).
2. Con la clave **live** (`sk_live_…`) en local, una vez: `STRIPE_SECRET_KEY=sk_live_… pnpm stripe:setup` (avisa de que es PRODUCCIÓN).
3. Dashboard → Developers → Webhooks → endpoint `https://<dominio>/api/stripe/webhook` con los eventos `checkout.session.completed`, `checkout.session.async_payment_succeeded` y `charge.refunded`; copia su `whsec_…`.
4. En Vercel (Production): `STRIPE_SECRET_KEY=sk_live_…` y `STRIPE_WEBHOOK_SECRET=whsec_…`; redeploy.
5. Compra real de 9 € con tu tarjeta y comprueba saldo, fila en `purchases` y el pago en Stripe.

## Despliegue (no desplegar sin autorización de Jorge)

1. **Vercel:** nuevo proyecto desde el repo con *Root Directory* `platform/`, framework Next.js, `pnpm install` / `pnpm build` (por defecto). Región de funciones cercana a Supabase (`dub1`, Dublín, junto a eu-west-1).
2. **Variables** (Production y Preview): todas las de la tabla de claves. `NEXT_PUBLIC_SITE_URL=https://<dominio>` sin barra final. `SUPABASE_SERVICE_ROLE_KEY`, `STRIPE_*`, `RESEND_API_KEY` y `WORKER_SHARED_SECRET` nunca con prefijo `NEXT_PUBLIC_`.
3. **Supabase Auth (URLs):** `supabase/config.toml` solo tiene `localhost`. Añade el dominio y súbelo:
   ```toml
   [auth]
   site_url = "https://<dominio>"
   additional_redirect_urls = ["https://<dominio>/auth/callback", "http://localhost:3000/auth/callback", "http://localhost:3000/**"]
   ```
   y `supabase config push` desde la raíz (proyecto enlazado `oyntcaxzskzntiyzxquy`). También se puede hacer en Dashboard → Authentication → URL Configuration. Sin esto, los enlaces mágicos de producción acaban en `localhost`.
4. **Correo de Auth:** el SMTP por defecto de Supabase envía muy pocos correos por hora; antes de anuncios configura SMTP propio (p. ej. Resend → Supabase → Authentication → SMTP) con el mismo dominio verificado, y revisa la plantilla del enlace mágico en español.
5. **Resend:** verifica el dominio (DNS SPF/DKIM), crea la clave y define `RESEND_API_KEY`, `NOTIFY_FROM_EMAIL` y `ADMIN_NOTIFY_EMAIL`.
6. **Worker:** en el `.env` de la raíz del Mac, `NOTIFY_URL=https://<dominio>/api/internal/notify` y el mismo `WORKER_SHARED_SECRET`; `just worker`.
7. **Stripe live:** ver la sección anterior.
8. **Admin:** `update profiles set is_admin = true where email = '<tu correo>';` en el SQL editor.

### Lista de comprobación antes de anuncios

- [ ] `NEXT_PUBLIC_SITE_URL` y Redirect URLs de Supabase con el dominio de producción (`supabase config push`).
- [ ] SMTP propio en Supabase Auth y plantilla del enlace mágico en español.
- [ ] Stripe en live: precios creados con `pnpm stripe:setup`, webhook con los tres eventos, compra real de prueba hecha.

- [ ] Resend con dominio verificado; recibes «Pieza en revisión» y el cliente «Tu pieza está lista».
- [ ] `NEXT_PUBLIC_META_PIXEL_ID` y/o `NEXT_PUBLIC_GA_ID`; eventos comprobados con Meta Pixel Helper / GA DebugView tras pulsar «Aceptar»; «Automatic Advanced Matching» desactivado en Meta.
- [ ] `NEXT_PUBLIC_CONTACT_EMAIL` y el titular (nombre y NIF) en `/privacidad` (`src/app/privacidad/page.tsx`, TODO).
- [ ] **Fotos de la landing:** `public/examples/` usa fotos de catálogos de terceros del piloto. Sustitúyelas por fotos propias o con permiso escrito.
- [ ] Aviso legal (titular, NIF, domicilio) y condiciones de venta; `/privacidad` ya existe en lenguaje llano, conviene que lo revise un abogado.
- [ ] Worker corriendo en el Mac con `PROVIDER` decidido (sin proveedor, las piezas orgánicas fallan).
- [ ] Un recorrido completo en producción desde el móvil: registro, pieza, revisión, visor con RA, compra y descarga.

### Cobros: factura, desistimiento, devoluciones y disputas

- Checkout crea **factura** (`invoice_creation`), pide **NIF/CIF** opcional (`tax_id_collection`) y la dirección de facturación. Antes de «Comprar», `/creditos` exige marcar «Acepto que el contenido digital se entrega de inmediato y renuncio al derecho de desistimiento.» (comprobado también en el servidor; queda en `metadata.withdrawal_waiver` de la sesión).
- **Devoluciones:** el evento `charge.refunded` con la devolución **completa** de un cobro que conocemos (`purchases.stripe_payment_intent`) resta los créditos del paquete con una fila `refund` negativa, una sola vez por evento (`credit_ledger.stripe_event_id` único). El saldo puede quedar negativo si ya se gastaron. Las devoluciones **parciales** solo se anotan en el log: ajusta los créditos a mano (fila `refund` desde el SQL editor).
- **Disputas** (`charge.dispute.*`): manuales. Responde en el Dashboard de Stripe y, si la pierdes, resta los créditos a mano.
