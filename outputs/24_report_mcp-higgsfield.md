# Informe del bake-off · mcp-higgsfield

Apto = ≥ 4 en los cuatro ejes (parecido, geometría, materiales, escala) sin retoque. Una pieza es apta si al menos uno de sus candidatos lo es.

Denominador: todas las piezas con algún candidato puntuado o con un fallo atribuible al candidato (tarea del proveedor fallida, sin GLB, modelo ausente, GLB ilegible o malla vacía), que cuentan como no aptas; se excluyen las piezas sin puntuar por infraestructura (sin Blender, sin clave de API, error de red o del juez) y, para cada variante, las piezas en las que no es aplicable (E solo se ejecuta en piezas rectilíneas).

## Aptos por variante y categoría

| Variante | macizo_mate | tapizado | metal_vidrio | patas_finas | Total | Δ vs A | Ganadora |
|---|---|---|---|---|---|---|---|
| E | — | — | — | — | — | — | no |
| HF_HUNYUAN | — | — | — | — | — | — | no |
| HF_TRIPO_CLEAN | — | — | — | — | — | — | no |
| HF_TRIPO_RAW | — | — | — | — | — | — | no |
| MG_HUNYUAN31PRO | — | — | — | — | — | — | no |
| MG_TRELLIS2 | — | — | — | — | — | — | no |
| MG_TRELLIS2_R5 | — | — | — | — | — | — | no |

## Medias por eje, coste y tiempo

| Variante | Parecido | Geometría | Materiales | Escala | Escala antes del ajuste | Coste medio por pieza | Tiempo medio por pieza | % mallas cerradas | Media de componentes | Sin puntuar (infraestructura) |
|---|---|---|---|---|---|---|---|---|---|---|
| E | — | — | — | — | 0,0 % | 0,00 USD | 16,1 s (0,3 min) | 0 % | 6,0 | 2 |
| HF_HUNYUAN | — | — | — | — | 9,0 % | 0,00 USD | 0,0 s (0,0 min) | 0 % | 2258,5 | 4 |
| HF_TRIPO_CLEAN | — | — | — | — | 14,1 % | 0,00 USD | 0,0 s (0,0 min) | 0 % | 197,4 | 5 |
| HF_TRIPO_RAW | — | — | — | — | 9,1 % | 0,00 USD | 0,0 s (0,0 min) | 0 % | 526,0 | 1 |
| MG_HUNYUAN31PRO | — | — | — | — | 121,1 % | 0,00 USD | 0,0 s (0,0 min) | 0 % | 2144,3 | 14 |
| MG_TRELLIS2 | — | — | — | — | 393,6 % | 0,00 USD | 0,0 s (0,0 min) | 0 % | 5448,9 | 14 |
| MG_TRELLIS2_R5 | — | — | — | — | 8,4 % | 0,00 USD | 0,0 s (0,0 min) | 0 % | 4703,5 | 5 |

**Coste total:** 0,00 USD = generación 0,00 USD + enrutado VLM (F) 0,00 USD + juez VLM 0,00 USD.

Mallas cerradas y componentes: solo candidatos medidos con trimesh (GLB legible).

**Ajuste a la caja del catálogo:** aplicado en 9 de 50 candidatos medidos. «Escala» se puntúa sobre el modelo final (ajustado, si procede); «Escala antes del ajuste» es la media del error máximo |relativo| tras la escala uniforme, antes de cualquier ajuste por eje.

## Decisión

No hay línea base (variante A) en esta ejecución: no se declara ganadora.

Regla: > 60 % de aptos en al menos 2 categorías y > 15 puntos sobre la línea base (A) en el total.

**Nota:** Diferencias < 15 puntos sobre 30 piezas son ruido: con esta muestra no permiten afirmar que una variante sea mejor que otra.
