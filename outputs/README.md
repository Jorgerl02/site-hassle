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

## Tercera ronda: generación real vía Higgsfield MCP (sin claves de proveedor)

Higgsfield expone por MCP modelos 3D de Tripo (H3.1), Meshy 7 y Hunyuan3D v3. Se generaron 7 modelos de 4 piezas con los créditos del plan (118 → 43; 9 créditos por Tripo H3.1, 15 por Hunyuan), se importaron con `python -m harness.data.import_glb`, y pasaron por el postprocesado, los renders y el informe del harness. El juez VLM no se ejecutó (sin clave de Anthropic); las puntuaciones las puso Claude desde esta sesión viendo los renders y la foto, sin ciego.

| Archivo | Qué es |
|---|---|
| `23_mcp_higgsfield_post.txt` | `post.ok`, errores de escala, triángulos antes y después del postprocesado por candidato |
| `24_report_mcp-higgsfield.md` | Informe generado por el harness (todo "sin puntuar" por falta de juez; geometría sí calculada) |
| `25_juez_claude_p04.csv` | Puntuaciones de Claude como juez para las 7 generaciones (todas no aptas) |
| `26_mcp_higgsfield_geometria.txt` | Tabla de errores de escala por eje, estanqueidad, componentes y caras |
| `renders/mcp/*.png` | Renders de cada generación (frontal y tres cuartos) |
| `glb/*.glb` | Los GLB originales descargados (no versionados en git) |

Resultado resumido:

| Pieza | Modelo | Error máx. de escala | Veredicto |
|---|---|---|---|
| p04 mesa teca | Tripo H3.1 cruda / limpia | 9,1 % / 8,5 % | Patas inventadas, no apta |
| p04 mesa teca | Hunyuan3D v3 | 3,1 % | Mejor geometría, tablero sin textura, no apta |
| p09 butaca bouclé | Tripo H3.1 | 5,2 % | Forma bien, tejido convertido en cuero, no apta |
| p09 butaca bouclé | Hunyuan3D v3 | 5,8 % | Forma bien, material liso, no apta |
| p17 lámpara cromada | Tripo H3.1 | 31,5 % | Cromo perdido, arco desproporcionado, no apta |
| p24 perchero tubo | Tripo H3.1 | 19,5 % | Muy fiel en forma, base más profunda, no apta |

Lo que el harness detectó en esta ronda y se corrigió: cargar los GLB con materiales en trimesh consumía 22 GB y mataba `eval`; ahora se cargan sin materiales (0,2 GB).

### Ampliación: 7 modelos más, incluidos 4 de Magnific

Higgsfield (39 créditos más, quedan 4): p07 Hunyuan, p13 Hunyuan y Tripo. Magnific (3.600 créditos de 45.540 del plan Plus): Hunyuan 3.1 Pro con PBR y TRELLIS-2 sobre p04 y p09. Magnific también ofrece Hi3D v3 (4.280 créditos) y Tripo H3.1 (580). Total: 14 generaciones de 6 piezas.

| Pieza | Modelo | Error máx. | Lectura |
|---|---|---|---|
| p04 mesa teca | Hunyuan 3.1 Pro (Magnific) | 2,2 % | Mejores proporciones de p04, patas aún inventadas |
| p04 mesa teca | TRELLIS-2 (Magnific) | 6,8 % | La veta más fiel, patas inventadas |
| p09 butaca | TRELLIS-2 (Magnific) | 0,5 % | Escala casi exacta; textura con motas, cuero en vez de bouclé |
| p09 butaca | Hunyuan 3.1 Pro (Magnific) | 6,5 % | Como el Hunyuan de Higgsfield |
| p07 mesa travertino | Hunyuan v3 (Higgsfield) | 17,9 % | Estructura correcta pero casi cúbica |
| p13 sofá cama | Hunyuan v3 / Tripo (Higgsfield) | 9,1 % / 5,7 % | Los más cercanos a apto; gris en vez de beige |

Veredicto acumulado: 0 de 14 aptos con el umbral de la spec. Lo que más se repite no es la geometría sino dos cosas: la escala se queda entre el 5 y el 9 % en tapizados y el color o material se pierde. Parte de la pérdida de color es del propio harness: los renders de Workbench salen oscuros y desaturados, lo que penaliza "materiales" a todas las variantes por igual. Conviene arreglar la iluminación de `bpy_render.py` antes de la siguiente ronda de puntuación.

## Cuarta ronda: 16 piezas de macizo y tapizado con TRELLIS-2 y Hunyuan 3.1 Pro (Magnific)

Se completaron las dos categorías con opciones: 8 piezas de macizo y 8 de tapizado, cada una con TRELLIS-2 (730 créditos) y Hunyuan 3.1 Pro con PBR (1.070). 24 generaciones nuevas, 22.670 créditos de Magnific. Antes de puntuar se corrigió la iluminación de los renders (luz de estudio, exposición +0,15): la luminancia del objeto queda a ±5 % de la foto. Las 38 generaciones se re-renderizaron y re-puntuaron.

