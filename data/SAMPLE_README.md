# Muestra fija de 30 piezas (`data/sample.csv`)

**Fecha de selección:** 2026-11-08 · **Enmienda:** 2026-11-08 (revisión 2, antes de cualquier
generación) · **Estado:** congelada.

> **La muestra queda congelada a partir de esta revisión 2.**

> **Las piezas no se cambian una vez empezada la generación.** La muestra se fijó antes de
> lanzar ninguna variante; sustituir, reordenar o reetiquetar piezas después invalida la
> comparación entre variantes. Si una ficha desaparece o una imagen deja de descargarse,
> se anota en el informe del run; la pieza no se reemplaza a mitad del bake-off.

## Criterios de selección

- **Origen:** fichas reales de cuatro tiendas españolas de mueble y decoración, todas sobre
  plataformas de e-commerce estándar:

  | Tienda | Plataforma | Piezas |
  |---|---|---|
  | Kenay Home (kenayhome.com) | PrestaShop | 15 |
  | SKLUM (sklum.com/es) | PrestaShop | 9 |
  | Pilma (pilma.com, Barcelona) | WooCommerce | 3 |
  | Decoración Beltrán (decoracionbeltran.com) | PrestaShop | 3 |

  Ninguna categoría tiene más del 60 % de sus piezas de una misma tienda.
- **Medidas:** todas las cifras salen de la ficha citada en `source_url` (Kenay: bloque
  «Dimensiones» Ancho/Fondo/Alto; SKLUM: bloque «Medidas» Alto/Ancho/Profundo; Pilma: tabla
  «Medidas» Largo/Profundidad/Altura; Beltrán: texto «Ancho x Alto x Hondo» o «Diámetro/Altura»).
  `width_cm` = ancho/largo, `depth_cm` = fondo/profundo/hondo, `height_cm` = alto. Se
  descartaron las piezas sin las tres medidas, con una excepción explícita: en las piezas
  redondas cuya ficha da solo **diámetro** (p20, mesa Ø35 cm; p02, jarrón Ø35 cm), el diámetro
  hace de ancho y de fondo. Son medidas del producto, no del embalaje. Kenay declara una
  tolerancia de ±2 cm y SKLUM de ±3 cm.
- **Imágenes:** 1–3 por pieza, priorizando el *packshot* (fondo blanco uniforme en Kenay,
  estudio gris en SKLUM, PNG recortado en Pilma). A propósito, varias piezas nuevas incluyen
  **fotos de ambiente** para ejercitar `clean_image`: p10 (solo fotos de ambiente), p02, p04
  y p14 (packshot + ambiente). Se usa el original de mayor resolución que sirve la tienda
  (Kenay ≈ 2000 × 2667 px, algunas de 900 × 1200; SKLUM 1000 × 1500; Pilma 1900 × 2200;
  Beltrán 1200 × 1372).
- **Variedad:** dentro de cada categoría se mezclan formas rectilíneas y orgánicas
  (`rectilinear`, a ojo), tamaños (de un jarrón de 20 cm a un sofá de 205 cm) y materiales.
- **Descripción:** una línea en español redactada a partir de la ficha.

## Recuento por categoría

| Categoría | Piezas | Rectilíneas | Orgánicas | Tiendas | Qué incluye |
|---|---|---|---|---|---|
| `macizo_mate` | 8 (p01–p08) | 4 | 4 | Kenay 4 · Pilma 2 · Beltrán 1 · SKLUM 1 | madera maciza, microcemento, gres, arcilla y travertino mate |
| `tapizado` | 8 (p09–p16) | 3 | 5 | Kenay 4 · Beltrán 2 · SKLUM 2 | butacas, sillones, cabeceros y sofá cama |
| `metal_vidrio` | 7 (p17–p23) | 2 | 5 | Kenay 3 · SKLUM 3 · Pilma 1 | lámpara cromada, mesas de cristal, acero inoxidable, estructura metálica |
| `patas_finas` | 7 (p24–p30) | 4 | 3 | Kenay 4 · SKLUM 3 | percheros, sillas de patas finas, mesa auxiliar y taburete |

## Historial

- **Rev. 1 (2026-11-08):** 21 piezas de Kenay Home y 9 de SKLUM.
- **Rev. 2 (2026-11-08, antes de generar nada):** se sustituyeron 6 piezas de Kenay Home
  (p02, p04, p06, p10, p14, p18) por piezas de Pilma (WooCommerce) y Decoración Beltrán,
  para que ninguna tienda pase del 60 % en ninguna categoría y para incluir fotos de ambiente.
  Los ids se reutilizan. Desde esta revisión la muestra no cambia.

## Columnas

Las 11 columnas de `harness.core.models.CSV_COLUMNS` más `image_urls` al final (URLs de
origen separadas por `;`). `images` lista las rutas locales `data/images/<id>/<n>.jpg`,
que crea la ingesta:

```bash
uv run python -m harness.data.ingest      # descarga, salta lo existente, escribe data/images/ingest_report.json
```

## Uso de las imágenes

Las imágenes y fichas son propiedad de sus tiendas. Se descargan **solo para evaluación
interna** de las variantes del pipeline foto→3D. **No se republican** ni se usan en webs,
redes, material comercial o datasets públicos, y `data/images/` está fuera del repositorio
(`.gitignore`).
