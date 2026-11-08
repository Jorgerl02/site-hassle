# Salidas de la prueba del harness · 2026-11-08

Ejecutado en esta máquina sin claves de API ni Blender. Todo lo que depende de Tripo, Meshy, Gemini, Anthropic o Blender queda registrado como fallo de infraestructura, que es el comportamiento esperado.

| Archivo | Qué es |
|---|---|
| `00_test_suite.log` | `uv run pytest -q`: 236 passed, 4 skipped (tests opt-in de Blender real) |
| `01_ingest.log` | Descarga de las 67 fotos de las 30 piezas: 67 descargadas, 0 fallos (22 MB en `data/images/`) |
| `02_prep_validate_clean.log` | `validate_input` sobre la primera foto de cada pieza y `clean_image` (rembg real, modelo BRIA 1 GB descargado) sobre 5 piezas |
| `clean/*.png` | Fotos limpias a 1024×1024: p01 mesa, p09 butaca, p17 lámpara cromada, p24 perchero de tubo fino, p10 butaca a partir de foto lifestyle con otros muebles |
| `03_cli_help.txt` | Ayuda de `bakeoff` y de `bakeoff run` |
| `04_run_fake.log` | `run --variants FAKE` sobre las 30 piezas: 30 ejecutados, 0 errores, 1 s |
| `05_preflight_sin_claves.log` | `run --variants A` sin `.env`: la comprobación previa aborta con exit 2 antes de cualquier llamada de pago |
| `06_run_E_sin_blender.log` | `run --variants E --skip-preflight` sobre 4 piezas: 3 orgánicas → `not_applicable`; 1 rectilínea → error `infra` (sin Blender); nada abortado |
| `07_run_resume.log` | Segunda invocación del mismo run: 30 reutilizados, 0 ejecutados |
| `08_eval_fake.log` | `eval --no-render`: 60 registros, geometría calculada con trimesh, juez omitido por falta de clave → `unscored` |
| `09_report_fake.log`, `10_report_prueba-offline.md` | Informe generado: tabla vacía de aptos (nada puntuado), 100 % mallas cerradas, denominador explicado, sin línea base A |
| `11_scores_resumen.txt` | Dos registros de `scores.jsonl`: errores de escala ≈ 0 en los tres ejes, `scale_factor` ≈ 1, `source: trimesh` |
| `12_blind_sheet_head.txt`, `13_blind_key_head.txt` | Hoja ciega (sin nombre de variante) y clave separada |
| `14_meta_candidato_p01.json` | `meta.json` de un candidato |
| `15_eval_E.log`, `16_report_prueba-e-sin-blender.md` | Informe de la variante E: "E: 1/4 piezas aplicables", 1 sin puntuar por infraestructura |

## Segunda ronda: con Blender 5.2.3 LTS instalado

| Archivo | Qué es |
|---|---|
| `17_tests_blender_real.log` | Tests opt-in con Blender real (`HARNESS_BLENDER_TEST_BIN`): 9 passed (postprocesado, paramétrico, render) |
| `18_run_fake_E_blender.log` | `run --variants FAKE,E` con postprocesado real sobre las 30 piezas: 60 pasos, 73 candidatos, **73/73 `post.ok`**, errores de escala ~1e-7, 3 min 12 s |
| `19_eval_blender.log` | `eval` con renders reales: 90 registros, 5 renders por candidato, juez omitido sin clave; E con 13 piezas aplicables y 17 "no aplicable" |
| `20_report_prueba-blender.md` | Informe del run con Blender |
| `21_E_clasificacion.txt` | Cómo clasificó E cada pieza rectilínea (mesa, estantería, caja) |
| `22_test_workbench_albedo.log` | Test de render con GLB texturizado real de E: el nodo activo es el de Base Color (1 passed) |
| `renders/*_E_*.png` (sin sufijo) | Renders de E ANTES del arreglo de textura: costuras diagonales y patas grises |
| `renders/*_after.png` | Renders de E DESPUÉS: proyección planar por cara, fondo de la foto rellenado con colores del objeto |
| `renders/*_FAKE_*.png` | Cajas grises de la variante FAKE a las medidas exactas |

Hallazgos de esta ronda:
- Los tres scripts `bpy_*` funcionan en Blender 5.2.3 sin cambios de API.
- La textura de E proyectaba el fondo blanco de la foto sobre las caras y la foto entera sobre el tablero; corregido con `planar_uv` por cara (6 quads por caja) y `fill_background`.
- Los renders salen más oscuros y desaturados que la foto (iluminación de `bpy_render.py`): el travertino de p07 se ve marrón. Pendiente, afecta por igual a todas las variantes pero puede bajar la nota de materiales.
- p07 (mesa auxiliar de mármol con paneles laterales) se clasifica como mesa con patas: la heurística de `parametric_spec` no distingue paneles de patas.

## Observaciones de la prueba

1. **`validate_input` rechaza 9 de 30 primeras fotos** por "objeto ≤ 10 % del área": lámparas, percheros, mesas auxiliares y piezas altas y finas (p01, p17, p20, p23, p24, p25, p29, p30). El umbral del 10 % de píxeles es demasiado estricto para producto fino; conviene bajarlo o medir por caja envolvente. Hoy las variantes no bloquean por esto, pero el validador de la etapa 1 del pipeline lo haría.
2. **Las 30 piezas tienen al menos 1.000 px** en el lado mayor; p11 y p29 son las menores (900×1200).
3. **La limpieza con rembg tarda ~7 s por foto** en CPU y aísla bien incluso con otros muebles en escena (p10).
4. **Geometría**: la variante FAKE produce cajas exactas a las medidas, y `eval` las mide con error < 1e-7 y `scale_factor` 1, lo que confirma la ruta escala-invariante.
5. **Lo que no se ha podido probar**: scripts `bpy_*` (postprocesado, paramétrico, renders), clientes Tripo/Meshy/Gemini/Anthropic, juez VLM, variantes A–D y F con tráfico real.

## Para una ejecución real

1. `brew install --cask blender` y `BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender` en `.env`.
2. Rellenar `TRIPO_API_KEY`, `MESHY_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` en `.env`.
3. `HARNESS_BLENDER_TEST_BIN=... uv run pytest tests/test_post.py tests/test_parametric.py tests/test_eval.py -q` para validar los scripts de Blender.
4. Una pieza primero: `uv run bakeoff run --variants A --pieces p04 --run-id humo`, luego `eval` y `report`, y revisar `post.ok` y el coste en `runs/humo/meta.json`.
