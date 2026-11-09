# Plataforma de piezas 3D a escala real — diseño del MVP

Fecha: 2026-11-09. Autor de las decisiones: Claude (coordinador), con el alcance fijado por Jorge: *"la primera versión es una especie de plataforma para generar piezas en 3D con facilidad, olvídate de conectores"*, con pasarela de pagos (pago por uso con créditos, uso gratuito limitado y, más adelante, mensual), y lista para probar con anuncios.

## 1. Intención y porqué

Una web donde una tienda de muebles (o cualquiera con una foto de catálogo y las medidas) sube la foto, escribe ancho × alto × fondo y recibe un modelo 3D a escala real que puede ver, girar y colocar en su casa con RA desde el móvil, y descargar en GLB y USDZ. Ver el resultado con RA es gratis; se cobra por pieza descargada, con créditos.

Lo que la hace distinta de Tripo, Meshy o Rodin (ver `reports/Productos IA de función única.md`): escala real garantizada por las medidas del catálogo, una sola función sin ajustes técnicos, y **solo se paga la pieza que se descarga, después de verla**. Lo que la hace distinta de un freelancer o de Modelry (desde 60 $/modelo, días de espera): minutos en lugar de días y precio por debajo de 20 €.

Referencias de producto que copiamos (del informe): la página única con prueba visual inmediata y controles mínimos de Magnific; el antes/después y las galerías de ejemplos reales; precios con tres paquetes y anclaje; créditos que no caducan si se compran y gratis limitado por cantidad, no por calidad.

## 2. Objetivos, no objetivos y anti-objetivos

**Objetivos del MVP**
- Flujo completo sin intervención del desarrollador: registro → nueva pieza → generación → revisión interna → resultado en visor → descarga con crédito.
- Pago real con Stripe Checkout por paquetes de créditos y libro de créditos auditable.
- Cola de revisión interna (Jorge o Claude) antes de enseñar el resultado al cliente.
- Landing con ejemplos reales del piloto, precios y captura de UTM, desplegable en Vercel, para probar con anuncios.
- Todo en español. Diseño cuidado (tipografía y copy), rápido, SEO básico desde el día 1.

**No objetivos (fase 2, con gancho dejado)**
- Conectores: MCP, API pública, plugins de Shopify o WooCommerce.
- Plan mensual: el libro de créditos lo admite (`reason = 'plan'`), no se construye.
- Entrada por URL de producto (scraping).
- Inglés y otras monedas.
- Juez automático con VLM; TRELLIS-2 autoalojado.
- Equipos o varios usuarios por cuenta.

**Anti-objetivos (fracaso aunque funcione)**
- Enseñar al cliente un modelo con escala incorrecta o un fallo evidente: por eso existe la revisión interna.
- Cobrar una pieza que el cliente no ha visto antes en el visor.
- Gastar créditos de proveedor en fotos que el validador habría rechazado.
- Una UX con ajustes técnicos (triángulos, semillas, texturas): un dueño de tienda no debe decidir nada técnico.

## 3. Restricciones

- Reutilizar el harness existente (`src/harness`: validador, enrutado, E paramétrica, postprocesado con ajuste a caja, evaluación geométrica, renders, entrega GLB/USDZ, refinado) como motor del worker. No duplicar lógica.
- Stack frontend de Jorge: Next.js 16 App Router, React 19, TypeScript, Chakra UI v3, pnpm.
- Supabase (proyecto nuevo `site-hassle`, región `eu-west-1`, coste 0 €) para Auth (enlace mágico por correo), Postgres, Storage. Stripe Checkout (cuenta sandbox "Bloom Studio" ya en la CLI). Vercel para la web. Blender 5.2 LTS en la máquina del worker.
- El worker corre en el Mac de Jorge durante la prueba (`uv run platform-worker`); el diseño permite moverlo a un VPS Linux sin cambios.
- Claves de proveedor: Tripo API o fal.ai (TRELLIS / Hunyuan3D). Sin clave, el worker genera piezas rectilíneas con E y usa un proveedor `fake` en desarrollo; las orgánicas quedan en espera con un mensaje claro. **Decisión pendiente de Jorge:** qué proveedor y clave; el adaptador admite ambos.
- Sin despliegue ni publicación sin autorización explícita de Jorge (build sí, deploy a producción no).
- Piezas de metal, vidrio y patas finas: se rechazan en la entrada con el texto de `docs/promesa.md`.

