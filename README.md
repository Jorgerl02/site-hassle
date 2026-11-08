# Harness bake-off foto→3D

Compara variantes de pipeline foto→3D (A–F) sobre una muestra fija de 30 piezas de mobiliario
(`data/sample.csv`) y genera puntuaciones e informe por variante y categoría.

> Esqueleto: la documentación completa (protocolo, hoja ciega, costes) llega en la Tarea 8.

## Instalación

```bash
uv python install 3.12
uv sync
cp .env.example .env   # rellena las claves y BLENDER_BIN
```

## Comandos

```bash
uv run bakeoff run --variants A,B --pieces all --candidates 2 --run-id prueba
uv run bakeoff eval --run-id prueba
uv run bakeoff report --run-id prueba
```

Salidas en `runs/<run_id>/<pieza>/<variante>/cand_<n>/` y `runs/<run_id>/eval/`.

## Tests

```bash
uv run pytest
uv run ruff check src tests
```