| Archivo | Qué es |
|---|---|
| `contact/<pieza>.jpg` | Hoja de contacto por pieza: foto limpia + renders de cada variante en tres cuartos y frontal, con el error de escala |
| `25_juez_claude_p04.csv` | Las 38 puntuaciones del juez (Claude, sin ciego) con la rúbrica de la spec |
| `26_mcp_higgsfield_geometria.txt` | Errores de escala por eje de las 38, y cuántas quedan bajo el 3 % por variante |
| `24_report_mcp-higgsfield.md` | Informe del harness |

Resultado: **2 aptos de 38**, los dos con TRELLIS-2: el jarrón de gres p05 y el sillón Matilda p15.

| Variante | Piezas | Escala < 3 % | Aptos |
|---|---|---|---|
| TRELLIS-2 (Magnific) | 14 | 3 | 2 |
| Hunyuan 3.1 Pro (Magnific) | 14 | 3 | 0 |
| Hunyuan v3 (Higgsfield) | 4 | 0 | 0 |
| Tripo H3.1 (Higgsfield) | 6 | 0 | 0 |

Por categoría, contando el mejor candidato por pieza: macizo 1 de 8 aptas, tapizado 1 de 8. El umbral de la spec era 60 %.

Qué falla, por orden:
1. **Escala**: solo 6 de 28 candidatos de Magnific quedan bajo el 3 %; la mayoría está entre el 3 y el 9 %, justo fuera. Con un umbral del 5 % habría 13 de 28.
2. **Piezas finas**: los dos cabeceros (3 y 6 cm de fondo) salen con 20 cm o se convierten en sofás. Es un fallo de categoría, no de modelo.
3. **Materiales**: TRELLIS-2 reproduce bouclé, listones y gres; Hunyuan tiende a cuero liso. Con la luz corregida el color ya no es el problema.
4. **Geometría inventada** en patas (p04) y bases (p06, p16).

## Quinta ronda: pipeline optimizado sobre 5 piezas

Tres palancas aplicadas a p01, p02, p08, p10 y p14, las que en la ronda 4 se quedaron entre el 3 y el 8 % de error: (1) ajuste a la caja del catálogo por eje con guardia del 10 % (`--fit-box`, nuevo en el harness), (2) dos candidatos de TRELLIS-2 por pieza (7.300 créditos), (3) variante E paramétrica sobre los dos cabeceros finos p11 y p12 (coste cero). Los dos candidatos de TRELLIS-2 son distintos entre sí, así que la selección del mejor funciona.

| Archivo | Qué es |
|---|---|
| `27_ronda5_geometria.txt` | Error antes y después del ajuste por candidato; 9 de 10 ajustados, 1 rechazado por la guardia |
| `contact/r5_<pieza>.jpg` | Hoja de contacto por pieza: foto, candidato de la ronda 4 y los dos de la ronda 5 |
| `25_juez_claude_p04.csv` | 50 puntuaciones acumuladas |

| Pieza | Ronda 4 | Ronda 5 | Qué cambió |
|---|---|---|---|
| p01 mesa redonda | no (3,1 %) | **apta** | Ajuste a la caja |
| p02 jarrón arcilla | no (4,4 %) | **apta** | Ajuste a la caja |
| p08 mesita | no | no | Textura rota en ambos candidatos; escala ya no es el problema |
| p10 butaca verde | no | no | Sale gris; color y tejido, no escala |
| p14 butaca bouclé | no (7,8 %) | **apta** | Ajuste a la caja |
| p11 cabecero 3 cm | no | **apta** | Variante E |
| p12 cabecero 6 cm | no | **apta** | Variante E |

Acumulado del piloto de 16 piezas, mejor candidato por pieza: **macizo 3 de 8, tapizado 4 de 8, 44 % en total** frente al 12 % de la ronda 4 y al 60 % del umbral. Las que siguen fallando lo hacen por material o textura (p08, p10, p09, p13, p15 con Hunyuan) o por geometría inventada (p04, p06, p16, p03), no por escala.

## Sexta ronda: ¿todo desde Blender? Arquetipo de paneles sobre 4 piezas rectilíneas

Nuevo arquetipo `panel_table` en la variante E (paneles laterales o pares en L, balda opcional) y un archivo `data/parametric_overrides.json` para forzar arquetipo y parámetros por pieza. E corrió sobre p03, p04, p07 y p08 a coste cero. Hoja de contacto: `contact/E_paneles.jpg`; renders en `renders/E_<pieza>_three_quarter.png`.

| Pieza | Arquetipo | Veredicto | Por qué |
|---|---|---|---|
| p07 mesa de travertino | paneles + balda | **apta** | Geometría exacta y la piedra real proyectada |
| p08 mesita | caja | no | Convincente de frente; falta el zócalo y el tablero muestra un artefacto |
| p03 zapatero | caja | no | Convincente de frente; sin patas y los laterales repiten el frontal |
| p04 mesa de teca | pares de paneles en L | no | Los tablones inclinados del original no se reproducen con cajas |

Acumulado del piloto de 16 piezas, mejor candidato por pieza: **macizo 4 de 8, tapizado 4 de 8, 50 %**. Lectura: Blender paramétrico resuelve lo que es realmente una composición de cajas (cabeceros, mesa de paneles) y se queda en "parecido pero no igual" en cuanto hay patas torneadas, zócalos, tablones inclinados o detalles. Para subir más haría falta arquetipos con patas y zócalo, y un extractor de parámetros desde la foto.

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
