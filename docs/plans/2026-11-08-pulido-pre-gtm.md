# Plan de implementación · Pulido previo al generador lean (6 puntos)

Spec: la lista de seis puntos acordada con Jorge el 8-nov-2026 (resumen abajo) sobre el harness existente (`src/harness`, rama `feat/harness-bakeoff`). Resultados del piloto que motivan cada punto: `outputs/README.md` y `outputs/25_juez_claude_p04.csv`.

Los seis puntos:
1. Cerrar la promesa: categorías cubiertas y excluidas, tolerancia de escala como decisión de producto.
2. Enrutado y refinado automáticos sin humano: F por reglas, arquetipo caja con patas y zócalo, bucle de refinado.
3. Entrega real en la ficha: GLB ligero (< 5 MB), USDZ, visor para probar en móvil.
4. Proveedor de generación por API, no por MCP.
5. Validador de entrada que no rechace piezas finas; requisitos de foto.
6. Juez ciego: consolidar hojas de jueces humanos en el informe (el juez VLM sigue dependiendo de una clave).

## Global Constraints

- Python 3.12 con `uv`; layout `src/harness/`; tests con `pytest`; `uv run pytest -q` verde (hoy 316 passed, 6 skipped); `ruff check` y `ruff format --check src tests` limpios. Blender 5.2.3 en `/Applications/Blender.app/Contents/MacOS/Blender` (`.env` tiene `BLENDER_BIN`; tests opt-in con `HARNESS_BLENDER_TEST_BIN`). Sin claves de API en la máquina: toda red se mockea en tests.
- **Disciplina de archivos en tareas paralelas (T1–T6)**: cada tarea toca solo sus archivos; `src/harness/cli.py`, `src/harness/core/registry.py`, `README.md` y `pyproject.toml` se editan solo en T7. Cada tarea ejecuta solo su fichero de tests. Sin commits por parte de los implementadores; sin subagentes; sin instalar dependencias (todas están declaradas).
- **Documentación antes de código**: `bpy` 5.x (exportador USD/USDZ, Decimate, imágenes), API de Meshy (retexture), `model-viewer` (atributos `ar`, `ios-src`): consultar Context7 o docs oficiales antes de escribir.
- Español en docs, mensajes de CLI y nombres de columnas visibles; código e identificadores en inglés.
- Decisiones del coordinador (no son del usuario): tolerancia por defecto 3 % y configurable; entrega web decimada a ≤ 60k triángulos, texturas ≤ 2048 px, Draco activado, objetivo < 5 MB; USDZ exportado por Blender; retexturizado detrás del cliente de Meshy (requiere clave) con la misma interfaz para otros proveedores; regla de "pieza fina": alguna dimensión < 8 cm o relación ancho/fondo o alto/fondo > 15.

## Tareas

### Task 1 · Validador por caja envolvente y requisitos de foto (paralela)

**Archivos**: `src/harness/prep/clean.py`, `src/harness/prep/requirements.py` (nuevo), `tests/test_prep_requirements.py` (nuevo).

**Pasos**: en `validate_input`, sustituir el criterio "objeto ≥ 10 % de los píxeles" por "caja envolvente del objeto ≥ 25 % del lado mayor en ambos ejes", conservando el mínimo de 1.000 px; mantener la firma `validate_input(path) -> list[str]`. Añadir `requirements.py` con `PHOTO_REQUIREMENTS: list[str]` (frontal o tres cuartos, fondo claro o uniforme, pieza completa sin recortes, ≥ 1.000 px, medidas en cm) y `explain(issues) -> str` en castellano para mostrar al usuario. Tests: silueta fina (perchero sintético: 4 % de píxeles, 70 % de caja) pasa; objeto diminuto (10 % de caja) falla; resolución baja falla; `explain` produce texto. No tocar `tests/test_core.py` (sus tests de `validate_input` deben seguir pasando: comprobar que el objeto pequeño usado allí sigue siendo rechazado por caja; si no, documentarlo en el informe para que T7 ajuste el test).

### Task 2 · Entrega web: GLB ligero, USDZ y visor (paralela)

**Archivos**: `src/harness/post/bpy_deliver.py` (nuevo, corre dentro de Blender), `src/harness/post/deliver.py` (nuevo), `src/harness/post/viewer_template.html` (nuevo), `tests/test_deliver.py` (nuevo), `tests/fixtures/deliver/*`.

