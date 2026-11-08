# Recetas del harness bake-off foto→3D. Requiere `just` (https://just.systems) y `uv`.
# Cada receta es un atajo de un comando `uv run ...` (ver README).

# Lista las recetas
default:
    @just --list

# Instala Python 3.12 y las dependencias del proyecto
install:
    uv python install 3.12
    uv sync

# Descarga las fotos de la muestra a data/images/<id>/<n>.jpg
ingest:
    uv run python -m harness.data.ingest

# Ejecuta las variantes sobre las 30 piezas (run_id vacío = marca de tiempo UTC;
# post="--no-post" omite el postprocesado Blender, pero E sigue necesitando Blender: sin él la
# comprobación previa termina con código 2 si se pide E;
# skip_preflight="--skip-preflight" continúa aunque falten claves o Blender)
run variants="A,B,C,D,E,F" run_id="" post="--post" skip_preflight="":
    if [ -n "{{run_id}}" ]; then \
        uv run bakeoff run --variants "{{variants}}" --pieces all --candidates 2 {{post}} {{skip_preflight}} --run-id "{{run_id}}"; \
    else \
        uv run bakeoff run --variants "{{variants}}" --pieces all --candidates 2 {{post}} {{skip_preflight}}; \
    fi

# Evalúa una ejecución: geometría, renders Blender, juez VLM y hoja ciega
eval run_id:
    uv run bakeoff eval --run-id "{{run_id}}"

# Genera runs/<run_id>/eval/report.md
report run_id:
    uv run bakeoff report --run-id "{{run_id}}"

# Informe con las hojas de los jueces humanos, p. ej. just report-sheets r1 ana.csv,luis.csv
report-sheets run_id sheets:
    uv run bakeoff report --run-id "{{run_id}}" --sheets "{{sheets}}"

# Diagnostica y corrige candidatos de una pieza (max_rounds=0: solo acciones gratuitas;
# extra="--dry-run" solo muestra el plan), p. ej. just refine r1 p08 0 "--variant A --candidate 1"
refine run_id piece max_rounds="2" extra="":
    uv run bakeoff refine --run-id "{{run_id}}" --piece "{{piece}}" --max-rounds {{max_rounds}} {{extra}}

# Entrega web (GLB ligero, USDZ y visor) en outputs/deliver/<pieza>/,
# p. ej. just deliver mcp-higgsfield p05,p15 "--variant MG_TRELLIS2"
deliver run_id pieces extra="":
    uv run bakeoff deliver --run-id "{{run_id}}" --pieces "{{pieces}}" --out-dir outputs/deliver {{extra}}

# Comprueba las fotos de entrada de unas piezas ('all' = toda la muestra)
validar pieces="all":
    uv run bakeoff validar --pieces "{{pieces}}"

# Tests offline (sin red, sin Blender, sin claves)
test:
    uv run pytest -q

# Lint
lint:
    uv run ruff check .
    uv run ruff format --check .

# Tests que ejecutan un Blender real (opt-in), p. ej. just blender-test /Applications/Blender.app/Contents/MacOS/Blender
# glb (opcional): GLB PBR texturizado para comprobar que los renders muestran el color base
blender-test bin glb="":
    HARNESS_BLENDER_TEST_BIN="{{bin}}" HARNESS_TEXTURED_GLB="{{glb}}" uv run pytest -q tests/test_post.py tests/test_parametric.py tests/test_eval.py tests/test_deliver.py
