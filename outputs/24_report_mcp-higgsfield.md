# Informe del bake-off · mcp-higgsfield

Apto = ≥ 4 en los cuatro ejes (parecido, geometría, materiales, escala) sin retoque. Una pieza es apta si al menos uno de sus candidatos lo es.

Denominador: todas las piezas con algún candidato puntuado o con un fallo atribuible al candidato (tarea del proveedor fallida, sin GLB, modelo ausente, GLB ilegible o malla vacía), que cuentan como no aptas; se excluyen las piezas sin puntuar por infraestructura (sin Blender, sin clave de API, error de red o del juez) y, para cada variante, las piezas en las que no es aplicable (E solo se ejecuta en piezas rectilíneas).

## Aptos por variante y categoría

| Variante | macizo_mate | tapizado | metal_vidrio | patas_finas | Total | Δ vs A | Ganadora |
|---|---|---|---|---|---|---|---|
| HF_HUNYUAN | — | — | — | — | — | — | no |
| HF_TRIPO_CLEAN | — | — | — | — | — | — | no |
| HF_TRIPO_RAW | — | — | — | — | — | — | no |
| MG_HUNYUAN31PRO | — | — | — | — | — | — | no |
| MG_TRELLIS2 | — | — | — | — | — | — | no |

## Medias por eje, coste y tiempo

| Variante | Parecido | Geometría | Materiales | Escala | Coste medio por pieza | Tiempo medio por pieza | % mallas cerradas | Media de componentes | Sin puntuar (infraestructura) |
|---|---|---|---|---|---|---|---|---|---|
| HF_HUNYUAN | — | — | — | — | 0,00 USD | 0,0 s (0,0 min) | 0 % | 2258,5 | 4 |
| HF_TRIPO_CLEAN | — | — | — | — | 0,00 USD | 0,0 s (0,0 min) | 0 % | 197,4 | 5 |
| HF_TRIPO_RAW | — | — | — | — | 0,00 USD | 0,0 s (0,0 min) | 0 % | 526,0 | 1 |
| MG_HUNYUAN31PRO | — | — | — | — | 0,00 USD | 0,0 s (0,0 min) | 0 % | 1810,5 | 2 |
| MG_TRELLIS2 | — | — | — | — | 0,00 USD | 0,0 s (0,0 min) | 0 % | 5797,5 | 2 |

**Coste total:** 0,00 USD = generación 0,00 USD + enrutado VLM (F) 0,00 USD + juez VLM 0,00 USD.

Mallas cerradas y componentes: solo candidatos medidos con trimesh (GLB legible).

## Decisión

No hay línea base (variante A) en esta ejecución: no se declara ganadora.

Regla: > 60 % de aptos en al menos 2 categorías y > 15 puntos sobre la línea base (A) en el total.

**Nota:** Diferencias < 15 puntos sobre 30 piezas son ruido: con esta muestra no permiten afirmar que una variante sea mejor que otra.
