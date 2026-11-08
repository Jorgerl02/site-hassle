# Muestra fija de 30 piezas (`data/sample.csv`)

**Fecha de selección:** 2026-11-08 · **Estado:** congelada.

> **Las piezas no se cambian una vez empezada la generación.** La muestra se fijó antes de
> lanzar ninguna variante; sustituir, reordenar o reetiquetar piezas después invalida la
> comparación entre variantes. Si una ficha desaparece o una imagen deja de descargarse,
> se anota en el informe del run; la pieza no se reemplaza a mitad del bake-off.

## Criterios de selección

- **Origen:** fichas de producto reales de tiendas españolas de mueble y decoración con
  catálogo en PrestaShop: **Kenay Home** (kenayhome.com, 21 piezas) y **SKLUM**
  (sklum.com/es, 9 piezas). Ambas publican medidas estructuradas en la ficha y fotos de
  producto en alta resolución.
- **Medidas:** todas las cifras salen de la ficha citada en `source_url` (bloque
  «Dimensiones» en Kenay: Ancho/Fondo/Alto; bloque «Medidas» en SKLUM: Alto/Ancho/Profundo).
  `width_cm` = ancho, `depth_cm` = fondo/profundo, `height_cm` = alto. Las piezas sin las
  tres medidas se descartaron, con una excepción explícita: las piezas redondas cuya ficha
  da solo **diámetro** (p20, mesa Ø35 cm) usan el diámetro como ancho y fondo. Las medidas
  son las del producto, no las del embalaje. Kenay declara una tolerancia de ±2 cm y SKLUM de ±3 cm.
- **Imágenes:** 1–3 por pieza (66 en total), priorizando el *packshot* sobre fondo liso
  (fondo blanco uniforme en Kenay, estudio gris en SKLUM) frente a fotos de ambiente. Se
  usa el original de mayor resolución que sirve la tienda (Kenay ≈ 2000 × 2667 px, salvo
  algunas de 900 × 1200; SKLUM 1000 × 1500 px).
- **Variedad:** dentro de cada categoría se mezclan formas rectilíneas y orgánicas
  (`rectilinear`, a ojo), tamaños (de un jarrón de 20 cm a un sofá de 205 cm) y materiales.
- **Descripción:** una línea en español redactada a partir de la ficha.

## Recuento por categoría

| Categoría | Piezas | Rectilíneas | Orgánicas | Qué incluye |
|---|---|---|---|---|
| `macizo_mate` | 8 (p01–p08) | 4 | 4 | madera maciza, microcemento, gres y travertino mate |
| `tapizado` | 8 (p09–p16) | 3 | 5 | butacas, sillones, cabeceros y sofá cama |
| `metal_vidrio` | 7 (p17–p23) | 2 | 5 | lámpara cromada, mesas de cristal, acero inoxidable, estructura metálica |
| `patas_finas` | 7 (p24–p30) | 4 | 3 | percheros, sillas de patas finas, mesa auxiliar y taburete |

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
