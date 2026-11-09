# Prueba con anuncios: qué medir y cómo

Objetivo de la prueba: saber cuánto cuesta llevar a una persona de un anuncio a **ver su pieza en 3D** y a **pagar**, antes de invertir más. La fuente de verdad son las tablas de Supabase (`profiles.attribution`, `pieces`, `credit_ledger`, `purchases`); los píxeles de Meta y GA solo sirven para que las plataformas optimicen la entrega y para cruzar datos.

## Las cuatro métricas

| Métrica | Cálculo | De dónde sale |
|---|---|---|
| Coste por registro | gasto ÷ registros | `profiles` creados en el periodo, por `attribution->>'utm_campaign'` |
| Coste por pieza creada | gasto ÷ personas con ≥ 1 pieza | `pieces` (cualquier estado) de esos usuarios |
| Coste por pieza aprobada | gasto ÷ piezas descargadas | `credit_ledger` con `reason = 'consume'` (una fila por pieza descargada; `pieces.status = 'approved'`) |
| Coste por compra | gasto ÷ compras | `purchases` con `status = 'paid'`; ingresos = `sum(amount_cents) / 100` |

Además, para leer el embudo:

- **Registro → pieza creada** (¿se entiende qué subir?).
- **Pieza creada → pieza mostrada** (`ready`, `approved` o `rejected` tras revisión): mide el worker y la revisión, no el anuncio. Las `needs_photos` y `failed` indican fotos o categorías que el anuncio está atrayendo mal.
- **Pieza mostrada → compra** (¿el visor gratis convence?).
- **ROAS** = ingresos ÷ gasto. Con paquetes de 9 €, 69 € y 169 € (IVA incluido; sin IVA ≈ 7,44 €, 57,02 € y 139,67 €), mira también qué paquete se compra.

Umbrales orientativos para decidir (a revisar con los primeros datos): si el coste por compra supera el ingreso medio por compra durante 2 semanas con ≥ 300 € de gasto, parar o cambiar el ángulo del anuncio antes de subir presupuesto.

## Convención de UTM

Todas las URL de los anuncios llevan los cinco parámetros, en minúsculas, sin espacios ni tildes (guion para separar):

| Parámetro | Valores | Ejemplo |
|---|---|---|
| `utm_source` | `meta`, `google`, `tiktok`, `linkedin`, `newsletter` | `meta` |
| `utm_medium` | `paid-social`, `cpc`, `email`, `organic-social` | `paid-social` |
| `utm_campaign` | `{aaaa-mm}-{objetivo}-{publico}` | `2026-11-registro-tiendas-mueble` |
| `utm_content` | `{formato}-{angulo}-{v}` (identifica la creatividad) | `video-antes-despues-v2` |
| `utm_term` | palabra clave (solo búsqueda) o segmento | `modelo-3d-mueble` |

Ejemplo:

```
https://<dominio>/?utm_source=meta&utm_medium=paid-social&utm_campaign=2026-11-registro-tiendas-mueble&utm_content=video-antes-despues-v2
```

Para enlaces de personas (afiliados, menciones), `?ref=<nombre>`.

Cómo se guarda: el proxy de la web (`platform/src/proxy.ts`) escribe en la cookie `sh_attr` los `utm_*` y `ref` de la última visita que los trae (90 días, último clic). Al registrarse, la atribución viaja con el enlace mágico y el trigger `handle_new_user` la copia a `profiles.attribution` (solo esas seis claves, 200 caracteres como máximo cada una). No se actualiza después del registro: es la atribución del registro.

## Eventos de los píxeles

Con `NEXT_PUBLIC_META_PIXEL_ID` y/o `NEXT_PUBLIC_GA_ID` definidos (ver `platform/README.md`):

| Evento | Meta | GA4 | Optimizar campañas por |
|---|---|---|---|
| Registro | `CompleteRegistration` | `sign_up` | Al empezar (más volumen) |
| Pieza creada | `PieceCreated` (conversión personalizada) | `piece_created` | Cuando haya ≥ 50 por semana |
| Pieza aprobada (descarga) | `PieceApproved` (personalizada) | `piece_approved` | — |
| Compra | `Purchase` con importe en EUR | `purchase` | Cuando haya ≥ 50 por semana |

En Meta, crea las conversiones personalizadas `PieceCreated` y `PieceApproved` a partir de los eventos personalizados del píxel. Los píxeles pierden parte de las conversiones (bloqueadores, iOS, consentimiento): compara siempre con las consultas de abajo.

**Consentimiento:** en la UE, Meta Pixel y GA necesitan consentimiento previo para cookies no esenciales. La web aún no tiene banner de cookies; hay que añadirlo antes de activar los ids en producción.

## Consultas (Supabase → SQL editor)

Sustituye las fechas del periodo. Excluye las cuentas de prueba (`test_%`) y la tuya.

```sql
-- Embudo por campaña
with periodo as (
  select timestamptz '2026-11-16' as desde, timestamptz '2026-11-30' as hasta
),
usuarios as (
  select p.id, coalesce(p.attribution->>'utm_campaign', '(sin campaña)') as campana
  from profiles p, periodo
  where p.created_at >= periodo.desde and p.created_at < periodo.hasta
    and p.email not like 'test\_%' and not p.is_admin
)
select
  u.campana,
  count(*) as registros,
  count(*) filter (where pz.piezas > 0) as con_pieza,
  sum(pz.piezas) as piezas,
  sum(pz.mostradas) as piezas_mostradas,
  sum(ap.aprobadas) as piezas_aprobadas,
  sum(co.compras) as compras,
  sum(co.ingresos) as ingresos_eur
from usuarios u
cross join lateral (
  select count(*) as piezas,
         count(*) filter (where status in ('ready', 'approved', 'rejected')) as mostradas
  from pieces where user_id = u.id
) pz
cross join lateral (
  select count(*) as aprobadas from credit_ledger where user_id = u.id and reason = 'consume'
) ap
cross join lateral (
  select count(*) as compras, coalesce(sum(amount_cents), 0) / 100.0 as ingresos
  from purchases where user_id = u.id and status = 'paid'
) co
group by u.campana
order by registros desc;
```

```sql
-- Ingresos por paquete y campaña
select coalesce(p.attribution->>'utm_campaign', '(sin campaña)') as campana,
       pu.pack, count(*) as compras, sum(pu.amount_cents) / 100.0 as ingresos_eur
from purchases pu join profiles p on p.id = pu.user_id
where pu.status = 'paid' and p.email not like 'test\_%'
group by 1, 2 order by 1, 2;

-- Por qué fallan las piezas (fotos o categorías que trae el anuncio)
select status, left(error, 80) as motivo, count(*)
from pieces
where status in ('needs_photos', 'failed', 'rejected')
group by 1, 2 order by 3 desc;
```

Apunta cada semana, por campaña: gasto (de la plataforma), registros, personas con pieza, piezas mostradas, piezas aprobadas, compras, ingresos y los cuatro costes.
