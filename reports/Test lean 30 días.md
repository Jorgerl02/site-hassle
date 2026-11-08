# Site Hassle · Test lean de 30 días

Complemento al informe [Site Hassle análisis crítico](Site%20Hassle%20an%C3%A1lisis%20cr%C3%ADtico.md). Fecha: 8-nov-2026.

## Qué se testea y qué no

| Se testea | No se testea (todavía) |
|---|---|
| Generador 3D para no técnicos: subes fotos o pegas un enlace, recibes GLB/USDZ y una vista "en tu espacio" | Plugin para Shopify/WooCommerce/PrestaShop |
| Un solo canal de captación no convencional | App nativa, cuenta de usuario, galería, equipo |
| Disposición a pagar sin empuje humano | Producción de modelos a mano, QA humano, venta a comerciantes |

Hipótesis única: *un no técnico paga por obtener un modelo 3D de un mueble a partir de fotos sin interactuar con herramientas 3D.*

## Alcance del producto (un fin de semana)

- Landing con precio visible y demo de salida real (no renders de Meshy, salida de tu pipeline).
- Stripe con un solo plan de pago, de 9 a 15 € al mes o 3 a 5 € por modelo. Sin plan gratuito ilimitado: cada generación cuesta 0,20–0,70 $ a Tripo o Meshy. Máximo una generación gratis con marca de agua.
- Backend: subida de fotos o URL, extracción de imágenes y medidas, llamada a la API, reescalado a las medidas, conversión a GLB/USDZ, visor con `model-viewer`.
- Nada de QA humano. Si el modelo sale mal, sale mal. Eso es parte de lo que se mide.

## Un canal, elegido antes de empezar

Elige uno y no lo cambies en 30 días. Candidatos: comunidades de impresión 3D (Printables, MakerWorld, r/3Dprinting), TikTok con vídeos generados en bucle, Product Hunt, directorios MCP. Presupuesto en dinero: 300–500 € en créditos de API y anuncios. Presupuesto en horas tuyas tras el lanzamiento: cero.

## Métricas y umbrales (día 30)

| Métrica | Umbral para seguir | Por qué ese número |
|---|---|---|
| Registros | ≥ 100 | Por debajo no hay muestra para medir nada |
| Pagadores | ≥ 5 | Freemius sitúa la conversión freemium en 2–5 % |
| Coste de captación por pagador | < 3 meses de cuota | Con churn SMB de 3–7 %/mes la vida media son 15–30 meses, pero un wrapper consumer churnea más |
| Tickets de soporte | < 1 por cada 20 usuarios | Si hay más, el negocio no es autónomo |
| Modelos aceptados por el usuario sin repetir | > 60 % | Si repiten, pagas 2–3 generaciones por cada una que cobras |
| Segunda generación en la misma cuenta | > 30 % de pagadores | Sin repetición no hay suscripción, hay compra única |

Si falla cualquiera de los tres primeros, se cierra. Si pasa los seis, se abre la fase 2.

## Fase 2: la persona con IA

La afirmación "una persona con IA rinde como 5 o 10" es cierta para código, contenido, anuncios y soporte de primer nivel. No lo es para lo que este negocio necesitaría si crece:

| Tarea | ¿Multiplica la IA? | Dato |
|---|---|---|
| Programar, publicar, responder tickets | Sí | |
| Revisar visualmente modelos y corregir escala o materiales | No, 20–60 min humanos por pieza | Notas de coste 3D, nov-2026 |
| Vender a comerciantes o agencias | No | Cold email ≈ 1 reunión por cada 100 envíos |
| Mejorar la calidad del modelo | No, el modelo es de Meshy o Tripo | |

Regla de contratación: no entra nadie hasta que el MRR cubra 1,5 veces su coste durante tres meses seguidos. Si el test pasa pero la persona acabaría haciendo QA de modelos, no contrates: eso es un estudio 3D con margen de estudio 3D.

## Techo que hay que aceptar antes de empezar

Si el test pasa y el canal escala, el escenario optimista de un wrapper que capta el 1 % del tráfico orgánico de Meshy son 80–200 pagadores y 800–2.000 € al mes brutos. Decide hoy si ese resultado justifica la fase 2. Si la respuesta es no, el test solo tiene sentido como aprendizaje, no como negocio.

## Ejecución paso a paso

### Día 0 · Decisiones cerradas por escrito antes de tocar código
1. Nombre y dominio nuevos, sin relación con Pietra ni Lince.
2. Precio: pago por modelo, 4,90 € uno o 14,90 € cinco. Nada de suscripción en el test: mide disposición a pagar, no retención.
3. Canal único: vídeo corto generado (TikTok, Reels, Shorts) con el antes y después de cada modelo. Product Hunt queda fuera, o se cuenta aparte.
4. Umbrales de corte copiados tal cual de la tabla anterior, firmados con fecha. No se cambian a mitad.
5. Alcance v1: solo subida de fotos. "Pegar enlace" se descarta hasta que alguien lo pida.

