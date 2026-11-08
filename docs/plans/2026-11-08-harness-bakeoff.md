# Plan de implementación · Harness de bake-off de pipelines 3D

Spec: `reports/Test lean 30 días.md`, secciones "Paso previo · Prueba interna de calidad" (puntos 1–7) y "Pipeline de calidad". La spec manda; este plan la argumenta.

## Objetivo

Un único harness que ejecuta N variantes de pipeline (fotos + medidas → GLB) sobre una muestra fija de 30 piezas, aplica el mismo postprocesado, mide error de escala y geometría, renderiza vistas de control, pide una puntuación ciega a un VLM, genera la hoja ciega para jueces humanos y produce el informe por variante y categoría con coste y minutos por pieza.

## Global Constraints

- **Lenguaje y entorno**: Python ≥ 3.11 gestionado con `uv` (el sistema trae 3.9; `uv python install 3.12`). Layout `src/harness/`. CLI con `typer`, comando `bakeoff`. Modelos de datos con `pydantic` v2.
- **Interfaz de variante (congelada en la Tarea 1)**:
  ```python
  class Variant(Protocol):
      name: str                      # "A", "B", "C", "D", "E", "F"
      def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult: ...
  ```
  `VariantResult(variant: str, piece_id: str, candidates: list[Candidate], notes: str)`;
  `Candidate(index: int, glb_path: Path, cost_usd: float, seconds: float, meta: dict)`.
