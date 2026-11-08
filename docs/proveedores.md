# Proveedores de generación 3D

Qué proveedor usamos para producción, cuánto cuesta por pieza y qué falta para pasar del piloto a un servicio. Los costes del piloto son los créditos medidos en `outputs/README.md`; las conversiones a dólares son aproximadas según el precio del plan de cada plataforma.

## Piloto frente a producción

En el piloto generamos a través de **Magnific** y **Higgsfield** por MCP, desde la sesión de Claude. Sirvió para comparar modelos sin claves de API, pero **no es una API de producto**: depende de una sesión interactiva, de créditos de un plan personal y de modelos que la plataforma puede cambiar sin aviso. Para producción hace falta una API con clave, cuotas y facturación propias.

## Tabla de proveedores

| Proveedor | Vía | Coste por pieza | Cliente del harness | Estado |
|---|---|---|---|---|
| **Tripo** (H3.1) | API Tripo OpenAPI v2 | ≈ 0,30 $ | `harness.clients.tripo` (variantes A, B, C, y F para orgánicas) | Cliente listo; falta clave |
| **Meshy** (Meshy 7) | API Meshy | ≈ 30 créditos por generación con textura | `harness.clients.meshy` (variante D) | Cliente listo; falta clave |
| **TRELLIS-2** autoalojado | GPU alquilada de 24 GB | ≈ 0,02–0,05 $ | Ninguno | El mejor del piloto; falta servidor y cliente |
| **Hunyuan 3D** (3.1 Pro) | Tencent Cloud | Sin medir por API | Ninguno | Falta cliente y cuenta en Tencent Cloud |
| *Tripo H3.1 vía Higgsfield* | MCP (solo piloto) | 9 créditos ≈ 0,30–0,45 $ | Importación manual (`harness.data.import_glb`) | No apto para producción |
| *Hunyuan 3.1 Pro vía Magnific* | MCP (solo piloto) | 1.070 créditos ≈ 0,75 $ | Importación manual | No apto para producción |
| *TRELLIS-2 vía Magnific* | MCP (solo piloto) | 730 créditos ≈ 0,50 $ | Importación manual | No apto para producción |

Resultado de calidad en el piloto (ronda 4, 14 piezas cada uno): TRELLIS-2 dio 2 aptas y 3 candidatos bajo el 3 % de escala; Hunyuan 3.1 Pro, 0 aptas y 3 bajo el 3 %; Tripo H3.1 vía Higgsfield, 0 de 6. Con dos candidatos de TRELLIS-2 por pieza y ajuste a la caja (ronda 5) subieron a aptas p01, p02 y p14.

## Recomendación

1. **TRELLIS-2 autoalojado** como proveedor principal: es el que más aptas dio y, en GPU alquilada, cuesta un orden de magnitud menos por pieza (0,02–0,05 $ frente a 0,50 $ vía Magnific). Generar dos candidatos por pieza cuesta menos de 0,10 $.
2. **Tripo por API** como alternativa gestionada mientras no exista el servidor: el cliente ya existe y está probado con respuestas simuladas.
3. **Meshy** para el retexturizado (cuando el material sale mal pero la forma es buena), no como generador principal.
4. **Hunyuan** solo si Tencent Cloud ofrece la versión 3.1 Pro con PBR a un precio competitivo: en el piloto no dio ninguna apta.

## Qué falta para producción

| Necesidad | Tripo | Meshy | TRELLIS-2 autoalojado | Hunyuan (Tencent Cloud) |
|---|---|---|---|---|
| Clave en `.env` | `TRIPO_API_KEY` | `MESHY_API_KEY` | Token del servidor propio | Credenciales de Tencent Cloud |
| Cliente en el harness | Hecho | Hecho | Por escribir (misma interfaz `generate`) | Por escribir |
| Reintentos | 408/429/5xx en llamadas idempotentes; la creación de tarea solo reintenta 429 | Igual | Por diseñar | Por diseñar |
| Cuotas y concurrencia | Límite de tareas simultáneas del plan, sin control en el harness | Igual | Una tarea por GPU; cola propia | Por medir |
| Precio verificado | `core/pricing.py` tiene 0,25 $ provisional | `core/pricing.py` tiene 0,65 $ provisional | Coste de GPU por hora / piezas por hora | Por medir |
| Caducidad de la URL del GLB | ≈ 5 minutos: descargar al terminar | Descarga al terminar | No aplica | Por medir |

Pendientes comunes: control de gasto por lote (tope en dólares antes de lanzar), cola con concurrencia limitada por proveedor, y alerta cuando la tasa de aptas de un proveedor baja.
