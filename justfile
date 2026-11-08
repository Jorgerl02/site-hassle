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
# post="--no-post" omite el postprocesado Blender)
run variants="A,B,C,D,E,F" run_id="" post="--post":
    if [ -n "{{run_id}}" ]; then \
        uv run bakeoff run --variants "{{variants}}" --pieces all --candidates 2 {{post}} --run-id "{{run_id}}"; \
    else \
        uv run bakeoff run --variants "{{variants}}" --pieces all --candidates 2 {{post}}; \
    fi

# Evalúa una ejecución: geometría, renders Blender, juez VLM y hoja ciega
eval run_id:
    uv run bakeoff eval --run-id "{{run_id}}"

# Genera runs/<run_id>/eval/report.md
report run_id:
    uv run bakeoff report --run-id "{{run_id}}"

# Tests offline (sin red, sin Blender, sin claves)
test:
    uv run pytest -q

# Lint
lint:
    uv run ruff check src tests

# Tests que ejecutan un Blender real (opt-in), p. ej. just blender-test /Applications/Blender.app/Contents/MacOS/Blender
blender-test bin:
    HARNESS_BLENDER_TEST_BIN="{{bin}}" uv run pytest -q tests/test_post.py tests/test_parametric.py tests/test_eval.py