**Pasos**: `bpy_deliver.py`: importa `model_post.glb`, decima a `--max-tris` (defecto 60.000), limita texturas a `--max-tex` (2048) y las recomprime a JPEG de calidad 85 cuando no tienen alfa, exporta `model_web.glb` con Draco (`export_draco_mesh_compression_enable=True`) y `model.usdz` con el exportador USD de Blender (`bpy.ops.wm.usd_export` con `.usdz`, materiales y texturas incluidos; verificar en docs 5.x), y escribe `deliver_meta.json` con tamaños en bytes, triángulos y texturas. `deliver.py`: `deliver(cand_dir: Path, piece: Piece, *, max_tris=60000, max_tex=2048, size_limit_bytes=5_000_000) -> DeliverResult` que lanza `bpy_deliver.py` vía `harness.core.blender.run_blender_script`, comprueba el tamaño (si `model_web.glb` supera el límite, reintenta una vez con la mitad de triángulos y texturas a 1024), y escribe `viewer.html` desde `viewer_template.html` con `<model-viewer src="model_web.glb" ios-src="model.usdz" ar ar-modes="webxr scene-viewer quick-look" camera-controls>` y el script de model-viewer desde unpkg con versión fijada. Tests: construcción de argumentos, parseo de `deliver_meta.json`, reintento cuando el tamaño excede (mock de `run_blender_script`), plantilla HTML con las rutas correctas; test opt-in con Blender real sobre `runs/mcp-higgsfield/p05/MG_TRELLIS2/cand_1/model_post.glb` si existe (tamaño < 5 MB, `model.usdz` presente).

### Task 3 · Enrutado por reglas y arquetipo caja con patas y zócalo (paralela)

**Archivos**: `src/harness/variants/f_router.py`, `src/harness/post/parametric_spec.py`, `src/harness/post/bpy_parametric.py` (solo si hace falta), `src/harness/variants/e_parametric.py`, `data/parametric_overrides.json`, `tests/test_router_rules.py` (nuevo), `tests/test_parametric.py` (ampliar).

**Pasos**: en `f_router.py`, añadir un clasificador por reglas `rule_classify(piece) -> RouteDecision(route, reason, thin)` usado cuando no hay VLM (sin `ANTHROPIC_API_KEY`) o cuando se pasa `classifier="rules"`: `thin` = alguna dimensión < 8 cm o relación ancho/fondo o alto/fondo > 15; rutas: `rectilinear is True and not thin` → E; `rectilinear is True and thin` → E (es una caja fina); `rectilinear is False` → ruta orgánica (C si ≥ 2 fotos, si no B; con `organic_variant="TRELLIS"` reservado para proveedores externos: dejar el nombre configurable); `rectilinear is None` → VLM si hay clave, si no orgánica con `reason="sin etiqueta"`. La decisión y la regla se registran en meta como hoy. Nuevo kind `box_legs` en `parametric_spec.py`: caja con `leg_height_cm` (defecto 10), `leg_size_cm` (5), `leg_inset_cm` (3) y/o `plinth_height_cm` (zócalo retranqueado `plinth_inset_cm`, defecto 2); caja envolvente exacta (tests existentes). `classify()` mapea "patas" → `box_legs` con patas y "zócalo" → `box_legs` con zócalo; sin palabras clave, `box` como hoy. Overrides: p03 → `box_legs` con patas 10 cm; p08 → `box_legs` con zócalo 5 cm. Ejecutar `uv run bakeoff run --variants E --pieces p03,p08 --run-id mcp-higgsfield --skip-preflight --no-resume --no-fit-box` y comparar visualmente los renders con las fotos (`outputs/clean/p03_*.png`, `p08_*.png`); copiar los tres cuartos a `outputs/renders/E2_<pieza>_three_quarter.png`. Tests: reglas de enrutado para los cuatro casos y la pieza fina; `box_legs` ambas variantes con caja exacta.

### Task 4 · Bucle de refinado: escala, geometría, material (paralela)

**Archivos**: `src/harness/refine/__init__.py` (nuevo), `src/harness/refine/rules.py` (nuevo), `src/harness/clients/meshy.py` (añadir `retexture`), `tests/test_refine.py` (nuevo), `tests/fixtures/meshy/retexture_*.json`.

**Pasos**: `rules.py`: `diagnose(candidate_meta, scores|None) -> list[Issue]` con tres issues: `scale` (error máximo entre tolerancia y guardia, sin ajuste aplicado), `geometry` (error > guardia, candidato rechazado por la guardia o `n_components` > 5.000), `material` (puntuación de materiales ≤ 3 si hay scores). `plan(issues) -> list[Action]` con acciones `fit_box`, `regenerate` (pide un candidato más a la variante, máximo +2), `retexture` (requiere proveedor con `retexture`). `__init__.py`: `refine_candidate(run_id, piece_id, variant, candidate, *, max_rounds=2, providers=...) -> RefineReport` que aplica las acciones en orden, re-postprocesa con `blender_post.postprocess(..., fit_box=True)` cuando toca, y escribe `refine.json` en el candidato con el historial; nunca gasta más de `max_rounds` acciones de pago. `MeshyClient.retexture(model_url_or_path, *, image_ref: Path | None, text_prompt: str | None, dst_glb) -> GenerationOutcome` según la API de Meshy (consultar docs; subir el GLB si la API exige URL pública: documentar la limitación y mockear). Tests: `diagnose` sobre metas sintéticas (los tres issues y ninguno), `plan` respeta el tope, `refine_candidate` con `postprocess` y proveedor mockeados aplica `fit_box` y `regenerate`, `retexture` del cliente con `pytest-httpx`.

