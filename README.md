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
| F | Enrutado: un VLM decide rectilínea → E; orgánica → C (≥ 2 fotos) o B (1 foto) | ¿El híbrido supera a cada ruta sola? |

`FAKE` es una variante de prueba sin llamadas externas (exporta una caja con las medidas).

## Instalación

Requisitos: [`uv`](https://docs.astral.sh/uv/), Python 3.12 (lo instala `uv`), Blender 4.x y,
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
| `ANTHROPIC_API_KEY` | Juez VLM de `eval` y clasificador de F | [platform.claude.com](https://platform.claude.com/settings/keys) → API Keys |
| `BLENDER_BIN` | Variante E y renders de control de `eval` | Ruta absoluta al ejecutable de [Blender 4.x](https://www.blender.org/download/), p. ej. `/Applications/Blender.app/Contents/MacOS/Blender` |

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
| `just run post="--no-post"` | `uv run bakeoff run --variants A,B,C,D,E,F --pieces all --candidates 2 --no-post` | Genera sin postprocesado Blender |
| `just eval r1` | `uv run bakeoff eval --run-id r1` | Geometría, renders, juez VLM y hoja ciega |
| `just report r1` | `uv run bakeoff report --run-id r1` | Escribe `runs/r1/eval/report.md` |
| `just test` | `uv run pytest -q` | Tests offline (sin red, sin claves, sin Blender) |
| `just lint` | `uv run ruff check src tests` | Lint |
| `just blender-test /ruta/a/blender [glb]` | `HARNESS_BLENDER_TEST_BIN=/ruta/a/blender HARNESS_TEXTURED_GLB=glb uv run pytest -q tests/test_post.py tests/test_parametric.py tests/test_eval.py` | Tests con un Blender real (opt-in) |

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
- `bakeoff eval --no-render` no lanza Blender y reutiliza los renders que ya existan.
- **Comprobación previa.** Antes de la primera llamada de pago, `run` comprueba las claves que
  necesita cada variante pedida (A/B: `TRIPO_API_KEY`; C: Tripo + `GEMINI_API_KEY`; D:
  `MESHY_API_KEY`; F: `ANTHROPIC_API_KEY` + Tripo + Gemini) y Blender si se pide E o `--post`.
  Si falta algo, imprime el resumen y termina con código 2. `--skip-preflight` continúa de
  todos modos (F sin Blender solo avisa: sus piezas rectilíneas van a la ruta orgánica).
- **Ejecución reanudable.** El `meta.json` del run se escribe tras **cada** paso (pieza,
  variante) y se fusiona con el existente: un run interrumpido conserva lo hecho. Sin
  `--run-id`, `run` usa la marca de tiempo UTC (`20261108T101500Z`); con un id ya usado y
  `--resume` (por defecto) se salta, con el aviso «reutilizado», cada paso cuyo resultado está
  registrado sin error y con todos sus `model.glb` en disco; `--no-resume` lo repite todo.
  `results` guarda el último resultado de cada paso, `errors` nunca pierde entradas (un
  reintento marca las anteriores con `superseded: true`) y `total_cost_usd` acumula el coste de
  cada paso ejecutado.
- Un fallo de una pieza o variante se registra en `errors` con un `kind` y la ejecución
  continúa: `infra` (falta una clave, sin Blender, error de red) queda fuera del denominador
  como «sin puntuar (infraestructura)»; `candidate` (la tarea del proveedor falla, no hay GLB)
  cuenta como pieza no apta. En C y D un candidato fallido no descarta los ya pagados: se anota
  en su `meta.json` (`error`) y en las notas; solo si fallan todos se registra el error.
- E en una pieza con `rectilinear=false` no genera nada y se registra en `skipped` con
  `kind: "not_applicable"`; con `rectilinear` vacío, E se ejecuta.

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

El informe automático usa solo el juez VLM; la consolidación de las hojas humanas (cruce con
`blind_key.csv` y comparación con el VLM) se hace a mano en una hoja de cálculo.

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

## Costes estimados de una ejecución completa

30 piezas × 6 variantes × 2 candidatos (E siempre genera 1 candidato determinista y no cuesta nada
salvo CPU). En la muestra actual 22 piezas tienen ≥ 2 fotos y 8 una sola; según la etiqueta del
CSV, 13 son rectilíneas (F → E) y 17 orgánicas (12 con ≥ 2 fotos → C, 5 con 1 foto → B). Si el
VLM de F coincide con el CSV:

| Concepto | Llamadas | Precio en `pricing.py` | Coste (constantes) | Coste con cifras reales conocidas |
|---|---|---|---|---|
| Tripo (A 60 + B 60 + C 60 + F 34) | 214 generaciones | 0,25 $/gen | 53,5 $ | 64–86 $ (0,30–0,40 $/gen) |
| Meshy (D) | 60 generaciones | 0,65 $/gen | 39,0 $ | 1.800 créditos (30/gen); USD por crédito sin precio público |
| Gemini (C 120 + F 48 vistas) | 168 imágenes | 0,039 $/img | 6,6 $ | sin verificar para `gemini-nano-banana-2.1` |
| Claude Sonnet 5.5, juez (≈ 317 candidatos, ~7 imágenes, ~12k tokens entrada / 300 salida) | 317 | 2 / 10 $/MTok | 8,6 $ | igual; hasta ~13 $ con reintentos |
| Claude Sonnet 5.5, clasificador de F | 30 | 2 / 10 $/MTok | 0,3 $ | igual |
| **Total** | | | **≈ 108 $** | **≈ 119–145 $** (Meshy y Gemini a la constante) |

Peor caso de F (el VLM marca todo como orgánico o no hay Blender, así que E cae a B/C): 240
generaciones Tripo (+26), 208 imágenes Gemini (+40) y 13 juicios más: ≈ +8 $ con constantes
(total ≈ 116 $) y ≈ +10–13 $ con el precio real de Tripo (total hasta ≈ 158 $). Por pieza y variante IA sale ≈ 0,6–0,9 $ con dos candidatos,
coherente con los 0,8–1,2 $ de la spec (que incluye postprocesado y reintentos). El control
manual del día 1 en la web de Tripo va aparte. Cada `meta.json` registra el coste real de cada
llamada con las constantes de `src/harness/core/pricing.py`; actualízalas antes del run real.

## Limitaciones conocidas

- **Precios provisionales.** Las constantes de `src/harness/core/pricing.py` son placeholders
  (`# TODO verificar`): Tripo real ≈ 0,30–0,40 $/gen (constante 0,25); Meshy cobra 30 créditos por
  generación sin precio público en USD por crédito (constante 0,65); el precio de Gemini
  `gemini-nano-banana-2.1` está sin verificar; Sonnet 5.5 está a 2/10 $/MTok. Los costes del
  informe heredan esas cifras.
- **Renders Workbench sin reflejos.** Los renders de control no muestran reflejos, lo que deprime
  la nota de `materiales` en metal y vidrio (el prompt del juez lo advierte, pero sesga la
  categoría `metal_vidrio`).
- **Blender nunca ejecutado de verdad.** `bpy_post.py`, `bpy_parametric.py` y `bpy_render.py` no
  se han ejecutado aún en un Blender real; ejecuta `just blender-test <bin>` antes del run.
- **Postprocesado depende de Blender.** Sin `BLENDER_BIN` (o con `--no-post`) se evalúa el GLB
  crudo de cada proveedor y la comparación deja de cumplir «postprocesado idéntico para todas»;
  revisa que ningún candidato tenga `post.ok = false` antes de dar el informe por bueno.
- **Piezas finas.** Con fondos de 3–6 cm, la tolerancia de escala del 3 % es de 1–2 mm: el eje
  `escala` será casi siempre < 4 en esas piezas.
- **`scores.jsonl` no es ciego.** Contiene la variante; a los jueces humanos solo se les da
  `blind_sheet.csv` y `eval/blind/`.
- **Regla de la ganadora.** El delta de > 15 puntos se aplica al total, no por categoría.
- **Reanudación a nivel de paso.** `--resume` reutiliza un paso (pieza, variante) completo; un
  paso con algún candidato fallido pero otros correctos cuenta como terminado y no se repite.
  `total_cost_usd` no incluye lo gastado en pasos que terminaron en error (p. ej. vistas Gemini
  de un C cuyos candidatos fallaron todos): está en los `meta.json` de sus candidatos.
- **Hojas humanas fuera del informe.** El informe solo agrega el juez VLM; las hojas humanas se
  consolidan a mano.

## Estructura del repositorio

```
data/sample.csv              # muestra fija de 30 piezas (con image_urls)
data/images/                 # fotos descargadas por ingest (no versionadas)
reports/                     # spec del test (Test lean 30 días.md) e informes
src/harness/
  cli.py                     # comando bakeoff: run, eval, report
  core/                      # modelos, almacenamiento, precios, config, registro, lanzador Blender
  clients/                   # Tripo, Meshy, Gemini imagen, VLM (Claude)
  data/ingest.py             # descarga de fotos de la muestra
  prep/                      # limpieza de fotos y vistas sintéticas
  post/                      # postprocesado Blender y generación paramétrica
  variants/                  # A–F (f_router.py es el enrutado)
  eval/                      # geometría, renders, juez, hoja ciega, informe
tests/                       # tests offline; fixtures en tests/fixtures/
justfile                     # atajos de los comandos
```