### Días 1–2 · Construcción (16–20 h)
- Next.js en Vercel. Una página: hero con demo real, subida de 1 a 4 fotos, campos de ancho, alto y fondo en cm, email, botón de pago.
- Stripe Checkout sin cuentas de usuario. El pago crea el trabajo; el resultado llega por email con enlace mágico (Resend).
- Preprocesado: recorte y fondo con rembg o la API de fondo de Tripo. Rechazar fotos de menos de 1.000 px y avisar antes de cobrar.
- Generación: API de Tripo, multi-imagen si hay más de una foto. Dos intentos por pedido, puntuados por ratio de la caja envolvente frente a las medidas introducidas; se entrega el mejor.
- Postprocesado: reescalado a las medidas, decimado a menos de 5 MB, GLB con Draco. USDZ lo genera `model-viewer` al vuelo en iOS, no hace falta pipeline propio.
- Entrega: página de resultado con `model-viewer`, botón "Ver en tu espacio", descarga GLB y USDZ, y botón "Repetir" gratis una vez. Cada repetición se registra como métrica.
- Analítica: PostHog o Plausible con cinco eventos: visita, subida, pago, descarga, repetición. Stripe como fuente de verdad de ingresos.
- Cumplimiento: casilla de permiso para usar el resultado en vídeos, aviso de contenido generado por IA (AI Act art. 50), metadatos de IA en el archivo.

### Día 3 · Prueba interna antes de lanzar
- 20 piezas reales en cuatro categorías: macizo mate, tapizado, metal o vidrio, patas finas. Cinco de cada.
- Si la aceptación propia baja del 40 %, no se lanza: el wrapper no ha movido la calidad lo suficiente y el test mediría solo el modelo de Tripo.
- Con las que salgan bien se graban los 10 primeros vídeos.

### Día 4 · Lanzamiento y automatización del canal
- Cada pedido con permiso genera un vídeo de 8 a 12 segundos (foto, giro del modelo, vista en el salón) con ffmpeg o Remotion.
- Programación automática en las tres redes con el scheduler ya conectado (Zernio). Dos publicaciones al día, sin intervención.
- Anuncios: 200–300 € en total, repartidos en los días 4 a 20, sobre el vídeo que mejor funcione de forma orgánica en los tres primeros días.

### Días 5–30 · Operación sin horas
- Revisión de 30 minutos el domingo: Stripe, PostHog, tickets. Nada más.
- Soporte: respuesta automática con las tres preguntas frecuentes y reembolso automático si el usuario marca "no me sirve". El reembolso también es métrica.
- Prohibido tocar producto, precio o canal hasta el día 30.

### Día 30 · Decisión
- Tabla con las seis métricas frente a sus umbrales. Fallan los tres primeros: se apaga el dominio y se archiva.
- Pasan los seis: fase 2 con la regla de contratación. Pasan tres o cuatro: una segunda ronda de 30 días cambiando una sola variable, nunca dos.

### Presupuesto
| Partida | Coste |
|---|---|
| Dominio | 10–15 € |
| Vercel, Resend, PostHog | 0–20 € |
| Créditos de API de Tripo para 60–100 generaciones | 30–60 $ |
| Anuncios | 200–300 € |
| Tus horas | 20–24 h en total, concentradas en el primer fin de semana |
| **Total en dinero** | **< 450 €** |

## Pipeline de calidad: validadores y vistas sintéticas

Orden de etapas y validador de cada una. Cada validador tiene un umbral y una acción (reintentar, cambiar de ruta o descartar). Coste orientativo por pieza con dos candidatos: 0,8–1,2 $.

| Etapa | Qué hace | Validador | Acción si falla |
|---|---|---|---|
| 1. Entrada | Fotos del usuario, medidas, descripción | Resolución ≥ 1.000 px, producto detectado, medidas coherentes (ratio de la foto frontal vs ancho/alto) | Pedir otra foto antes de cobrar |
| 2. Limpieza | Recorte, fondo neutro, luz normalizada | Máscara cubre > 90 % del objeto; sin recortes de patas | Reintentar con otro modelo de segmentación |
| 3. Vistas sintéticas (opcional, v2) | Modelo de imagen genera frontal, lateral, trasera y 3/4 ortográficas | Similitud con la foto original (VLM o CLIP) > umbral; silueta coherente entre vistas; proporciones de la silueta vs medidas | Reducir a 2 vistas o saltar a Tripo con la foto limpia |
| 4. Generación | Tripo multi-imagen, 2 candidatos | Malla cerrada, sin agujeros, sin componentes sueltos; caja envolvente reescalada coincide con medidas en los tres ejes con error < 3 % | Reintentar una vez; si repite, marcar "difícil" |
| 5. Render de control | Renderizar el modelo desde la cámara estimada de la foto original | Comparación con la foto (VLM juez o LPIPS); detectar patas fundidas, geometría inventada | Descartar candidato |
| 6. Postprocesado | Blender headless: remallado, decimado, UV, horneado, PBR, origen en la base, GLB con Draco | < 5 MB, ≤ 2K texturas, orientación correcta | Repetir con parámetros más agresivos |
| 7. Entrega | Visor y RA | Carga < 2 s en 4G | Reducir texturas |