## 4. El producto, pantalla a pantalla

1. **Landing** (`/`): titular, subtítulo, CTA "Prueba con una pieza gratis". Galería de 6–8 ejemplos reales del piloto (foto → render → visor), cada uno con sus medidas. Sección "Cómo funciona" (3 pasos). Precios (tres paquetes + primera pieza gratis + "solo pagas lo que apruebas"). FAQ corta (qué fotos valen, qué no hacemos: metal, vidrio, patas finas; formatos; RA). Captura `utm_*` y `ref` en una cookie para asociarlos al registro.
2. **Acceso** (`/entrar`): correo → enlace mágico de Supabase. Sin contraseña.
3. **Panel** (`/panel`): lista de piezas con estado y miniatura; saldo de créditos; botón "Nueva pieza".
4. **Nueva pieza** (`/piezas/nueva`): nombre, tipo (selector cerrado), medidas en cm (ancho, alto, fondo), de 1 a 4 fotos, pregunta "¿Es una pieza recta, como una caja, un panel o un cabecero?" (sí / no / no sé), notas opcionales. Validación en cliente (resolución mínima, número de fotos) y en el worker (requisitos completos, con el texto de `explain`). Al enviar: estado `queued`.
5. **Pieza** (`/piezas/[id]`): estado con pasos (En cola → Generando → Ajustando escala → Revisando → Lista). Cuando está lista: visor `model-viewer` con RA, medidas, y tres acciones: **Descargar** (consume 1 crédito; la previsualización y la RA son gratis), **Pedir otra versión** (vuelve a la cola, máximo 2 veces, sin coste para el cliente), **No me sirve** (motivo; sin coste). Tras aprobar: descargas GLB y USDZ y enlace público del visor.
6. **Créditos** (`/creditos`): saldo, movimientos, tres paquetes → Stripe Checkout → vuelta con confirmación.
7. **Revisión interna** (`/admin/revision`, solo `is_admin`): cola de piezas en `review` con hoja de contacto (renders de cuatro vistas + foto), error de escala, proveedor, intento; acciones: **Mostrar al cliente** (`ready`), **Regenerar** (`queued`, con nota), **Rechazar** (`rejected`, con motivo que verá el cliente).

Estados de una pieza: `queued → generating → review → ready → approved` (approved = descargada con crédito), con salidas `needs_photos` (validador), `rejected` (interno o cliente), `failed` (error técnico, reintentable). `attempt` cuenta generaciones; el cliente puede pedir hasta 2 versiones más.

## 5. Arquitectura

```
platform/ (Next.js 16, Chakra v3)  ──Supabase JS──▶  Supabase (Auth, Postgres, Storage)
        │  server actions / route handlers                     ▲
        │  Stripe Checkout + webhook                           │ REST con service role
        ▼                                                      │
     Stripe                                   src/platform_worker/ (Python, reutiliza src/harness)
                                              bucle: claim_next_piece() → pipeline → sube resultados
```

