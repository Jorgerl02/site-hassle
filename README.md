# Harness bake-off foto→3D

Banco de pruebas que compara seis variantes de pipeline foto→3D (A–F) sobre una muestra fija de
30 piezas de mobiliario de catálogos españoles (`data/sample.csv`). Genera los modelos, los mide,
los hace puntuar por un juez VLM a ciegas, prepara una hoja ciega para jueces humanos y escribe
un informe con la tasa de aptos por variante y categoría, el coste y los segundos por pieza.

Implementa el **Paso previo · Prueba interna de calidad** de la spec
([`reports/Test lean 30 días.md`](reports/Test%20lean%2030%20d%C3%ADas.md)): saber, en 10 días y
sin hablar con comercios, si algún pipeline produce modelos lo bastante buenos para enseñarlos.

| Variante | Enfoque | Pregunta que responde |
|---|---|---|
| A | Tripo directo, primera foto tal cual | Línea base |
| B | Limpieza de la primera foto (rembg, recorte, fondo blanco) → Tripo `image_to_model`; nunca multivista, porque las fotos de catálogo no llevan etiqueta de vista | ¿Cuánto aporta el preprocesado? |
| C | Limpieza → 4 vistas sintéticas con Gemini → Tripo multivista (la única variante multivista: sus vistas sí están etiquetadas) | ¿Las vistas inventadas ayudan o perjudican? |
| D | Limpieza → Meshy | ¿Importa el proveedor? |
| E | Paramétrico en Blender (cajas con medidas exactas y la foto como textura); solo piezas rectilíneas (`rectilinear=false` → «no aplicable») | ¿La ruta sin IA gana en su categoría? |
| F | Enrutado: rectilínea → E; orgánica → C (≥ 2 fotos) o B (1 foto). Decide por reglas (etiqueta `rectilinear` del CSV, sin coste) o por un VLM (`--router-classifier`) | ¿El híbrido supera a cada ruta sola? |

`FAKE` es una variante de prueba sin llamadas externas (exporta una caja con las medidas).

## Instalación