Advertencia sobre la etapa 3: los generadores 3D ya hacen difusión multivista por dentro. Añadir un modelo de imagen antes añade una segunda capa de invención (la trasera y los laterales que la foto no muestra). Ayuda cuando el problema es la foto (fondo, luz, oclusión); perjudica cuando el problema es geometría que nadie ha visto. Por eso es v2 y solo entra si la prueba interna de 20 piezas muestra fallos de entrada, no de geometría.

### Blender: para qué sí y para qué no

| Uso | ¿Tiene sentido? | Nota |
|---|---|---|
| Postprocesado headless (`bpy`) | Sí, desde v1 | Es el estándar del sector y sustituye la última milla humana en lo mecánico |
| Generación paramétrica con Geometry Nodes | Sí, como segunda ruta | Mesas, estanterías, aparadores, encimeras, losas: medidas exactas, geometría perfecta, sin invención. Textura desde la foto. Cubre una parte grande del mobiliario rectilíneo y es lo único que garantiza escala |
| Ejecutar generadores abiertos dentro de Blender (TRELLIS.2, Hunyuan3D) | No en el test; quizá en fase 2 | Exige GPU de 24 GB (0,5–1 $/h en alquiler), latencia y mantenimiento. Hunyuan3D 2.x excluye la UE en su licencia; TRELLIS.2 es MIT |
| "Blender en lugar de Tripo" como generador desde fotos | No | Blender no genera desde imágenes; haría falta uno de los modelos anteriores igualmente |

Enrutado propuesto: si la pieza es rectilínea y el usuario da medidas, ruta paramétrica en Blender; si es orgánica (tapizados, curvas, diseño), ruta IA con Tripo. El clasificador puede ser un VLM con una pregunta.

## Paso previo · Prueba interna de calidad, sin comercios

Objetivo único: saber si el output es lo bastante bueno como para enseñárselo a alguien. Nada de captación ni de ventas. Plazo cerrado de 10 días.

1. **Control antes que pipeline.** Día 1: 10 piezas por la web de Tripo tal cual, sin nada vuestro. Es la línea base. El pipeline debe superarla de forma clara o no justifica existir.
2. **Muestra fija de 30 piezas** elegida antes de generar: fotos públicas de catálogos españoles, 7–8 por categoría (macizo mate, tapizado, metal o vidrio, patas finas), con medidas conocidas. No se cambia ninguna pieza después.
3. **Definición de "bueno", por escrito, día 1.** Rúbrica de 1 a 5 en cuatro ejes: parecido con la foto, geometría (sin agujeros, patas, trasera creíble), materiales, escala (error de caja envolvente < 3 %). Apto = 4 o más en los cuatro ejes sin retoque humano.
4. **Tres jueces a ciegas.** VLM con la rúbrica, tú sin ver la variante, y una tercera persona que no haya participado. Las puntuaciones se registran antes de revelar la variante.
5. **Resultado que se busca.** Tasa de aptos por variante y por categoría, coste y minutos por pieza. Pasa si alguna variante supera el 60 % de aptos en al menos dos categorías y mejora la línea base en más de 15 puntos.
6. **Arquitectura: un harness, N variantes.** El harness es único (muestra, rúbrica, jueces, métricas, informe). Cada enfoque es una variante que implementa la misma interfaz: recibe fotos y medidas, devuelve GLB. Variantes de la ronda 1, máximo seis:

   | Variante | Enfoque | Qué pregunta responde |
   |---|---|---|
   | A | Tripo directo, foto tal cual | Línea base |
   | B | Limpieza de foto → Tripo | ¿Cuánto aporta el preprocesado? |
   | C | Limpieza → vistas sintéticas → Tripo | ¿Las vistas inventadas ayudan o perjudican? |
   | D | Limpieza → Meshy | ¿Importa el proveedor del modelo? |
   | E | Paramétrico en Blender para rectilíneas | ¿La ruta sin IA gana en su categoría? |
   | F | Enrutado: E si rectilínea, B o C si orgánica | ¿El híbrido supera a cada ruta sola? |

   TRELLIS.2 o Hunyuan3D autoalojados quedan para la ronda 2 si alguna variante pasa y el coste por pieza importa. Postprocesado en Blender headless idéntico para todas.

   Cuidado con comparar seis variantes sobre 30 piezas: diferencias menores de 15 puntos de aptos son ruido. Solo cuenta una variante como ganadora si supera a la línea base por más de eso y lo hace en al menos dos categorías.