- **Web (`platform/`)**: App Router; componentes de servidor para lectura; server actions para crear pieza, aprobar, rechazar, pedir versión; route handler para el webhook de Stripe. Cliente de Supabase con cookies (`@supabase/ssr`). Chakra v3 con tema propio (tipografía y colores definidos en una tarea de diseño). `model-viewer` 4.4.0 por `<script type="module">`.
- **Datos (Supabase)**: tablas `profiles`, `pieces`, `piece_photos`, `piece_models`, `credit_ledger`, `purchases`; función SQL `claim_next_piece()` (atómica, `FOR UPDATE SKIP LOCKED`), función `credit_balance(user_id)`; RLS: cada usuario ve lo suyo; el worker y el admin usan la clave de servicio desde servidor. Buckets: `photos` (privado), `models` (público para RA y visor), `renders` (privado, firmado para admin y cliente).
- **Worker (`src/platform_worker/`)**: `run(once=False)`; por pieza: descarga fotos → `validate_input`/`explain` → `rule_classify` → genera (E local; orgánica por `ProviderAdapter`: `fake` | `tripo` | `fal`) con 2 candidatos en orgánicas → `postprocess(fit_box=True)` → geometría + renders de 4 vistas + hoja de contacto → `deliver` (GLB web, USDZ, meta) → sube a Storage → `piece_models` + `pieces.status = review`. Errores: `failed` con mensaje; reintento manual desde admin. Un solo proceso, secuencial.
- **Pagos**: Stripe Checkout en modo pago único por paquete; webhook `checkout.session.completed` → `purchases` + `credit_ledger (+n, purchase)`; idempotente por `stripe_session_id`. Descargar una pieza: transacción que comprueba saldo y escribe `credit_ledger (−1, consume)`; después las descargas son URLs firmadas.
- **Correo**: los de acceso los envía Supabase. Aviso de "tu pieza está lista" por Resend si existe `RESEND_API_KEY`; si no, solo en la web. Gancho, no bloqueo.
- **Analítica de anuncios**: `utm_source/medium/campaign/content` y `ref` guardados en `profiles.attribution` al registrarse; `NEXT_PUBLIC_META_PIXEL_ID` y `NEXT_PUBLIC_GA_ID` opcionales; eventos `signup`, `piece_created`, `piece_approved`, `purchase`.

## 6. Precios y créditos (decisión del coordinador, tomada del informe `reports/Productos IA de función única.md`)

- **Gratis: ver el resultado completo, pagar solo por el archivo.** Cualquier cuenta puede crear hasta 3 piezas al día y ver cada resultado en el visor con medidas y RA, en calidad de previsualización (`model_preview.glb`: texturas a 512 px y ≤ 15.000 triángulos, público). El archivo bueno (`model_web.glb` a 2K + `model.usdz`) solo se descarga con 1 crédito. Es el «pago por resultado» de Rodin aplicado a mobiliario y la puerta gratuita de Photoroom/remove.bg (ves todo, te llevas poco).
- 1 crédito = 1 pieza descargada (GLB 2K + USDZ a escala). Las versiones nuevas (máximo 2 por pieza) y los fallos no consumen crédito. Sin reembolsos: el coste de GPU ya está gastado (regla de Magnific e Interior AI).
- Paquetes (IVA incluido): **1 pieza 9 €**, **10 piezas 69 €** (6,90 €/pieza, «Más elegido»), **30 piezas 169 €** (5,63 €/pieza). Los créditos comprados no caducan.
- Gancho para mensual (fase 2, solo si ≥ 20 % de compradores repiten en 90 días): `credit_ledger.reason = 'plan'` y `profiles.plan` nulo.
- Economía unitaria (estimación): coste de proveedor 0,10–1 € por pieza orgánica, 0 € en rectilíneas; margen > 60 % en la pieza suelta.

## 7. Lo que queda al constructor

- Tema visual (paleta, tipografía) dentro de Chakra v3; copy final de landing y correos, en español, revisado por el coordinador.
- Estructura exacta de componentes y rutas, siempre que respete las pantallas del punto 4.
- Mapeo de los `kind` de pieza del formulario a los del harness (`parametric_spec.KINDS`) y a la categoría de `docs/promesa.md`.
- Formato de la hoja de contacto del admin (puede reutilizar `outputs/contact`).

## 8. Criterio de "MVP funcional, listo para anuncios"

- `pnpm build` verde, `uv run pytest` verde, lint limpio.
- Prueba de extremo a extremo con Playwright sobre Supabase local (`supabase start`) y proveedor `fake`: registro, pieza rectilínea (E real con Blender), revisión, visor gratis, descarga bloqueada sin saldo, compra de un paquete en Stripe test, descarga con crédito.
- Un recorrido manual con una pieza real del piloto (p07 travertino o p15 Matilda) hasta el visor en el móvil de Jorge.
- Landing con Lighthouse ≥ 90 en rendimiento y SEO en móvil.
- Documento `platform/README.md` con despliegue (Vercel + Supabase + worker en el Mac) y lista de claves necesarias.