### Task 5 · Hojas de jueces humanos en el informe (paralela)

**Archivos**: `src/harness/eval/sheets.py` (nuevo), `src/harness/eval/report.py` (añadir sección), `tests/test_sheets.py` (nuevo), `tests/fixtures/sheets/*.csv`.

**Pasos**: `sheets.py`: `read_sheet(path) -> dict[blind_id, HumanScore]` tolerante a celdas vacías, `merge(key, sheets: dict[judge_name, dict]) -> list[JudgedRecord]` que une por `blind_id` con la clave `blind_key.csv`, `agreement(records) -> AgreementStats` (porcentaje de acuerdo en "apto" por pareja de jueces y kappa de Cohen simple), `summarize_by_variant(records)`. `report.py`: `render_markdown(run_id, summaries, human=None)` añade la sección "Jueces humanos" con tasa de aptos por juez y variante, acuerdo entre jueces y acuerdo con el juez automático cuando exista. Tests: lectura con celdas vacías, unión con clave, kappa en casos conocidos (acuerdo total = 1, azar ≈ 0), sección en el markdown. No tocar `cli.py` (T7 añade `--sheets`).

### Task 6 · Tolerancia configurable, promesa y proveedor por API (paralela)

**Archivos**: `src/harness/core/models.py` (tolerancia), `src/harness/core/config.py` (`Settings.scale_tolerance`), `src/harness/post/blender_post.py` (usar la tolerancia de Settings), `src/harness/eval/judge.py` (umbrales de `escala` derivados de la tolerancia: 5 si < tol, 3 si < 3·tol, 1), `docs/promesa.md` (nuevo), `docs/proveedores.md` (nuevo), `tests/test_tolerance.py` (nuevo).

**Pasos**: `SCALE_TOLERANCE` pasa a ser el valor por defecto; `Settings.scale_tolerance` lee `SCALE_TOLERANCE` de `.env` (defecto 0.03); `GeometryMetrics.scale_ok` y `PostResult.scale_ok` aceptan `tolerance` opcional; el juez deriva los umbrales. `docs/promesa.md`: categorías cubiertas con la tasa observada (macizo, cerámica, tapizado), excluidas (metal, vidrio, tubo fino, cromo), piezas finas rectilíneas por E, tolerancia vendida (3 % o 5 %, con lo que cambia en el piloto: 6/28 vs 13/28 candidatos), requisitos de foto (enlazar `prep/requirements.py`), y la frase de la promesa. `docs/proveedores.md`: tabla de proveedores con API (Tripo, Meshy, TRELLIS-2 autoalojado en GPU alquilada, Hunyuan vía Tencent Cloud), coste por pieza, qué cliente del harness los cubre, qué falta para producción (claves, cuotas, reintentos), y que Magnific/Higgsfield por MCP sirvieron para el piloto pero no son una API de producto. Tests: tolerancia desde `.env`, `scale_ok` con 0.05, umbrales del juez.

### Task 7 · Cableado de CLI, integración y revisión (serial, al final)

**Archivos**: `src/harness/cli.py`, `src/harness/core/registry.py`, `README.md`, `justfile`, `tests/test_integration.py`, `tests/test_core.py` (solo si T1 lo requiere).

**Pasos**: comandos nuevos `bakeoff deliver --run-id --piece --variant --candidate`, `bakeoff refine --run-id [--piece] [--max-rounds]`, opción `report --sheets a.csv,b.csv`, opción global `--scale-tolerance`; `run` usa el enrutador por reglas cuando no hay clave; `justfile` con `deliver`, `refine`. Test de integración end-to-end con stubs: run FAKE → refine (fit) → deliver (postprocess y Blender mockeados) → report con una hoja humana. README: secciones de entrega, refinado, jueces humanos, tolerancia, promesa y proveedores. Suite completa verde y ruff limpio.

## Orden de ejecución

1. T1–T6 en paralelo (archivos disjuntos; ninguna toca `cli.py`, `registry.py`, `README.md`).
2. T7 sola.
3. Revisión final de rama.