Requisitos: [`uv`](https://docs.astral.sh/uv/), Python 3.12 (lo instala `uv`), Blender (probado con 5.2) y,
opcionalmente, [`just`](https://just.systems) para los atajos.

```bash
uv python install 3.12
uv sync
cp .env.example .env
```

Rellena `.env` (el entorno del proceso tiene prioridad sobre `.env`; nunca subas `.env`):

| Variable | Para qué | Dónde se consigue |
|---|---|---|
| `TRIPO_API_KEY` | Variantes A, B, C y F | [platform.tripo3d.ai](https://platform.tripo3d.ai) → API Keys |
| `MESHY_API_KEY` | Variante D | [meshy.ai](https://www.meshy.ai) → Settings → API |
| `GEMINI_API_KEY` | Vistas sintéticas de C (y F cuando enruta a C) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `ANTHROPIC_API_KEY` | Juez VLM de `eval` y clasificador VLM de F (opcional: sin clave, F decide por reglas) | [platform.claude.com](https://platform.claude.com/settings/keys) → API Keys |
| `BLENDER_BIN` | Variante E, postprocesado, renders de control de `eval`, `refine` y `deliver` | Ruta absoluta al ejecutable de [Blender](https://www.blender.org/download/), p. ej. `/Applications/Blender.app/Contents/MacOS/Blender` |
| `SCALE_TOLERANCE` | Tolerancia de escala (0.03 = 3 % por defecto); ver [Tolerancia de escala](#tolerancia-de-escala) | — |

Blender solo se usa como subproceso (`BLENDER_BIN --background --python <script> -- <args>`);
nunca se importa `bpy` en el proceso de Python. Sin `BLENDER_BIN`, `run` se detiene en la
comprobación previa si se pide E o `--post` (ver abajo); con `--skip-preflight`, E falla como
infraestructura, F cae a la ruta orgánica y `eval` registra los candidatos sin renders como «sin
puntuar (infraestructura)».

## Protocolo de 10 días (resumen)

El detalle está en la spec, sección
[«Paso previo · Prueba interna de calidad»](reports/Test%20lean%2030%20d%C3%ADas.md#paso-previo--prueba-interna-de-calidad-sin-comercios)
y la tabla de etapas en
[«Pipeline de calidad»](reports/Test%20lean%2030%20d%C3%ADas.md#pipeline-de-calidad-validadores-y-vistas-sintéticas).

1. **Día 1 · Control.** 10 piezas por la web de Tripo tal cual, a mano. Es la referencia que el
   pipeline debe superar con claridad; la variante A la aproxima por API.
2. **Muestra fija.** 30 piezas (7–8 por categoría: `macizo_mate`, `tapizado`, `metal_vidrio`,
   `patas_finas`) con medidas conocidas, fijadas en `data/sample.csv` antes de generar nada. No se
   cambia ninguna pieza después.
3. **Definición de «bueno», por escrito.** Rúbrica 1–5 en cuatro ejes: parecido con la foto,
   geometría (sin agujeros, patas, trasera creíble), materiales y escala (error de caja
   envolvente < 3 % por eje). **Apto = ≥ 4 en los cuatro ejes sin retoque humano.**
4. **Tres jueces a ciegas.** El VLM (automático en `eval`), tú sin ver la variante y una tercera
   persona ajena. Las puntuaciones se registran antes de revelar la variante.
5. **Resultado.** Tasa de aptos por variante y categoría, coste y tiempo por pieza. Pasa si una
   variante supera el 60 % de aptos en al menos dos categorías y mejora la línea base (A) en más
   de 15 puntos.
6. **Un harness, N variantes.** Todas implementan la misma interfaz (`Variant.run(pieza, workdir,
   candidatos) → VariantResult`) y se evalúan con la misma rúbrica, jueces e informe.
7. **Compromiso previo.** Si pasa, el siguiente paso es enseñar el output a comercios y pedir
   pago, no otra ronda de pipeline. Si no pasa, se documenta si el fallo es de entrada o de
   geometría; solo el primero justifica seguir.

Calendario orientativo: día 1 control y rúbrica; día 2 `ingest` y revisión de fotos; días 3–5
`run` por tandas (A, B, D primero; C, E, F después); días 6–7 `eval` y hojas ciegas humanas;
días 8–9 consolidar puntuaciones e informe; día 10 decisión por escrito.

## Comandos

| `just` | Equivalente sin `just` | Qué hace |
|---|---|---|
| `just install` | `uv python install 3.12 && uv sync` | Instala Python y dependencias |
| `just ingest` | `uv run python -m harness.data.ingest` | Descarga las fotos a `data/images/<id>/<n>.jpg` y escribe un informe de ingesta |
| `just run` | `uv run bakeoff run --variants A,B,C,D,E,F --pieces all --candidates 2` | Genera los modelos |
| `just run variants="A,B" run_id="r1"` | `uv run bakeoff run --variants A,B --pieces all --candidates 2 --run-id r1` | Solo algunas variantes, con id fijo |
| `just run post="--no-post"` | `uv run bakeoff run --variants A,B,C,D,E,F --pieces all --candidates 2 --no-post` | Genera sin postprocesado Blender. E sigue necesitando Blender: si se pide E sin `BLENDER_BIN`, la comprobación previa termina con código 2 (quita E de `variants` o añade `--skip-preflight`) |
| `just run skip_preflight="--skip-preflight"` | `uv run bakeoff run --variants A,B,C,D,E,F --pieces all --candidates 2 --skip-preflight` | Continúa aunque falten claves o Blender (los pasos afectados fallan como infraestructura) |
| `just eval r1` | `uv run bakeoff eval --run-id r1` | Geometría, renders, juez VLM y hoja ciega |
| `just report r1` | `uv run bakeoff report --run-id r1` | Escribe `runs/r1/eval/report.md` |
| `just report-sheets r1 ana.csv,luis.csv` | `uv run bakeoff report --run-id r1 --sheets ana.csv,luis.csv` | Informe con la sección de jueces humanos |
| `just refine r1 p08` | `uv run bakeoff refine --run-id r1 --piece p08 --max-rounds 2` | Diagnostica y corrige los candidatos de una pieza |
| `just deliver r1 p05,p15 "--variant B"` | `uv run bakeoff deliver --run-id r1 --pieces p05,p15 --variant B --out-dir outputs/deliver` | GLB ligero, USDZ y visor web por pieza |
| `just validar p01,p02` | `uv run bakeoff validar --pieces p01,p02` | Comprueba las fotos de entrada (`bakeoff requisitos` lista los requisitos) |
| `just test` | `uv run pytest -q` | Tests offline (sin red, sin claves, sin Blender) |
| `just lint` | `uv run ruff check . && uv run ruff format --check .` | Lint y formato |
| `just blender-test /ruta/a/blender [glb]` | `HARNESS_BLENDER_TEST_BIN=/ruta/a/blender HARNESS_TEXTURED_GLB=glb uv run pytest -q tests/test_post.py tests/test_parametric.py tests/test_eval.py tests/test_deliver.py` | Tests con un Blender real (opt-in) |

`blender-test` y la textura en los renders: Workbench pinta la textura del nodo de imagen
**activo** de cada material, y un GLB PBR trae varios (color base, normales, rugosidad).
`bpy_render.py` activa antes de renderizar el nodo conectado a `Base Color` del Principled BSDF.
El cubo de `tests/fixtures/` no tiene textura, así que para comprobarlo pasa como segundo
argumento un GLB PBR texturizado con, al menos, color base y mapa de normales (por ejemplo, un
GLB real de Tripo o Meshy, o `DamagedHelmet.glb` de los
[glTF Sample Assets de Khronos](https://github.com/KhronosGroup/glTF-Sample-Assets)); el test
falla si el render frontal parece un mapa de normales (azul dominante). No se versionan
fixtures binarios.

Opciones útiles:

- `bakeoff run --pieces p01,p07` limita las piezas; `--sample otro.csv` cambia la muestra;
  `--runs-root otra/carpeta` cambia la raíz de salidas (también en `eval` y `report`).
- `bakeoff run --post` (por defecto) pasa **todos** los candidatos de todas las variantes
  (también E y FAKE) por el mismo postprocesado Blender headless (`bpy_post.py`: escala a las
  medidas, centra, decima) y escribe `model_post.glb`; `eval` lo usa en lugar de `model.glb`
  cuando existe. El resultado queda en `meta.json` → `post` (`ok`, `seconds`, `errors`,
  `errors_axis`, `triangles_before/after`, `draco`). Sin Blender se registra
  `post: {"ok": false, "reason": "sin Blender"}` sin reintentarlo en cada candidato y el run
  continúa (se evalúa el GLB crudo); un fallo de Blender guarda el final del log en `reason`.
  `--no-post` omite el paso.
- **Postprocesado: ajuste a la caja del catálogo (`--fit-box`, desactivado por defecto).** Tras
  la escala uniforme, si el error residual de **cada** eje emparejado (alto = vertical; ancho y
  fondo emparejados por tamaño) es ≤ `--fit-guard` (0,10 por defecto), `bpy_post.py` aplica una
  escala distinta por eje respecto al centro de la base (las patas siguen en Z = 0) para que la
  caja envolvente mida exactamente ancho × alto × fondo del catálogo. Si algún eje supera la
  guarda no se ajusta nada y `post_meta.json` → `fit_skip_reason` dice qué eje y cuánto. Es un
  paso legítimo para responder «¿cabe?» (el usuario ve en RA la caja real del producto), pero
  deforma el modelo hasta un 10 % por eje, así que **se informa siempre**: `post_meta.json` y
  `meta.json` → `post` guardan `fit_box_applied`, `fit_factors` ({x, y, z} en Blender) y
  `errors_before_fit` (los residuos de la escala uniforme); `eval` los copia a `scores.jsonl` y
  el informe añade la columna «Escala antes del ajuste» y cuántos candidatos se ajustaron. La
  nota `escala` se calcula sobre el modelo final, así que con el ajuste sube: compara siempre
  con el error previo. También en `python -m harness.data.import_glb ... --fit-box
  --fit-guard 0.10`.
- `bakeoff eval --no-render` no lanza Blender y reutiliza los renders que ya existan.
- **Comprobación previa.** Antes de la primera llamada de pago, `run` comprueba las claves que
  necesita cada variante pedida (A/B: `TRIPO_API_KEY`; C: Tripo + `GEMINI_API_KEY`; D:
  `MESHY_API_KEY`; F: las claves de su ruta orgánica, Tripo + Gemini por defecto, y
  `ANTHROPIC_API_KEY` solo con `--router-classifier vlm`) y Blender si se pide E o `--post`.
  Si falta algo, imprime el resumen y termina con código 2. `--skip-preflight` continúa de
  todos modos (F sin Blender solo avisa: sus piezas rectilíneas van a la ruta orgánica).
- **Ejecución reanudable.** El `meta.json` del run se escribe tras **cada** paso (pieza,
  variante) y se fusiona con el existente: un run interrumpido conserva lo hecho. Sin
  `--run-id`, `run` usa la marca de tiempo UTC (`20261108T101500Z`); con un id ya usado y
  `--resume` (por defecto) se salta, con el aviso «reutilizado», cada paso cuyo resultado está
  registrado sin error, con todos sus `model.glb` en disco y sin ningún candidato fallido por
  infraestructura (`meta.json` del candidato con `error` y `error_kind: "infra"`: red, clave);
  esos pasos se repiten enteros, así que un corte de red se reintenta al reanudar. Un paso con
  candidatos fallidos solo del lado del proveedor (`error_kind: "candidate"`) se reutiliza tal
  cual, y un paso que falló entero (error activo en `errors`) siempre se repite.
  `--no-resume` lo repite todo.
  `results` guarda el último resultado de cada paso, `errors` nunca pierde entradas (un
  reintento marca las anteriores con `superseded: true`) y `total_cost_usd` acumula el coste de
  cada paso ejecutado.
- Un fallo de una pieza o variante se registra en `errors` con un `kind` y la ejecución
  continúa: `infra` (falta una clave, sin Blender, error de red) queda fuera del denominador
  como «sin puntuar (infraestructura)»; `candidate` (la tarea del proveedor falla, no hay GLB)
  cuenta como pieza no apta. En A, B, C y D un candidato fallido no descarta los ya pagados: se
  anota en su `meta.json` (`error` y `error_kind`, con el mismo clasificador
  `harness.core.errors.error_kind`) y en las notas; solo si fallan todos se registra el error del
  paso. `eval` no carga ningún GLB de esos candidatos: con `error_kind: "infra"` quedan
  `unscored` (fuera del denominador, «sin puntuar (infraestructura)»); con `"candidate"` (o sin
  `error_kind`) quedan `candidate_failed` (no aptos). No reciben id ciego.
- E en una pieza con `rectilinear=false` no genera nada y se registra en `skipped` con
  `kind: "not_applicable"`; con `rectilinear` vacío, E se ejecuta. Si la descripción menciona
  «patas» o «zócalo», E genera una caja con patas o zócalo (`box_legs`); los ajustes por pieza
  están en `data/parametric_overrides.json`.
- **Enrutado de F (`--router-classifier auto|vlm|rules`, `auto` por defecto).** `rules` usa la
  etiqueta `rectilinear` del CSV: rectilínea → E; orgánica → C con ≥ 2 fotos o B con 1; sin
  etiqueta → ruta orgánica (o el VLM, si hay clave). `vlm` pregunta siempre al VLM y exige
  `ANTHROPIC_API_KEY`. `auto` usa el VLM si hay clave y, si no, las reglas. El motivo queda en
  `meta.json` → `router.rule` y en las notas. `--organic-variant D` (o cualquier otra variante
  registrada salvo E y F) sustituye a C/B como ruta orgánica; la comprobación previa pide
  entonces sus claves.

Salidas:

```
runs/<run_id>/meta.json                                   # run: variantes, piezas, resultados, coste acumulado, errores, no aplicables
runs/<run_id>/<pieza>/<variante>/cand_<n>/model.glb       # modelo generado
runs/<run_id>/<pieza>/<variante>/cand_<n>/model_post.glb  # modelo postprocesado (Blender)
runs/<run_id>/<pieza>/<variante>/cand_<n>/post_meta.json  # errores de escala y triángulos del postprocesado
runs/<run_id>/<pieza>/<variante>/cand_<n>/meta.json       # coste, segundos, parámetros, respuestas
runs/<run_id>/<pieza>/<variante>/cand_<n>/renders/*.png   # renders de control (eval)
runs/<run_id>/<pieza>/F/route_<X>/...                     # trabajo interno de la variante delegada por F
runs/<run_id>/eval/scores.jsonl                           # una línea por candidato (¡contiene la variante!)
runs/<run_id>/eval/blind_sheet.csv + eval/blind/<id>/     # hoja ciega y renders anonimizados
runs/<run_id>/eval/blind_key.csv                          # clave blind_id → pieza/variante/candidato
runs/<run_id>/eval/report.md                              # informe
```

## Cómo rellenar la hoja ciega

`eval` asigna a cada candidato un id ciego (`B001`, `B002`…) con un barajado de semilla fija y
copia sus cinco renders (`front`, `side`, `back`, `three_quarter`, `top`) a
`runs/<run_id>/eval/blind/<blind_id>/`, para que ninguna ruta revele la variante.

1. Entrega a cada juez humano **solo** `blind_sheet.csv` y la carpeta `eval/blind/`. **Nunca**
   `scores.jsonl`, `blind_key.csv`, `meta.json` ni el resto de `runs/`: contienen el nombre de la
   variante. Las fotos originales están en `data/images/<id>/` (rutas en la columna `fotos`).
2. Cada juez hace una copia de la hoja con su nombre (`blind_sheet_<juez>.csv`) y, por fila,
   mira las fotos y los cinco renders y rellena de 1 a 5:
   - `parecido`: 5 mismo producto … 1 no identificable.
   - `geometria`: 5 sin agujeros, patas completas, trasera creíble … 1 rota.
   - `materiales`: 5 color, textura y acabado fieles … 1 sin textura o erróneo.
   - `escala`: el harness la mide (error de caja envolvente: 5 si < 3 %, 3 si < 10 %, 1 si no);
     el juez humano puede dejarla en blanco y tomar la de `scores.jsonl` al consolidar.
   - `apto`: `sí` solo si los cuatro ejes son ≥ 4 sin imaginar retoques.
   - `comentario`: el defecto principal en una frase.
   Las definiciones completas de cada nivel están en `src/harness/eval/judge.py` (`RUBRIC_PROMPT`),
   las mismas que ve el VLM.
3. Las hojas se cierran y se guardan **antes** de abrir `blind_key.csv`. Solo entonces se cruzan
   por `blind_id` con la clave para obtener pieza y variante.

Las hojas rellenadas se añaden al informe con `--sheets` (ver
[Jueces humanos en el informe](#jueces-humanos-en-el-informe)).

## Cómo leer el informe

`report.md` tiene dos tablas y una decisión:

- **Aptos por variante y categoría.** La unidad es la pieza: una pieza es apta para una variante si
  al menos uno de sus candidatos es apto (el pipeline genera N y se queda el mejor). Cada celda es
  `% (aptas/n)`. «Δ vs A» son puntos porcentuales sobre la línea base en el total.
- **Medias por eje, coste y tiempo.** Media de cada eje sobre los candidatos puntuados; coste y
  tiempo por pieza (segundos y minutos) = suma de sus candidatos, promediada sobre las piezas;
  «% mallas cerradas» y «media de componentes» sobre los candidatos medidos con trimesh. Debajo,
  **Coste total** = generación + enrutado VLM de F + juez VLM.
- **Escala.** Antes de medir, el modelo se reescala de forma uniforme con la misma regla que el
  postprocesado (`max(medidas) / max(caja cruda)`): el eje `escala` mide **proporciones**, y un
  GLB crudo y su copia postprocesada dan la misma nota. `scores.jsonl` guarda la caja cruda
  (`raw_extents_cm`), el factor (`scale_factor`) y el origen (`trimesh` o `post_meta`), y el
  modelo que respondió al juez (`judge_model`; el juez nunca usa modelos de respaldo).
  Con `--fit-box`, «Escala» puntúa el modelo ya ajustado; «Escala antes del ajuste» es la media
  del error máximo |relativo| tras la escala uniforme, y una línea indica en cuántos candidatos
  se aplicó el ajuste.
- **Regla de la ganadora (spec).** Una variante gana si tiene **> 60 % de aptos en al menos 2
  categorías** y **> 15 puntos sobre A** en el total. Sin A en el run no se declara ganadora.
- **Denominador.** Cuentan todas las piezas con algún candidato puntuado o con un fallo atribuible
  al candidato (`kind: "candidate"`: la tarea del proveedor falla o no hay GLB; o modelo
  ausente, GLB ilegible o malla vacía), que cuentan como no aptas. Se excluyen las piezas sin
  puntuar por infraestructura (`kind: "infra"`: sin Blender, sin clave, error de red, o error
  del juez); aparecen en la columna «Sin puntuar (infraestructura)». Si esa columna no es 0, el
  porcentaje se calcula sobre menos de 30 piezas: corrige la infraestructura y repite `run`
  (reanuda) y `eval`. Para E se excluyen además las piezas orgánicas (`not_applicable`): el
  informe indica «E: N/M piezas aplicables» y sus tasas son sobre ese subconjunto.
- **Ruido.** Con 30 piezas, diferencias < 15 puntos son ruido: no permiten afirmar que una variante
  sea mejor que otra, aunque la tabla muestre un número mayor.

## Jueces humanos en el informe

```bash
uv run bakeoff report --run-id r1 --sheets ana.csv --sheets luis.csv   # o --sheets ana.csv,luis.csv
```

Cada hoja es una copia de `runs/<run_id>/eval/blind_sheet.csv` rellenada por un juez; el
**nombre del archivo** (sin `.csv`) es el nombre del juez, así que dos hojas no pueden llamarse
igual. `report` las cruza por `blind_id` con `eval/blind_key.csv` y añade la sección «Jueces
humanos» (tasa de aptos por juez y variante, con la pieza como unidad, igual que el informe
automático) y «Acuerdo entre jueces» (% de acuerdo y kappa de Cohen por pareja, incluido el juez
automático cuando hay puntuaciones del VLM).

- Columnas obligatorias: `blind_id` y `apto`; se leen además `parecido`, `geometria`,
  `materiales`, `escala` (1–5, admite coma decimal: `4,5`) y `comentario`. Las demás columnas de
  la hoja (`fotos`, `render_*`) se ignoran.
- `apto`: `sí`, `si`, `s`, `yes`, `1`, `true` o `apto` → apto; `no`, `n`, `0`, `false` o
  `no apto` → no apto; vacío → sin valorar (la fila no cuenta). Mayúsculas y tildes dan igual.
- Se acepta la exportación de Excel en español: separador `;` y BOM UTF-8. Los comentarios
  entrecomillados pueden tener saltos de línea.
- Errores claros, sin traza: una hoja con un `blind_id` que no está en la clave (por ejemplo, la
  hoja de otra ejecución), un `blind_id` repetido, un `apto` ilegible o una columna obligatoria
  ausente terminan con código 1 y el motivo.

## Tolerancia de escala

La tolerancia de escala es el error relativo máximo por eje de la caja envolvente para que el
eje `escala` valga 5 (y el candidato pueda ser apto). Por defecto es **0,03 (3 %)**; el umbral
de la nota 3 es 10/3 de la tolerancia (10 % con el 3 %).

- `SCALE_TOLERANCE=0.03` en `.env` la fija para todos los comandos (admite coma decimal).
- `--scale-tolerance 0.05` la cambia para un comando: `run` (postprocesado), `eval` (nota de
  escala y apto) y `refine` (diagnóstico de escala).
- `eval` guarda la tolerancia usada en cada línea de `scores.jsonl` (`scale_tolerance`) y el
  informe la muestra en la cabecera («Tolerancia de escala: 3 %»; si se mezclan varias, lo
  avisa). Compara solo informes con la misma tolerancia.

Las piezas finas (alguna medida < 8 cm o proporción ancho/fondo o alto/fondo > 15) son las que
más sufren con el 3 %: 1–2 mm de error ya bajan la nota.

## Refinado (`refine`)

```bash
uv run bakeoff refine --run-id r1 --piece p08 --variant A --candidate 1 --dry-run
uv run bakeoff refine --run-id r1 --piece p08 --max-rounds 0   # solo acciones gratuitas
uv run bakeoff refine --run-id r1 --piece p08,p10 --max-rounds 2 --no-retexture
```

Diagnostica cada candidato elegido (`--piece` obligatorio, uno, varios o `all`; `--variant` y
`--candidate` filtran) y aplica, de una en una, la primera acción pendiente; después vuelve a
diagnosticar. Usa el bloque `post` de `meta.json` y, si existe, la fila de `scores.jsonl`.

| Problema | Cuándo | Acción |
|---|---|---|
| Escala | Error entre la tolerancia y la guarda de `--fit-guard` (10 %) sin ajuste aplicado | Ajuste a la caja (`fit_box`), gratis |
| Geometría | Error por encima de la guarda, ajuste rechazado por la guarda o > 5.000 componentes | Regenerar un candidato nuevo (de pago) |
| Sin postprocesado | `post` ausente o fallido y sin evaluación | Repetir el postprocesado, gratis |
| Material | Nota de `materiales` ≤ 3 en `scores.jsonl` | Retexturizar con Meshy (de pago) |

- **Gasto.** `--max-rounds` (2 por defecto) es el máximo de acciones de pago por candidato; con
  0 solo se aplican las gratuitas. Regenerar crea `cand_<N+1>` sin tocar los existentes, como
  mucho 2 veces por pieza y variante (en total, entre llamadas); una variante por API cobra
  N+1 generaciones para conseguir ese candidato. Retexturizar escribe `model_retex.glb` y
  conserva `model.glb`; `--no-retexture` lo desactiva.
- **Comprobación previa.** Si una acción de pago dentro de `--max-rounds` necesita una clave que
  falta (`MESHY_API_KEY` para retexturizar; las de la variante para regenerar), `refine` termina
  con código 2 antes de tocar nada. Las variantes importadas (`MG_*`, `HF_*`) no se pueden
  regenerar: el paso queda como omitido.
- `--dry-run` imprime problemas y plan sin aplicar nada ni escribir archivos.
- Historial en `cand_<n>/refine.json` (pasos, coste, problemas antes y después). Su coste se
  suma a `total_cost_usd` del run y queda aparte en `refine_cost_usd`.
- Después de retexturizar hay que repetir `eval`: la nota de materiales no se recalcula sola.

## Entrega web (`deliver`)

```bash
uv run bakeoff deliver --run-id r1 --pieces p05,p15 --variant B --candidate 1 --out-dir outputs/deliver
```

Parte de `model_post.glb` del candidato y escribe, por pieza, en `<out-dir>/<pieza>/` (sin
`--out-dir`, en la carpeta del candidato):

- `model_web.glb`: decimado a `--max-tris` (60.000), texturas a `--max-tex` px (2048) y
  recodificadas a JPEG (PNG solo con transparencia real), compresión Draco. Objetivo:
  `--size-limit` (5.000.000 bytes). Si lo supera, se reintenta una vez con la mitad de
  triángulos y texturas de 1024 px.
- `model.usdz` para AR Quick Look en iPhone (exportado por Blender, texturas JPEG/PNG).
- `viewer.html` con `<model-viewer>` 4.4.0: botón «Ver en tu espacio», tamaño real fijo en RA
  y medidas del catálogo.
- `deliver_meta.json` (tamaños, triángulos, texturas e intentos) y `deliver_blender.log`.

Sin `--variant` o `--candidate`, se usa el único que tenga `model_post.glb`; si hay varios, el
comando pide elegir. Imprime tamaños, triángulos y la ruta del visor. Termina con código 1 si
algún GLB supera el límite o falla, y con 2 si no hay Blender.

**Ver el visor.** Abierto como archivo (`file://`) no carga el modelo: hay que servirlo por HTTP.

```bash
python -m http.server 8000 --directory outputs/deliver
# abre http://localhost:8000/p05/viewer.html
```

Desde el móvil en la misma red sirve la IP del ordenador; Quick Look funciona por HTTP en Safari,
pero WebXR y Scene Viewer (Android) exigen HTTPS, así que para probar la RA en un teléfono real
hace falta publicarlo con HTTPS. Limitación conocida: el USDZ no admite Draco ni compresión
(≈ 3,5–4,5 MB con 60.000 triángulos) y el límite de tamaño solo se aplica al GLB.

## Fotos de entrada (`validar`, `requisitos`)

`bakeoff requisitos` lista lo que debe cumplir la foto (vista frontal o de tres cuartos, fondo
claro o uniforme, pieza completa, ≥ 1.000 px en el lado mayor, pieza ≥ 25 % del lado mayor de la
foto y medidas en cm). `bakeoff validar foto.jpg …` o `bakeoff validar --pieces p01,p02` los
comprueba (con rembg: la primera vez carga el modelo) y explica en castellano qué falla; una
imagen dañada o ilegible se informa como problema. Termina con código 1 si alguna foto no
cumple. La regla de tamaño mide la caja envolvente del objeto, no la fracción de píxeles: deja
pasar siluetas finas (percheros, lámparas) bien encuadradas.

## Promesa y proveedores

- [`docs/promesa.md`](docs/promesa.md): qué prometemos al cliente (piezas aceptadas, precisión
  y foto necesaria), con los datos del piloto.
- [`docs/proveedores.md`](docs/proveedores.md): proveedores de generación 3D, coste por pieza y
  qué falta para producción (las cifras en dólares indican su fuente).

## Costes estimados de una ejecución completa

30 piezas × 6 variantes × 2 candidatos (E siempre genera 1 candidato determinista y no cuesta nada
salvo CPU). En la muestra actual 22 piezas tienen ≥ 2 fotos y 8 una sola; según la etiqueta del
CSV, 13 son rectilíneas (F → E) y 17 orgánicas (12 con ≥ 2 fotos → C, 5 con 1 foto → B). Si el
VLM de F coincide con el CSV:

| Concepto | Llamadas | Precio en `pricing.py` | Coste (constantes) | Coste con cifras reales conocidas |
|---|---|---|---|---|
| Tripo (A 60 + B 60 + C 60 + F 34) | 214 generaciones | 0,30 $/gen | 64,2 $ | 64–86 $ (0,30–0,40 $/gen) |
| Meshy (D) | 60 generaciones | 0,65 $/gen | 39,0 $ | 1.800 créditos (30/gen); USD por crédito sin precio público |
| Gemini (C 120 + F 48 vistas) | 168 imágenes | 0,039 $/img | 6,6 $ | sin verificar para `gemini-nano-banana-2.1` |
| Claude Sonnet 5.5, juez (≈ 317 candidatos, ~7 imágenes, ~12k tokens entrada / 300 salida) | 317 | 2 / 10 $/MTok | 8,6 $ | igual; hasta ~13 $ con reintentos |
| Claude Sonnet 5.5, clasificador de F (solo con VLM; con reglas, 0) | 30 | 2 / 10 $/MTok | 0,3 $ | igual |
| **Total** | | | **≈ 119 $** | **≈ 119–145 $** (Meshy y Gemini a la constante) |

Peor caso de F (el VLM marca todo como orgánico o no hay Blender, así que E cae a B/C): 240
generaciones Tripo (+26), 208 imágenes Gemini (+40) y 13 juicios más: ≈ +10 $ con constantes
(total ≈ 128 $) y ≈ +12 $ con 0,40 $/gen (total hasta ≈ 157 $). Por pieza y variante IA sale ≈ 0,6–0,9 $ con dos candidatos,
coherente con los 0,8–1,2 $ de la spec (que incluye postprocesado y reintentos). El control
manual del día 1 en la web de Tripo va aparte. Cada `meta.json` registra el coste real de cada
llamada con las constantes de `src/harness/core/pricing.py` (fuentes en
[`docs/proveedores.md`](docs/proveedores.md)); revísalas antes del run real.

## Limitaciones conocidas

- **Precios en parte provisionales.** `src/harness/core/pricing.py`: Tripo 0,30 $/gen (cota
  inferior del precio público, 0,30–0,40); Meshy cobra 30 créditos por generación y 10 por
  retexturizado, sin precio público en USD por crédito (constante provisional 0,65 $/gen, de la
  que se deriva el retexturizado); Gemini `gemini-nano-banana-2.1` sin verificar; Sonnet 5.5 a
  2/10 $/MTok. Los costes del informe heredan esas cifras.
- **Renders Workbench sin reflejos.** Los renders de control no muestran reflejos, lo que deprime
  la nota de `materiales` en metal y vidrio (el prompt del juez lo advierte, pero sesga la
  categoría `metal_vidrio`).
- **Blender real solo en tests opt-in.** Los scripts `bpy_*.py` se han ejecutado con Blender
  5.2.3; la suite normal los simula. Con otra versión, ejecuta `just blender-test <bin>` antes
  del run.
- **Entrega web.** La RA no se ha probado en un teléfono real (el USDZ pasa el
  `ComplianceChecker` de ARKit) y el USDZ va sin comprimir.
- **Postprocesado depende de Blender.** Sin `BLENDER_BIN` (o con `--no-post`) se evalúa el GLB
  crudo de cada proveedor y la comparación deja de cumplir «postprocesado idéntico para todas»;
  revisa que ningún candidato tenga `post.ok = false` antes de dar el informe por bueno.
- **Piezas finas.** Con fondos de 3–6 cm, la tolerancia de escala del 3 % es de 1–2 mm: el eje
  `escala` será casi siempre < 4 en esas piezas.
- **`scores.jsonl` no es ciego.** Contiene la variante; a los jueces humanos solo se les da
  `blind_sheet.csv` y `eval/blind/`.
- **Regla de la ganadora.** El delta de > 15 puntos se aplica al total, no por categoría.
- **Reanudación a nivel de paso.** `--resume` reutiliza un paso (pieza, variante) completo; un
  paso con algún candidato fallido por el proveedor pero otros correctos cuenta como terminado y
  no se repite. Si algún candidato falló por infraestructura, se repite el paso entero (también
  sus candidatos correctos, que se vuelven a pagar).
  `total_cost_usd` no incluye lo gastado en pasos que terminaron en error (p. ej. vistas Gemini
  de un C cuyos candidatos fallaron todos): está en los `meta.json` de sus candidatos.

## Estructura del repositorio

```
data/sample.csv              # muestra fija de 30 piezas (con image_urls)
data/images/                 # fotos descargadas por ingest (no versionadas)
reports/                     # spec del test (Test lean 30 días.md) e informes
docs/                        # promesa al comercio y proveedores
src/harness/
  cli.py                     # comando bakeoff: run, eval, report, refine, deliver, validar, requisitos
  core/                      # modelos, almacenamiento, precios, config, registro, lanzador Blender
  clients/                   # Tripo, Meshy, Gemini imagen, VLM (Claude)
  data/ingest.py             # descarga de fotos de la muestra
  prep/                      # limpieza de fotos y vistas sintéticas
  post/                      # postprocesado Blender, generación paramétrica y entrega web
  refine/                    # bucle de refinado: diagnóstico, plan y acciones
  variants/                  # A–F (f_router.py es el enrutado)
  eval/                      # geometría, renders, juez, hoja ciega, hojas humanas, informe
tests/                       # tests offline; fixtures en tests/fixtures/
justfile                     # atajos de los comandos
```