7. **Compromiso previo.** Si pasa, el siguiente paso es la Variante B (enviar a comercios y pedir pago), no otra ronda de pipeline. Si no pasa, se documenta qué falla y se decide si el problema es de entrada o de geometría; solo el primero justifica seguir.

## Variante B · Bake-off de pipelines con productos de clientes potenciales

Sustituye al test consumer cuando se quiere validar primero la calidad. Solo vale si termina con una petición de pago a los comercios cuyos productos se han usado; sin eso es un hobby técnico. Esta variante testea la hipótesis B2B (comerciante paga por modelos de su catálogo), no la consumer.

### Diseño
1. **Muestra**: 10 tiendas españolas de mueble o deco en WooCommerce o PrestaShop con 20–500 SKU. 3 productos por tienda, repartidos en las cuatro categorías de material (macizo mate, tapizado, metal o vidrio, patas finas). 30 piezas en total, con fotos y medidas públicas de la ficha.
2. **Variantes del pipeline, congeladas el día 1**:
   - A: foto limpia → Tripo directo, 2 candidatos.
   - B: foto limpia → vistas sintéticas → Tripo, 2 candidatos.
   - C: ruta paramétrica en Blender para las piezas rectilíneas, textura desde foto.
   - Todas pasan por los mismos validadores y el mismo postprocesado.
3. **Evaluación a ciegas**, tres jueces: un VLM con rúbrica fija, tú sin saber la variante, y el propio comercio en el paso 5. Puntuación de 1 a 5 en parecido, geometría, materiales y escala. Se registra tiempo y coste por pieza.
4. **Umbral técnico**: una variante gana si consigue ≥ 4/5 en más del 60 % de las piezas de su categoría sin retoque humano. Si ninguna lo consigue en tapizados y metal o vidrio, el producto se limita a macizo y rectilíneo, que es un mercado más pequeño y hay que aceptarlo.
5. **Cierre comercial obligatorio**: a cada tienda se le envía un enlace con sus 3 productos en el visor y en RA, y una sola pregunta: "¿pagaríais 290 € por tener así vuestros 20 productos más vendidos en la web, en 7 días?". Pago único, no cuota: lo que se mide es si el resultado vale dinero. Si dicen que sí, se les cobra y se producen.

### Umbrales de decisión
| Métrica | Umbral |
|---|---|
| Tiendas que responden al envío | ≥ 5 de 10 |
| Tiendas que aceptan pagar 290 € | ≥ 2 de 10 |
| Aceptación técnica sin retoque | > 60 % en al menos dos categorías |
| Horas humanas por pieza entregada, incluidas correcciones | < 15 min de media |

Dos tiendas pagando es el mismo criterio que fijaste en tu estudio previo (3 de 15), pero con el producto delante en vez de un piloto hipotético. Si ninguna paga con sus propios productos en RA en la mano, no hay nada que el plugin vaya a arreglar.

### Coste y plazo
| Partida | Valor |
|---|---|
| Generaciones: 30 piezas × 3 variantes × 2 candidatos | 180 generaciones, 40–130 $ |
| Modelo de imagen para vistas sintéticas | 30 × 4 vistas × 2, unos 10 $ |
| VLM juez | < 10 $ |
| Tus horas | 30–40 h en tres semanas: pipeline, variantes, evaluación, envíos |
| Plazo cerrado | 3 semanas. Las variantes no se tocan tras el día 1 |

### Riesgos propios de esta variante
- **Deriva técnica**: cada fallo invita a "una variante más". Por eso se congelan el día 1 y el plazo es cerrado.
- **Fotos de terceros**: usar fotos públicas para una demo que se envía al propietario es práctica habitual de outbound y de riesgo bajo; no publicar los modelos en ningún otro sitio.
- **Sesgo de selección**: elegir productos fáciles infla la aceptación. Las 30 piezas se eligen antes de generar nada y se reparten por categoría.

## Lo que el test no puede demostrar

- Que un comerciante pague por un plugin. Eso exige otro test con 10–15 entrevistas y una preventa.
- Que la calidad del modelo generalice a tapizados, vidrio y metal. Se verá en la tasa de repetición, pero no en qué falla.
- Que el canal siga abierto cuando Meshy o Tripo lo copien.
