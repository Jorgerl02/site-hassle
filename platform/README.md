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
| `pnpm test:e2e` | Tests de extremo a extremo (Playwright, `tests/e2e`); hace build y arranca en el puerto 3100 |

Lighthouse móvil de la landing (con `pnpm start` corriendo):

```bash
pnpm dlx lighthouse http://localhost:3000 --form-factor=mobile --screenEmulation.mobile \
  --only-categories=performance,seo --output=json --output-path=/tmp/lh.json --chrome-flags="--headless"
```

## Claves (`.env.local`)

| Variable | Dónde se usa |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Clientes de Supabase (navegador, servidor y proxy) |
| `SUPABASE_SERVICE_ROLE_KEY` | `createAdminClient()`, solo servidor; salta RLS |
| `NEXT_PUBLIC_SITE_URL` | Origen público: enlaces mágicos, `metadataBase`, sitemap. En Vercel, la URL de producción |
| `STRIPE_*`, `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Pagos (Tarea 5) |
| `RESEND_API_KEY`, `NEXT_PUBLIC_META_PIXEL_ID`, `NEXT_PUBLIC_GA_ID` | Opcionales |

## Estructura

- `src/app/` — rutas: `/` (landing), `/entrar` (enlace mágico), `/auth/callback`, `/panel`. Las tareas siguientes añaden `/piezas`, `/creditos` y `/admin`.
- `src/proxy.ts` — en Next.js 16 `middleware.ts` se llama `proxy.ts`. Refresca la sesión de Supabase en cada petición y guarda `utm_*` y `ref` en la cookie `sh_attr` (90 días, último clic).
- `src/lib/supabase/` — `createClient()` (navegador), `createServerClient()` (cookies; RSC, server actions y route handlers), `createAdminClient()` (service role, `server-only`).
- `src/lib/auth.ts` — `requireUser()` redirige a `/entrar` sin sesión y devuelve `{ user, profile }`.
- `src/lib/pricing.ts` — paquetes de créditos (`PACKS`) y `formatEur()`.
- `src/lib/attribution.ts` — lectura de UTM y de la cookie de atribución; al registrarse se envía como `data.attribution` y el trigger `handle_new_user` la copia a `profiles.attribution`.
- `src/lib/database.types.ts` — stub escrito a mano; la Tarea 4 lo sustituye por los tipos generados.
- `src/theme.ts` — tema de Chakra (paleta arena y arcilla; Fraunces para titulares, Inter para texto).
- `public/examples/` — fotos y modelos del piloto que enseña la landing.

## Decisiones y trampas

- **Cache Components está desactivado** (`next.config.ts`). Con él activo, la hidratación de los estilos de Chakra/Emotion dentro del shell prerenderizado provocaba un error de hidratación que congelaba la página unos segundos después de cargar (Next 16.4.5, React 19.3, Chakra 3.38). Hay un test e2e («stays responsive after hydration») que lo vigila si se vuelve a activar.
- `model-viewer` se carga con `import()` solo cuando la tarjeta del ejemplo se acerca a la pantalla, y usa `ar-scale="fixed"` para que la realidad aumentada respete el tamaño real.
- El enlace mágico usa PKCE: hay que abrirlo en el mismo navegador donde se pidió. `/auth/callback` acepta también `token_hash` + `type` por si se cambia la plantilla del correo.
- En Supabase → Authentication → URL Configuration hay que añadir `http://localhost:3000/auth/callback` y la URL de producción a las Redirect URLs.

## Despliegue (no desplegar sin autorización de Jorge)

Vercel con la raíz del proyecto en `platform/`, las variables de la tabla anterior y `NEXT_PUBLIC_SITE_URL` con el dominio final. Supabase alojado (`oyntcaxzskzntiyzxquy`). El worker corre en el Mac de Jorge (`uv run platform-worker`).