- **Esquema de pieza** (`Piece`): `id`, `name`, `store`, `source_url`, `category` ∈ {`macizo_mate`, `tapizado`, `metal_vidrio`, `patas_finas`}, `images: list[Path]`, `width_cm`, `height_cm`, `depth_cm`, `description: str`, `rectilinear: bool | None`.
- **Layout de salida**: `runs/<run_id>/<piece_id>/<variant>/cand_<n>/{model.glb, model_post.glb, renders/*.png, meta.json}`; `runs/<run_id>/eval/{scores.jsonl, blind_sheet.csv, blind_key.csv, report.md}`.
- **Categorías de muestra**: 30 piezas, 7–8 por categoría, fijadas en `data/sample.csv` antes de generar nada.
- **Umbrales de la spec**: apto = ≥ 4 en los cuatro ejes (parecido, geometría, materiales, escala) sin retoque; error de caja envolvente < 3 % por eje; una variante gana si > 60 % de aptos en ≥ 2 categorías y > 15 puntos sobre la línea base (variante A).
- **Red**: toda llamada externa va detrás de un cliente en `src/harness/clients/`. Las claves se leen de `.env` (`TRIPO_API_KEY`, `MESHY_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `BLENDER_BIN`). Los tests nunca tocan la red: HTTP mockeado con `pytest-httpx`; Blender y VLM mockeados o `skip` si no hay binario o clave.
- **Coste**: cada llamada externa registra `cost_usd` usando `src/harness/core/pricing.py` (tabla con constantes y comentario `# TODO verificar` con fecha y URL de la fuente).
- **Blender**: solo vía subproceso `BLENDER_BIN --background --python <script> -- <args>`; nunca `import bpy` en el proceso principal. Tests que lo requieren hacen `pytest.skip` si `BLENDER_BIN` no está.
- **Documentación antes de código**: Tripo API, Meshy API, Gemini image API (`google-genai`), Anthropic SDK y `bpy` cambian rápido. Consultar Context7 (`resolve-library-id` + `query-docs`) o la documentación oficial antes de escribir cada cliente. Para el SDK de Anthropic leer antes el skill `claude-api`.
- **Disciplina de archivos en tareas paralelas**: cada tarea toca solo sus módulos y su fichero de test. `pyproject.toml`, `README.md`, `src/harness/core/*`, `src/harness/cli.py` solo se editan en las Tareas 1 y 8. Cada tarea ejecuta solo `uv run pytest tests/test_<suyo>.py`. Ninguna tarea instala dependencias: todas se declaran en la Tarea 1.
- **Sin subagentes** dentro de los implementadores. **Sin commits** por parte de los implementadores: el coordinador commitea por tarea.
- Español en docs y mensajes al usuario; código, identificadores y comentarios en inglés.

## Tareas

### Tarea 1 · Núcleo del harness (serial, antes que todo)

**Archivos**: `pyproject.toml`, `.python-version`, `.env.example`, `README.md` (esqueleto), `src/harness/__init__.py`, `src/harness/core/models.py`, `src/harness/core/variant.py`, `src/harness/core/storage.py`, `src/harness/core/pricing.py`, `src/harness/core/config.py`, `src/harness/core/registry.py`, `src/harness/prep/clean.py`, `src/harness/clients/vlm.py`, `src/harness/cli.py`, `data/sample.csv` (solo cabecera), `tests/test_core.py`, `tests/conftest.py`.

**Pasos**:
1. `uv init` con Python 3.12; declarar en `pyproject.toml` TODAS las dependencias del proyecto: `typer`, `pydantic>=2`, `httpx`, `python-dotenv`, `pillow`, `rembg[cpu]`, `onnxruntime`, `trimesh`, `numpy`, `anthropic`, `google-genai`, `rich`; dev: `pytest`, `pytest-httpx`, `ruff`. Ejecutar `uv sync` una vez.
2. `models.py`: `Piece`, `Candidate`, `VariantResult`, `Scores` (cuatro ejes 1–5 + `apt: bool`), `GeometryMetrics` (bbox por eje en cm, error relativo por eje, `watertight`, `n_components`, `n_faces`). Carga de `data/sample.csv` → `list[Piece]` con validación de categorías y 30 filas máximo.
3. `variant.py`: el `Protocol` de la interfaz y una `FakeVariant` que copia un GLB de fixture (cubo) para tests e integración.
4. `storage.py`: funciones puras que devuelven rutas del layout; crean directorios; escriben/leen `meta.json`.
5. `pricing.py`: constantes `TRIPO_USD_PER_MODEL`, `MESHY_USD_PER_MODEL`, `GEMINI_IMAGE_USD`, `ANTHROPIC_INPUT_USD_PER_MTOK`, `ANTHROPIC_OUTPUT_USD_PER_MTOK`, cada una con `# TODO verificar <fecha> <url>`.
6. `config.py`: carga `.env`, expone `Settings` con las claves y `blender_bin: Path | None`.
7. `registry.py`: `get_variant(name) -> Variant` con registro por nombre; de momento solo `FAKE`.
8. `prep/clean.py`: `clean_image(src: Path, dst: Path, size: int = 1024) -> Path`: rembg, recorte al bbox del alfa con margen 8 %, pad a cuadrado, fondo blanco neutro; `validate_input(path) -> list[str]` (resolución ≥ 1000 px en el lado mayor, objeto detectado > 10 % del área).
9. `clients/vlm.py`: `VLMClient.ask_json(prompt: str, images: list[Path], schema_hint: str) -> dict` con el SDK de Anthropic (modelo configurable, por defecto `claude-sonnet-5-5`), reintento con backoff, registro de coste por tokens. Leer el skill `claude-api` antes.
10. `cli.py`: comandos `run --variants A,B --pieces all|id,id --candidates 2 --run-id`, `eval --run-id`, `report --run-id`; `run` carga piezas, resuelve variantes por registro, ejecuta y escribe `meta.json`; `eval` y `report` quedan como stubs que importan de `harness.eval` (módulos que crea la Tarea 6) con mensaje claro si faltan.
11. Tests: carga de CSV válida e inválida, layout de storage, `FakeVariant` produce 2 candidatos con GLB existente, `clean_image` sobre una imagen sintética (cuadrado de color sobre fondo), `validate_input` rechaza imagen pequeña, `VLMClient` con transporte mockeado parsea JSON.

### Tarea 2 · Cliente Tripo + variantes A y B (paralela)

**Archivos**: `src/harness/clients/tripo.py`, `src/harness/variants/a_tripo_direct.py`, `src/harness/variants/b_clean_tripo.py`, `tests/test_tripo.py`, `tests/fixtures/tripo/*.json`.

**Pasos**: consultar la documentación vigente de la API de Tripo (subida de imagen, `image_to_model`, `multiview_to_model`, consulta de tarea, descarga de GLB, parámetros de calidad/textura PBR). Implementar `TripoClient` con `httpx`, polling con timeout configurable y `cost_usd` desde `pricing`. Variante A: primera foto tal cual → `image_to_model`, N candidatos con semillas distintas. Variante B: `clean_image` sobre todas las fotos → `multiview_to_model` si hay ≥ 2 fotos, si no `image_to_model`. Guardar `meta.json` con request, task id, tiempos. Tests con `pytest-httpx` que recorren el ciclo completo con respuestas de fixture, incluidos fallo de tarea y timeout.

### Tarea 3 · Cliente Meshy + variante D (paralela)

**Archivos**: `src/harness/clients/meshy.py`, `src/harness/variants/d_clean_meshy.py`, `tests/test_meshy.py`, `tests/fixtures/meshy/*.json`.

**Pasos**: igual que la Tarea 2 con la API de Meshy (image-to-3D, multi-image si está disponible, polling, descarga GLB). Variante D: `clean_image` → Meshy. Tests mockeados análogos.

### Tarea 4 · Vistas sintéticas + variante C (paralela)

**Archivos**: `src/harness/prep/synth_views.py`, `src/harness/clients/gemini_image.py`, `src/harness/variants/c_synth_tripo.py`, `tests/test_synth_views.py`.

**Pasos**: consultar la documentación de `google-genai` para generación y edición de imagen. `GeminiImageClient.edit(image: Path, prompt: str) -> Path`. `generate_views(clean_front: Path, piece: Piece, workdir) -> dict[str, Path]` para `front`, `side`, `back`, `three_quarter` con prompts que exigen vista ortográfica, fondo blanco, misma pieza, proporciones según medidas. Validador `check_views(views, piece) -> ViewCheck`: relación de aspecto de la silueta frontal vs ancho/alto y lateral vs fondo/alto con tolerancia 10 %; descarta vistas que fallan; si quedan < 2 vistas, degrada a solo frontal. Variante C: limpieza → vistas → `TripoClient.multiview_to_model` (importar el cliente de la Tarea 2 por su ruta pública `harness.clients.tripo.TripoClient`; si en el momento de los tests no existe, mockear la importación). Tests: cliente mockeado, validador con siluetas sintéticas que pasan y fallan, degradación a frontal.

### Tarea 5 · Postprocesado Blender + variante E paramétrica (paralela)

**Archivos**: `src/harness/post/blender_post.py`, `src/harness/post/bpy_post.py`, `src/harness/post/bpy_parametric.py`, `src/harness/variants/e_parametric.py`, `src/harness/post/parametric_spec.py`, `tests/test_post.py`, `tests/test_parametric.py`.

**Pasos**: consultar la API de `bpy` 4.x (import glTF, dimensiones, origen, `decimate`, export glTF con Draco). `bpy_post.py` (se ejecuta dentro de Blender): importa GLB, escala uniforme para que la caja envolvente coincida con el eje mayor de las medidas y registra el error en los otros dos, origen en el centro de la base, `decimate` hasta ≤ 150k triángulos, texturas ≤ 2048 px, exporta GLB con Draco y escribe `post_meta.json`. `blender_post.py`: wrapper por subproceso con `BLENDER_BIN`, timeout, captura de log. `parametric_spec.py`: funciones puras que convierten `Piece` + tipo (`table`, `shelf`, `sideboard`, `slab`, `box`) en una lista de paralelepípedos con posiciones y tamaños en cm (patas, tablero, baldas, puertas). `bpy_parametric.py`: construye las piezas, aplica material con la foto limpia proyectada en las caras frontal y superior, exporta GLB. Variante E: clasifica el tipo con una heurística sobre `description` y proporciones (sin VLM aquí), genera y devuelve 1 candidato con `cost_usd = 0`. Tests puros para `parametric_spec` (una mesa 120×75×60 produce tablero + 4 patas con cotas correctas); tests de subproceso con `skip` si no hay Blender.

### Tarea 6 · Evaluación: geometría, renders, juez VLM, hoja ciega, informe (paralela)

**Archivos**: `src/harness/eval/geometry.py`, `src/harness/eval/render.py`, `src/harness/eval/bpy_render.py`, `src/harness/eval/judge.py`, `src/harness/eval/blind_sheet.py`, `src/harness/eval/report.py`, `src/harness/eval/__init__.py` (función `evaluate_run(run_id)` y `build_report(run_id)` que `cli.py` importa), `tests/test_eval.py`.

**Pasos**: `geometry.py` con `trimesh`: caja envolvente en cm, error relativo por eje frente a las medidas, `watertight`, número de componentes, caras; `scale_ok = max_error < 0.03`. `render.py` + `bpy_render.py`: 5 renders PNG 1024 px con fondo blanco (frontal, lateral, trasera, 3/4, cenital) por subproceso Blender; `skip` sin Blender. `judge.py`: prompt con la rúbrica de la spec (cuatro ejes 1–5, definiciones por nivel) que recibe las fotos originales y los renders, pide JSON estricto `{parecido, geometria, materiales, escala, comentario}`; `escala` se fija automáticamente desde `geometry` (5 si error < 3 %, 3 si < 10 %, 1 si mayor) y el VLM solo puntúa los otros tres; `apt = all(>=4)`. El juez nunca recibe el nombre de la variante. `blind_sheet.py`: CSV con `blind_id`, rutas de renders y columnas vacías para los cuatro ejes; `blind_key.csv` separado con `blind_id → piece_id, variant, candidate`, barajado con semilla. `report.py`: tabla por variante × categoría con `% aptos`, medias por eje, coste medio y segundos medios por pieza; fila de línea base (A) y delta en puntos; marca ganadora solo si cumple la regla de la spec (> 60 % en ≥ 2 categorías y > 15 puntos sobre A); nota explícita de ruido. Tests: geometría sobre un cubo de `trimesh` con medidas conocidas (error 0) y mal escalado (error detectado); juez con `VLMClient` mockeado; hoja ciega no contiene el nombre de variante y la clave la recupera; informe sobre `scores.jsonl` sintético aplica la regla correctamente.

### Tarea 7 · Muestra de 30 piezas e ingesta (paralela, requiere web)

**Archivos**: `data/sample.csv`, `data/SAMPLE_README.md`, `src/harness/data/ingest.py`, `tests/test_ingest.py`.

**Pasos**: seleccionar 30 piezas reales de catálogos españoles de mueble y decoración (tiendas en WooCommerce o PrestaShop preferentemente; también Kave Home, Maisons du Monde ES, Westwing ES si hace falta), 7–8 por categoría: `macizo_mate` (madera maciza, piedra, cerámica mate), `tapizado` (sofás, butacas, cabeceros), `metal_vidrio` (mesas de cristal, lámparas cromadas, estructuras metálicas), `patas_finas` (sillas de patas finas, mesas auxiliares, percheros). Para cada una: URL de la ficha, 1–4 URLs de imagen, medidas en cm, descripción breve, `rectilinear` a ojo. Registrar en `SAMPLE_README.md` los criterios de selección, la fecha y la advertencia de que las piezas no se cambian después. `ingest.py`: descarga las imágenes a `data/images/<id>/<n>.jpg` con `httpx`, respeta errores, no reintenta más de 2 veces, escribe un informe de las que fallan. Tests: CSV con exactamente 30 filas, categorías válidas, 7–8 por categoría, medidas positivas; `ingest` con HTTP mockeado.

### Tarea 8 · Enrutado F, registro, integración end-to-end y README (serial, al final)

**Archivos**: `src/harness/variants/f_router.py`, `src/harness/core/registry.py` (registrar A–F), `src/harness/cli.py` (conectar `eval` y `report`), `tests/test_integration.py`, `README.md`, `justfile` o `Makefile`.

**Pasos**: `f_router.py`: `VLMClient.ask_json` con las fotos y la pregunta "¿la pieza es rectilínea (cajas, tableros, patas rectas) u orgánica (curvas, tapizado, formas libres)?" → `rectilinear`; si rectilínea, delega en E; si orgánica, en C si hay ≥ 2 fotos, si no en B. Registrar A–F. Test de integración: `run` con `FakeVariant` y variantes reales con clientes mockeados sobre 2 piezas de fixture → `eval` con geometría real y juez mockeado → `report` produce tabla. README completo: instalación (`uv`, Blender, `.env`), protocolo de 10 días resumido con enlace a la spec, comandos, cómo rellenar la hoja ciega, cómo leer el informe, costes estimados por ejecución completa (30 piezas × 6 variantes × 2 candidatos). `justfile`: `install`, `ingest`, `run`, `eval`, `report`, `test`, `lint`.

## Orden de ejecución

1. Tarea 1 sola.
2. Tareas 2, 3, 4, 5, 6, 7 en paralelo (archivos disjuntos; ninguna toca núcleo, CLI, `pyproject` ni `README`).
3. Tarea 8 sola.
4. Revisión final de rama completa.
