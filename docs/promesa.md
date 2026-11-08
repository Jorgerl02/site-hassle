# Qué prometemos al cliente

Este documento fija qué piezas aceptamos, con qué precisión las entregamos y qué foto necesitamos. Los números salen del piloto de 16 piezas: rondas 4 y 5 de `outputs/README.md`, y las puntuaciones de E con `panel_table` en `outputs/25_juez_claude_p04.csv`. El juez fue Claude sin ciego, con la rúbrica de la spec: una pieza es **apta** si parecido, geometría, materiales y escala puntúan 4 o más.

## La promesa

> Envíanos una foto limpia y las medidas de la pieza. Te devolvemos un modelo 3D listo para web y realidad aumentada, a la escala del catálogo (±3 % por eje), en piezas de madera o piedra maciza, cerámica y tapizado. Si no alcanza la calidad, no lo entregamos.

La última frase es la parte que nos protege: en el piloto la mitad de las piezas todavía no llega a apta, así que el compromiso es **filtrar**, no garantizar que toda pieza sale.

## Categorías cubiertas

Mejor candidato por pieza, acumulado de las rondas 4 y 5 y de las puntuaciones de E con `panel_table` (`outputs/25_juez_claude_p04.csv`):

| Categoría | Aptas | Piezas aptas | Qué falla en el resto |
|---|---|---|---|
| Macizo (madera, piedra, microcemento) | 2 de 6 | p01 mesa redonda, p07 mesa de travertino | Geometría inventada (patas de p04, base de p06), textura rota (p08), patas ausentes (p03) |
| Cerámica (jarrones) | 2 de 2 | p02 jarrón de arcilla, p05 jarrón de gres | — |
| Tapizado | 4 de 8 | p14 butaca bouclé, p15 sillón Matilda, p11 y p12 cabeceros | Color o tejido perdido (p09, p10, p13), base inventada (p16) |
| **Total del piloto** | **8 de 16 (50 %)** | | El umbral de la spec era 60 % |

En la clasificación del CSV la cerámica cuenta como `macizo_mate`: por eso el informe dice "macizo 4 de 8".

Las piezas que salen aptas lo hacen por tres vías:

- **TRELLIS-2** sobre fotos limpias: jarrones, butacas de bouclé y mesas de veta sencilla.
- **Ajuste a la caja del catálogo** (`--fit-box`, guardia del 10 %): convirtió en aptas p01, p02 y p14, que se habían quedado entre el 3 y el 8 % de error de escala.
- **Variante E paramétrica en Blender** para lo que de verdad es una composición de cajas (ver más abajo).

## Categorías excluidas

| Categoría | Resultado | Por qué la excluimos |
|---|---|---|
| Metal, cromo | 0 aptas (p17 lámpara cromada: 31,5 % de error, cromo perdido) | Los generadores pierden el reflejo y deforman los arcos |
| Vidrio | Sin probar en el piloto | Excluido por el mismo motivo que el metal (reflejo y transparencia) |
| Tubo fino, patas finas | 0 aptas (p24 perchero: 19,5 % de error) | La forma sale, pero las proporciones no; además la foto suele no pasar la validación |

Una pieza de estas categorías se rechaza al dar de alta, antes de gastar créditos (lo aplica el validador de requisitos de foto de la tarea 1; hoy es una regla documentada, no un bloqueo en el CLI).

## Piezas finas y rectilíneas: solo con la variante E

Regla de "pieza fina": alguna dimensión menor de 8 cm, o una relación ancho/fondo o alto/fondo mayor de 15. Los dos cabeceros del piloto (3 y 6 cm de fondo) salieron de los generadores con 20 cm de fondo o convertidos en sofás: errores del 568 % al 4.317 %. La variante E (cajas paramétricas en Blender con la foto proyectada) los resolvió los dos a coste cero, y también la mesa de paneles p07.

E **no** resuelve patas torneadas, zócalos, tablones inclinados ni detalles (p03, p04, p08 se quedan en "parecido pero no igual"). Prometemos piezas finas solo cuando son rectilíneas.

## Tolerancia de escala: 3 % o 5 %

La tolerancia es el error relativo máximo del bounding box por eje frente a las medidas del catálogo. Por defecto es **3 %** y se configura con `SCALE_TOLERANCE` en `.env` (fracción: `0.03` = 3 %, `0.05` = 5 %). La misma cifra decide `scale_ok` en la geometría y en el postprocesado, y los umbrales del eje `escala` del juez: 5 por debajo de la tolerancia, 3 por debajo de 10/3 de la tolerancia (3 % → 10 %, 5 % → 16,7 %), 1 en el resto.

Lo que cambia en el piloto (candidatos de Magnific de la ronda 4, sin ajuste a la caja):

| Tolerancia | Candidatos dentro | Lectura |
|---|---|---|
| 3 % | 6 de 28 | La mayoría se queda entre el 3 y el 9 %, justo fuera |
| 5 % | 13 de 28 | Más del doble, sin tocar el modelo |

Con el ajuste a la caja (ronda 5) el error de escala final queda en ≈ 0 % cuando el candidato está dentro de la guardia del 10 %, así que **vendemos 3 %**: es la cifra que el cliente entiende como "a medida", y el postprocesado la alcanza. El 5 % queda como opción para catálogos que acepten esa holgura a cambio de menos descartes; si se vende, hay que decirlo por escrito en el pedido.

## Requisitos de la foto

Los requisitos que ve el cliente están en `src/harness/prep/requirements.py` (`PHOTO_REQUIREMENTS`), y `explain()` traduce los fallos de validación a un mensaje en español. Resumen: vista frontal o de tres cuartos, fondo claro sin otros muebles, pieza completa en el encuadre, al menos 1.000 px en el lado mayor, la pieza ocupando una fracción mínima de la foto, y las medidas reales en centímetros.

## Lo que no prometemos

- Porcentaje de piezas aptas: el piloto da 50 %, por debajo del 60 % de la spec. Cada pieza se puntúa y solo se entrega si es apta.
- Material idéntico en tejidos con color saturado (p10 verde salió gris) ni texturas con mucho detalle fino (p08).
- Plazo cerrado por pieza: depende de la cola del proveedor (ver `docs/proveedores.md`).
