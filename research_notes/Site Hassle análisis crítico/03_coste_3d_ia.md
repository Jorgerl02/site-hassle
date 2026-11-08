# Viabilidad técnica y coste unitario de generar modelos 3D "AR-ready" a escala real desde fotos de catálogo con IA (noviembre 2026)

Notas de investigación para el consultor que va a cuestionar la tesis de "Site Hassle" ("instala, elige productos y en ~30 min tienes modelos 3D realistas a escala con botón AR, generados por IA desde fotos + medidas del catálogo"). Todas las cifras llevan fecha de la fuente o del momento de consulta (8 nov 2026). Donde una cifra viene de un agregador o blog de proveedor, se señala.

Convención: USD salvo indicación. Meshy publica en EUR para cuentas europeas; se indica.

---

## P1. Estado del arte image-to-3D en 2026: precio por generación, calidad, fallos, licencias

### Takeaway
En nov 2026 la generación bruta de un modelo 3D con textura desde una imagen cuesta entre $0,10 y $0,50 por intento vía API (Tripo $0,20–0,30; Meshy ≈ €0,4–0,7 según plan; Rodin $0,25–0,80) y tarda 1,5–3,5 minutos; el modelo abierto más potente (TRELLIS.2, MIT, 4B parámetros) necesita una GPU de 24 GB y el otro gran modelo abierto (Hunyuan3D 2.1) tiene una licencia que **excluye expresamente la UE**. El coste marginal de computar es casi irrelevante; la barrera no es el precio sino la tasa de resultados aceptables en superficies pulidas/espejo, vidrio, partes finas y la cara posterior inventada, que todos los proveedores reconocen como fallos sistemáticos.

### Cited Findings

**Tabla resumen de proveedores (consultado 8-nov-2026)**

| Proveedor / modelo | Precio por generación (imagen→3D texturizado) | Salida | API | Licencia comercial | Fallos reconocidos / límites |
|---|---|---|---|---|---|
| **Meshy 7.1 / 6** | 20 créditos (Meshy 7.1 o 6), 25 créditos Ultra 2K/4K, 10 créditos Meshy 6 Lite; +10 créditos textura; Smart Topology 5 (T2) o 20 (T1); remesh 0 — [docs Meshy](https://docs.meshy.ai/en/webapp/pricing). Plan Pro €19/mes = 1.000 créditos ("hasta 100 assets"), 10 tareas concurrentes; Premium €38 = 3.000; Ultra €95 = 8.000 (100 concurrentes); Studio €67/mes + €9,5/asiento = 5.500 — [meshy.ai/pricing (EUR)](https://www.meshy.ai/pricing). ⇒ ≈ €0,019/crédito en Pro ⇒ **€0,38–0,48 geometría + €0,19 textura ≈ €0,6–0,7/modelo**. Benchmark externo: $0,20/llamada API Meshy 6 (abr–may 2026) — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show) | Malla + texturas PBR; 17.438 caras mediana en test — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show) | Sí en planes de pago — [meshy.ai/pricing](https://www.meshy.ai/pricing) | Free: CC BY 4.0 (comercial con atribución); planes de pago: licencia privada, el cliente es dueño del output — [docs Meshy](https://docs.meshy.ai/en/webapp/pricing) | "Se rompe en estructuras muy complejas; partes adyacentes se fusionan; el detalle fino se suaviza; superficies complejas desarrollan agujeros" — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show). Free bajó de 300→200 créditos (ago 2026) — [PricingSaaS](https://pricingsaas.com/companies/meshy/diffs/2026W31); hoy 100 — [docs](https://docs.meshy.ai/en/webapp/pricing) |
| **Tripo v3.1 (H3.1 / P2.0)** | API: 1 crédito = $0,01; image-to-3D 20–30 créditos (**$0,20–0,30**); multiview-to-3D 20–30; textura 10–30; retopología 10–40; conversión de formato 5–10; image-to-multiview 10 — [developers.tripo3d.ai](https://developers.tripo3d.ai/). Benchmark externo: $0,18/llamada — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show). Studio (no API): tier más alto subió de $110 a $330/mes en ago 2026 — [Costbench](https://costbench.com/changelog/tripo-ai-price-increase-2026-05/) | GLB, FBX, OBJ, USDZ — [developers.tripo3d.ai](https://developers.tripo3d.ai/); 13.482 caras mediana — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show) | Sí; "cuotas de concurrencia independientes por tipo de tarea" sin cifras — [developers.tripo3d.ai](https://developers.tripo3d.ai/) | ToS enlazados, no reproducidos (gap) | Mejor geometría "white mesh" del test (gana a Rodin 77,9 % single-view); separación de partes frecuentemente correcta — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show). El propio Tripo documenta fallo en cromo, metal pulido y vidrio ("texturas horneadas en vez de reflectancia real") — [Tripo blog](https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-and-reflective-surfaces-failure-cases) y en estructuras finas por escasez de datos y topología — [Tripo blog](https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-and-thin-structures-survival-strategies) |
| **Hyper3D Rodin Gen-2 / Gen-2.5** | Creator $30/mes ≈ 60 modelos ($0,50/modelo); Business $120/mes ≈ 416 modelos ($0,29/modelo); créditos directos $1,5/crédito; API solo en Business (120–240 RPM) — [hyper3d.ai/pricing](https://hyper3d.ai/pricing). Revendedores: $0,80/petición — [EmpirioLabs](https://empiriolabs.ai/models/hyper3d-gen2); $0,40–1,20 — [Runware](https://runware.ai/models/hyper3d-rodin-gen-2); $0,40 estándar / $0,80 Extreme-High — [WaveSpeed](https://wavespeed.ai/models/hyper3d/rodin-v2.5/image-to-3d). Benchmark: $0,25/llamada — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show) | "High-Poly Quads" en Business; 20.054 caras mediana — [hyper3d.ai/pricing](https://hyper3d.ai/pricing), [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show) | Solo Business — [hyper3d.ai/pricing](https://hyper3d.ai/pricing) | "Unlimited export and any use" en Creator; revisar términos — [hyper3d.ai/pricing](https://hyper3d.ai/pricing) | "Deslices estructurales": barril con lados redondeados en vez de duelas rectas, dedos mal contados; separación de partes inconsistente — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show) |
| **Tencent Hunyuan3D 2.1** (pesos abiertos, 13-jun-2025) | Coste = GPU propia: ~10 GB VRAM forma, ~21 GB textura, ~29 GB ambos — [GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) | Malla + PBR ("production-ready PBR material"); texturizado hasta 6 vistas — [GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) | Self-host | **Tencent Hunyuan 3D 2.1 Community License: el territorio excluye UE, Reino Unido y Corea del Sur ("DOES NOT APPLY")**; >1 M MAU requiere licencia aparte; prohibido usar outputs para entrenar otros modelos; obligaciones de aviso — [LICENSE](https://raw.githubusercontent.com/Tencent-Hunyuan/Hunyuan3D-2.1/main/LICENSE) | — |
| **Hunyuan3D 3.0** (sept 2025) | Acceso vía motor web y API Tencent Cloud; ~20 generaciones gratis/día (fuente terciaria) — [Pandaily](https://pandaily.com/tencent-unveils-hunyuan-3d-3-0-ai-model-tripling-modeling-accuracy-with-free-access), [ToolNavs](https://toolnavs.com/en/article/275-hunyuan-3-d-3-0-lai-xi-ai-san-bei-jing-du-yu-1-5-3-6-3-fen-bian-l-3-d-dit-zhong) | Geometría 1536³ (~3,6 G vóxeles) frente a 1024 en 2.5 — [ToolNavs](https://toolnavs.com/en/article/275-hunyuan-3-d-3-0-lai-xi-ai-san-bei-jing-du-yu-1-5-3-6-3-fen-bian-l-3-d-dit-zhong) | API Tencent Cloud — [Pandaily](https://pandaily.com/tencent-unveils-hunyuan-3d-3-0-ai-model-tripling-modeling-accuracy-with-free-access) | Open-source **no confirmado**; la versión abierta anunciada es Hunyuan3D-Omni (arXiv 25-sep-2025, construida sobre 2.1, acepta bounding boxes/point clouds/pose como control) — [arXiv](https://arxiv.org/abs/2509.21245v1) | Precios API no encontrados (gap) |
| **Microsoft TRELLIS.2-4B** (dic 2025, arXiv 2512.14692) | GPU propia: ≥24 GB VRAM (A100/H100), solo Linux; H100: 3 s a 512³, 17 s a 1024³, 60 s a 1536³ — [GitHub](https://github.com/microsoft/TRELLIS.2) | GLB con PBR (base color, roughness, metallic, opacity); el canal alfa no está activo por defecto en el GLB — [GitHub](https://github.com/microsoft/TRELLIS.2) | Self-host | **MIT** (dependencias nvdiffrast/nvdiffrec con licencia propia) — [GitHub](https://github.com/microsoft/TRELLIS.2) | Solo imagen única; instalación "con muchas dependencias" — [GitHub](https://github.com/microsoft/TRELLIS.2) |
| **Stability SPAR3D** (ene 2025, arXiv 2501.04689) | GPU propia: 10,5 GB VRAM por defecto (~7 GB low-VRAM) — [GitHub](https://github.com/Stability-AI/stable-point-aware-3d) | GLB, resolución de textura configurable, remesh tri/quad; no afirma PBR — [GitHub](https://github.com/Stability-AI/stable-point-aware-3d) | Self-host; pesos gated en HF | Licencia no verificada (gap) | Soporte Windows/Mac experimental — [GitHub](https://github.com/Stability-AI/stable-point-aware-3d) |
| **Kaedim** | Solo contratos enterprise a medida, sin precio público (verificado mar 2026); cifras de terceros ($149–500/mes; ~$20/crédito) poco fiables — [Costbench](https://costbench.pages.dev/software/ai-3d-generation/kaedim/), [TechShark](https://techshark.io/tools/kaedim/) | — | — | — | — |
| **CSM.ai** | Planes $20 / $60 / $499 / $2.000 al mes (agregador) — [Costbench](https://costbench.com/compare/csm-vs-meshy/) | — | — | — | Precio por crédito no encontrado (gap) |
| **Luma Genie** | Cifras contradictorias ($30/$90/$300 vs $9,99) — [Costbench](https://costbench.com/software/ai-3d-generation/luma-genie/), [Staquest](https://staquest.com/compare/csmai-vs-luma-genie) | — | — | — | (gap) |
| **Alpha3D** | $5–$162/mes por tiers (agregador) — [Costbench](https://www.costbench.com/software/ai-3d-generation/) | — | — | — | Precio por modelo no encontrado (gap) |
| **Apple Object Capture** | Fotogrametría en Mac/iPhone; requiere fotografiar el objeto físico — [Apple Quick Look](https://developer.apple.com/augmented-reality/quick-look/) | USDZ | — | — | No aplica a "fotos de catálogo" |

**Benchmark independiente más reciente (abr–may 2026, publicado 3-jun-2026; OJO: el autor trabaja en Meshy)**
- Tasa de éxito técnico image-to-3D: Meshy 6 100 %, Tripo v3.1 100 %, Rodin Gen-2.5 98 %; latencia mediana image-to-3D: Tripo 99 s, Rodin 190 s, Meshy 195 s — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show).
- "Éxito" = la API devolvió un modelo; el artículo **no reporta tasa de aceptabilidad** ni prueba simetría, partes finas, cara posterior ni fallos de textura — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show).
- Votación ciega: Tripo gana a Rodin 77,9 % en geometría single-view; Meshy gana a Rodin 83,9 % en texturizado single-view — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show).
- Estudio Step1X-3D (may 2025): Tripo v2.5 puntuó mejor en geometría que Meshy 4 (versiones ya superadas) — [okmiku](https://okmiku.com/blog/ai-3d-model-generator-meshy-tripo-meta-sam-2026).

**Fallos sistemáticos en mobiliario/decoración**
- "Maneja bien mobiliario mate y opaco y falla de forma predecible en vidrio, cromo y celosías finas" — [TinyHouse blog](https://www.tinyhouse.com/post/can-meshy-ai-help-turn-your-home-decor-ideas-into-3d-concepts) (blog, admite que hay poco testeo independiente para mobiliario).
- Cromo, metal pulido y vidrio producen "texturas horneadas incorrectas en vez de propiedades reflectantes reales" — [Tripo blog](https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-and-reflective-surfaces-failure-cases).
- Guía de QA: "si el objeto tiene patas, asas, agujeros, correas o partes finas, haz zoom ahí primero: buscas agujeros, geometría flotante, bordes fundidos y costuras de textura" — [Meshy blog](https://www.meshy.ai/blog/best-ai-tools-for-3d-printing).

### Inferences
- Para el caso Pietra by Bianca (travertino, piedra mate/porosa, formas macizas) la IA está en su mejor escenario: superficie opaca, geometría sólida, pocas partes finas. **Que funcione en travertino no demuestra que funcione en una silla de patas metálicas cromadas, una lámpara de vidrio o un sofá de tela con cojines.** Es un sesgo de muestra, no una prueba de pipeline generalizable.
- El coste de cómputo por SKU (≈ $0,2–0,7 por intento, $0,6–2 con 2–3 reintentos y post-proceso) es tan bajo que cualquier competidor lo iguala en una tarde con la misma API; no hay foso en "la IA barata". Si hay foso, estaría en los datos/heurísticas de QA y escala, no en la generación.
- Un pipeline europeo que use Hunyuan3D 2.1/Omni self-hosted estaría operando **fuera de licencia** (UE excluida). La alternativa abierta legalmente limpia es TRELLIS.2 (MIT), que exige GPU de 24 GB (coste de alquiler H100/A100 no investigado, gap).

### Gaps
- No se encontró la página oficial de precios de Tripo Studio (403) ni los ToS de la API; el precio por tarea sale de developers.tripo3d.ai, no del pricing web.
- Precio API oficial de Hunyuan3D 3.0 en Tencent Cloud y su licencia: no encontrados.
- Licencia exacta de SPAR3D (Stability Community License o no): no verificada en la fetch.
- Precio por crédito de CSM, Alpha3D, Kaedim: solo agregadores contradictorios.
- Ningún benchmark independiente mide "tasa de aceptabilidad para ficha de producto" en mobiliario; el único test cuantitativo (HackerNoon) lo firma un empleado de Meshy y no publica tamaño de muestra.

---

## P2. Escala métrica: ¿salen a escala real? ¿Qué hace falta para "true-to-scale"?

### Takeaway
Ningún generador image-to-3D produce escala métrica por sí mismo: una foto no contiene escala absoluta y los propios proveedores lo reconocen; "true-to-scale" se consigue con un paso determinista posterior (reescalar la bounding box a las dimensiones del catálogo), que depende de que el comerciante tenga medidas correctas y de que la geometría generada tenga las proporciones correctas (si la IA inventa la profundidad, el reescalado no lo corrige). No existe ningún benchmark independiente del error dimensional.

### Cited Findings
- "Una fotografía plana carece de datos de escala absoluta" — [Tripo](https://www.tripo3d.ai/ai-3d-home-design/image-to-3d-furniture-convert-catalog-images-accurately); "la escala real absoluta requiere mapeo manual de referencia" — [Tripo](https://www.tripo3d.ai/ai-3d-home-design/ai-3d-product-visualization-workflow-home-design); "los modelos generados por IA pueden no exportarse siempre a dimensiones reales exactas; usa las herramientas de medida y escalado del software destino tras importar" — [Tripo](https://www.tripo3d.ai/ai-3d-home-design/image-to-3d-furniture-conversion-for-e-commerce-product-pages).
- Un desarrollador de plugin (FORM3D, SketchUp) explica que si se especifican dimensiones en el prompt junto a la imagen "la generación las sigue; si no, se usa un tamaño típico del objeto", y admite que la importación a escala real "es algo hacia lo que estamos trabajando" — [SketchUp forum](https://forums.sketchup.com/t/how-do-you-bring-real-world-furniture-into-sketchup/339570?page=2).
- Hunyuan3D-Omni (sept 2025) añade control explícito por bounding box, point cloud, vóxeles y pose — [arXiv](https://arxiv.org/abs/2509.21245v1) — es el único modelo abierto que acepta una caja envolvente como condicionamiento (pero hereda la licencia 2.1 que excluye la UE, ver P1).
- Shopify exige "construir el modelo a escala real con las unidades correctas (metros)" y "centrar el origen en la base" — [Shopify Partners checklist](https://help.shopify.com/partners/resources/creating-3d-models/3d-model-standards-checklist).
- `<model-viewer>` permite `ar-scale="fixed"` para impedir que el usuario reescale el modelo en AR en los tres modos (WebXR, Scene Viewer, Quick Look) — [modelviewer.dev](https://modelviewer.dev/examples/augmentedreality/).
- USDZ almacena una unidad explícita; OBJ no, así que el tamaño "lo deduce el visor" y hay que comprobar la escala tras importar — [Innerscene](https://www.innerscene.com/tools/obj-to-usdz).
- Un actor de Apify ("Product Photo to 3D Model with Real-World Scale") y FurniMesh venden "dimensiones precisas" sin test independiente — [Apify](https://apify.com/toolsheder/photo-to-3d), [FurniMesh](https://next.webcatalog.io/en/apps/furnimesh).

### Inferences
- El paso "reescalar bbox a ancho×fondo×alto del catálogo" es trivial (un script con gltf-transform o trimesh) y lo haría cualquiera; no es diferencial.
- El error real no está en la escala global sino en las **proporciones internas**: el fondo de un sofá, el grosor de un tablero o la altura de patas se inventan a partir de una foto frontal. Reescalar a la caja del catálogo deja esas proporciones mal. Hace falta al menos una vista lateral o la foto de perfil, que muchos catálogos no tienen.
- Las medidas del catálogo son a menudo "ancho × alto × fondo" del producto embalado o con tolerancias; un error de 2–3 cm en una mesa auxiliar es irrelevante, pero en un sofá modular o un armario empotrado la promesa "sabrás si cabe" se rompe.

### Gaps
- No se encontró ningún benchmark con error dimensional medido (cm o %) de ningún generador en mobiliario.
- No se encontró documentación de que Meshy, Tripo o Rodin acepten dimensiones métricas como input en API (Tripo lista "advanced setup from 5 credits" sin detallar).

---

## P3. La "última milla" humana por modelo y su coste (QA, retopo, texturas, pivote, USDZ, decimación, PBR, sombras AR)

### Takeaway
La checklist de Shopify para un modelo aceptable en ficha de producto (≈4 MB, texturas ≤2K, mapas PBR separados, origen en la base, escala en metros, quads, UV manual, reflectividad correcta, sin huecos ni z-fighting) describe un trabajo que la IA no entrega hoy; el mercado humano cotiza ese trabajo entre $50–200 (Fiverr, GLB sencillo), $179+ (Sayduck), $210–265 (Augment) y $350+ (estudio), con plazos de días a 2–3 semanas, mientras que las tarifas freelance en España rondan 25–60 €/h. Ningún proveedor publica datos auditables de a cuánto reduce la IA ese coste; el único número ("–90 %") es marketing sin metodología.

### Cited Findings

**Qué exige una tienda (checklist de Shopify Partners, consultada 8-nov-2026)**
- Tamaño total ≈ 4 MB (algunos medios exigen menos); texturas JPG optimizadas, ≤2048×2048 para móvil; empezar en alta y comprimir — [Shopify Partners](https://help.shopify.com/partners/resources/creating-3d-models/3d-model-standards-checklist).
- PBR: mapa difuso + normal + un mapa combinado ORM (occlusion/roughness/metalness en R/G/B); un mapa por característica — [Shopify Partners](https://help.shopify.com/partners/resources/creating-3d-models/3d-model-standards-checklist).
- Escala real en metros, origen centrado en la base; geometría en quads, "evitar triangulación y decimación donde sea posible"; **UV desplegado a mano ("no usar herramientas automáticas")**, un solo set UV, sin solapes; un solo objeto y un solo material — [Shopify Partners](https://help.shopify.com/partners/resources/creating-3d-models/3d-model-standards-checklist).
- Calidad: igualar fotos en apariencia, proporciones y silueta; materiales que igualen reflectividad, brillo y transparencia; imperfecciones sutiles; sin polígonos negros, z-fighting, clipping ni huecos; probar en el dispositivo del comerciante — [Shopify Partners](https://help.shopify.com/partners/resources/creating-3d-models/3d-model-standards-checklist).
- Shopify acepta GLB y USDZ hasta 500 MB; >15 MB se optimiza automáticamente; <15 MB no se toca; siempre genera la versión USDZ y GLB — [Shopify Help](https://help.shopify.com/changelog/filter-product-media-by-media_type), [Shopify Partners](https://help.shopify.com/partners/resources/creating-3d-models/3d-model-standards-checklist). Error conocido: "Failed to convert model to USDZ format" con GLB muy comprimidos — [Shopify Community](https://community.shopify.com/t/why-am-i-getting-an-error-when-uploading-a-glb-file/36204).
- Apple Quick Look: un USDZ de 1,6 MB con texturas 4096² fue rechazado por "demasiado grande" porque el límite es memoria en el dispositivo, no tamaño en disco; no hay cifra publicada — [Apple Developer Forums](https://developer.apple.com/forums/thread/118710).

**Qué entrega la IA frente a eso**
- Output típico 13–20k caras trianguladas (no quads), texturas horneadas — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show); reflejos "horneados" en vez de PBR correcto en metal/vidrio — [Tripo blog](https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-and-reflective-surfaces-failure-cases); TRELLIS.2 exporta opacidad en el PNG pero el GLB sale OPAQUE y hay que conectarla a mano — [GitHub](https://github.com/microsoft/TRELLIS.2).
- Retopología/"Smart Topology" cuesta 5–20 créditos extra en Meshy y 10–40 en Tripo — [docs Meshy](https://docs.meshy.ai/en/webapp/pricing), [developers.tripo3d.ai](https://developers.tripo3d.ai/).

**Precios humanos de referencia (2025–2026)**

| Fuente | Precio por modelo | Plazo / condiciones | Fecha |
|---|---|---|---|
| Sayduck (servicio 3D, Shopify Plus partner) | "desde 179 USD para modelos muy simples"; 1 ronda de revisión incluida | "de días a 2–3 semanas" | pricing consultado nov 2026 — [Sayduck](https://www.sayduck.com/pricing), [llms.txt](https://www.sayduck.com/llms.txt); perfil Shopify "desde $199" — [Shopify Partners](https://www.shopify.com/plus/partners/sayduck) |
| Augment (agencia AR) | $265/modelo (lotes 11–50); $210 (50+) | — | [augment.com/pricing](https://www.augment.com/pricing/) |
| Estudio CGI (cgifurniture) | "desde $350" modelo AR/ecommerce optimizado con PBR | — | [cgifurniture](https://cgifurniture.com/3d-rendering-guide/ar-modeling-services) |
| Guías de mercado | $100–$1.000+/SKU, "la mayor partida del presupuesto" — [Framesixty](https://framesixty.com/ar-product-visualization/); $200–800/modelo, simples $200–400 — [MaverickFrame](https://maverickframe.com/blog/3d-product-rendering-cost/); Sketchfab: creación $40–1.000 según complejidad — [Sketchfab](https://sketchfab.com/blogs/enterprise/?p=8647) | — | 2025–2026 |
| Fiverr (gigs GLB/USDZ mobiliario) | $50–100 (3 días); $100–200 (10 días); hasta $50 (2 días); $400–600 (4 semanas); "máx $250 según complejidad" | — | [Fiverr 1](https://fiverr.com/mamun3dwork/provide-3d-product-glb-gltf-and-usdz-models), [Fiverr 2](https://fiverr.com/agniesleos/create-3d-models-in-glb-or-gltf-format-for-ar-purposes), [Fiverr 3](https://www.fiverr.com/pixelvibe3d/create-glb-3d-models-optimized-for-ar-web-and-realtime-use) |
| Freelancer.com (pujas offshore) | $15 simple / $30 medio / $40 complejo con optimización GLB; otra puja ₹1.500 / ₹3.500 / ₹6.500 (~$18 / $42 / $78) con entrega 1–5 días | — | [Freelancer](https://www.freelancer.com.au/projects/blender/photorealistic-furniture-modeling) |
| ARitize3D (app Shopify, pipeline semi-automático) | "$4 por SKU para modelos simples" | — | [Digismoothie](https://www.digismoothie.com/app/aritize3d) |
| Vendor IA (Rewarx) | "históricamente $300–1.200 por modelo de estudio"; "recorta costes un 90 %" — **sin metodología, marketing propio** | — | [Rewarx](https://www.rewarx.com/blogs/3d-product-visualization-mid-market-furniture) |

**Tarifas hora**
- España: principiante 15–25 €/h, junior 25–40 €/h, medio 40–60 €/h (Sevilla, sin fecha) — [Twine](https://www.twine.net/es/find/3d-designers/es/seville); rango genérico freelance 23–95 €/h, estudios 70–190 €/h — [laps4](https://www.laps4.com/preguntas-y-respuestas/cuanto-gana-un-modelador-3d-en-espana); salario base 3D Artist España 41.500 €/año — [Talentup](https://talentup.io/en/salary/3D%20Artist/Spain); media local Tarifa (Cádiz) 20 €/h — [Fixando](https://www.fixando.es/en/servicios-de-cad-y-modelado-3d/precio/Andaluc%C3%ADa/Tarifa).
- Offshore: las pujas de Freelancer ($15–78/modelo con 1–5 días de entrega) implican tarifas efectivas de ~$5–15/h — [Freelancer](https://www.freelancer.com.au/projects/blender/photorealistic-furniture-modeling).

### Inferences
- Tiempo humano estimado por SKU en un flujo "IA + QA/fix" (inferencia propia a partir de la checklist y los fallos documentados): abrir y revisar en visor (3–5 min), reescalar/pivote/orientación (2–3 min), decimar a <4 MB y redimensionar texturas (5 min), corregir material PBR (metalness/roughness erróneos: 5–15 min), tapar agujeros o re-generar (0–20 min), exportar GLB + comprobar USDZ en iPhone y Scene Viewer/WebXR en Android (5–10 min) ⇒ **20–60 min/SKU** en casos buenos; un rebuild manual de patas o partes finas sube a 1–3 h. A 30–45 €/h en España son **10–45 €/SKU**; offshore a 8–15 €/h, **3–15 €/SKU**.
- Lo que Shopify exige explícitamente ("UV a mano", "quads", "evitar decimación") es **incompatible por diseño** con el output de cualquier generador actual; en la práctica las tiendas aceptan modelos triangulados y con UV automática si *se ven bien*, pero esto significa que el criterio de aceptación es visual y subjetivo → necesita ojo humano.
- El "$4 por SKU" de ARitize3D (pipeline semi-automatizado ya en el mercado desde hace años) marca el suelo del precio al que un competidor ya vende; cualquier cuota mensual por producto de Site Hassle compite contra eso.

### Gaps
- Ningún proveedor de IA publica tasas de aceptación/rework ni tiempos de QA humano por SKU; los tiempos de la inferencia anterior son estimación.
- No se encontró el precio de Intervibe ni de Hexa; 3D Cloud no publica precios — [G2](https://g2.com/products/3d-cloud/pricing).
- "Shopify 3D partners $50–200/modelo (histórico)" no se pudo documentar con fuente primaria; la referencia más cercana es Sayduck ($179–199 "desde").

---

## P4. Multi-vista desde fotos de catálogo: ¿funciona con 1–4 fotos lifestyle/packshot? ¿"30 minutos sin esfuerzo del comerciante" es realista?

### Takeaway
Los modos multi-imagen exigen lo que un catálogo no suele tener: Meshy pide hasta 3 imágenes adicionales "consistentes en tamaño, ángulo y posición del sujeto" y solo en Meshy 7 (de pago); Tripo exige una vista frontal más al menos una lateral/trasera y recomienda eliminar fondos de todas las vistas. Generar es rápido (99–195 s por modelo, luego 30 min para una decena de productos es plausible en bruto), pero "sin esfuerzo del comerciante" solo es cierto si se acepta el modelo bruto sin QA, sin escala verificada y con la cara trasera inventada.

### Cited Findings
- Meshy Multi-View: "hasta 3 imágenes de referencia adicionales junto a la foto principal"; solo Meshy 7; "Meshy 6 y 6 Lite no soportan Multi-View"; función de pago; "requiere que todas las imágenes de referencia sean consistentes en tamaño, ángulo y posición del sujeto" — [Meshy Help](https://intercom.help/meshy/en/articles/12634481-how-to-use-multi-view).
- Tripo multiview: "la imagen frontal es obligatoria" y al menos una adicional izquierda/trasera/derecha — [RunComfy node](https://www.runcomfy.com/comfyui-nodes/ComfyUI/tripo-multiview-to-model-node); Tripo Studio acepta hasta 3 referencias y recomienda "eliminar fondos que distraigan de todas las vistas" — [Tripo blog](https://www.tripo3d.ai/blog/multi-view-reference-images-3d).
- Tripo API ofrece "image to multiview" (10 créditos) para sintetizar vistas antes de 3D — [developers.tripo3d.ai](https://developers.tripo3d.ai/).
- Hunyuan3D 2.1 texturiza con hasta 6 vistas (`max_num_view=6`) — [GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1).
- Latencia mediana image-to-3D: Tripo 99 s, Rodin 190 s, Meshy 195 s; text-to-3D 88–158 s — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show). Concurrencia: Meshy Pro 10 tareas, Ultra 100 — [meshy.ai/pricing](https://www.meshy.ai/pricing).
- En multi-view "white mesh", Tripo gana a Rodin 62,7 % y Rodin gana a Meshy 75 % — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show).
- Fallo de geometría oculta: "partes adyacentes se fusionan", "agujeros y regiones rotas" (Meshy 6); "deslices estructurales" (Rodin) — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show).

### Inferences
- Un catálogo típico (1 packshot frontal 3/4 + 1–3 lifestyle con iluminación y fondo distintos) **no cumple** el requisito de consistencia de Meshy ni el de "frontal + lateral limpios" de Tripo. El pipeline tendrá que (a) segmentar fondos automáticamente, (b) usar solo la mejor foto en single-image, o (c) sintetizar vistas con "image-to-multiview" — que inventa la trasera igual que el modo single-image.
- Por tanto, el input mínimo realista que el comerciante debe aportar es: 1 packshot frontal sobre fondo neutro, idealmente 1 lateral y 1 trasera a la misma distancia, más dimensiones A×F×H verificadas. Esto ya es "esfuerzo del comerciante" y para catálogos de cientos de SKUs es una sesión de fotos.
- "30 minutos" es realista como tiempo de *cola de generación* (10 productos × ~3 min con 10 tareas concurrentes), no como tiempo para tener modelos aceptables en la ficha: el QA humano (P3) multiplica ese tiempo por 10–20.

### Gaps
- No hay documentación pública de cómo se comportan los modos multi-imagen con iluminación/fondo inconsistentes (solo la advertencia de Meshy de que se exige consistencia).
- No se encontraron hilos de Reddit (r/3Dmodeling, r/Shopify) específicos de mobiliario con tasas de aceptación; la búsqueda solo devolvió blogs de proveedores.

---

## P5. Alternativas que hacen innecesario el 3D: composición 2D generativa ("pon este producto en mi foto")

### Takeaway
La composición 2D generativa cuesta $0,02–0,08 por imagen (Gemini 2.5 Flash Image $0,039, $0,0195 en batch; Flux Kontext pro $0,04) frente a $0,2–0,5 por modelo 3D + QA humano, no necesita malla, escala ni USDZ y resuelve la pregunta "¿cómo queda?"; pero no resuelve de forma fiable "¿cabe?" (escala métrica) ni permite rotar/caminar alrededor. Wayfair ya pivotó de su herramienta generativa (Decorify) a Muse y mantiene AR nativo; IKEA Kreativ y Amazon usan AR con escala real. El 2D erosiona la mitad "look" del valor del 3D, que es la que más convence al comprador medio.

### Cited Findings
- Gemini 2.5 Flash Image ("Nano Banana"): $0,039 por imagen 1024² (1.290 tokens de salida), $0,0195 en batch — [AnotherWrapper](https://anotherwrapper.com/tools/llm-pricing/image-models/gemini-25-flash-image-nano-banana), [MyArchitectAI](https://www.myarchitectai.com/blog/nano-banana-api-pricing). Sustituido como default de la app por Nano Banana 2 el 26-feb-2026; sigue en API a $0,039; Nano Banana 2 (Gemini 3.1 Flash Image) $0,045 (0,5K) – $0,151 (4K) — [Moda](https://moda.app/resources/models/nano-banana).
- Flux Kontext [pro] $0,04/imagen; [max] $0,08 — [bfl.ai/pricing](https://bfl.ai/pricing).
- Wayfair Decorify (2023): subes foto de tu espacio, eliges estilo y la IA generativa la rediseña y busca productos parecidos; "no es una app AR que te deje soltar representaciones CGI en tu habitación a través de la cámara" — [Wayfair](https://www.aboutwayfair.com/category/company-news/wayfair-launches-decorify-a-virtual-room-styler-powered-by-generative-ai), [RetailWire](https://retailwire.com/discussion/shop-virtually-with-wayfairs-generative-ai-decorify/). Versión Vision Pro con "objetos 3D a escala real anclados al suelo" — [Wayfair](https://www.aboutwayfair.com/category/company-news/wayfair-announces-decorify-app-for-apple-vision-pro). Decorify fue reemplazado por **Muse** en feb 2025 (con Google Lens) — [Textiles Review](https://textilesreview.pages.dev/wayfair-retools-its-consumer-ideation-experience-replacing-decorify-with-muse), [The Home Fashion](https://thehomefashion.in/wayfair-launches-muse-a-next-generation-ai-powered-home-design-tool).
- IKEA Kreativ: ARKit, escanea la habitación, borra muebles existentes, coloca productos IKEA y permite añadir al carrito — [TechCrunch](https://techcrunch.com/?p=2340297).
- Amazon "View in Your Room": AR desde 2017 (un objeto); "Room Decorator" varios objetos a escala simultáneamente; ampliado a objetos de sobremesa (lámparas, decoración, pequeños electrodomésticos) — [TechCrunch](https://techcrunch.com/?p=2035393), [Chain Store Age](https://chainstoreage.com/amazon-enhances-online-shopping-experience-ai-ar).
- Apps Shopify de composición 2D: "My Room Visualiser" promete colocar el producto "escalado a dimensiones reales para que parezca a tamaño real" — [Shopify App Store](https://apps.shopify.com/my-room-visualiser).
- Google Shopping: una fuente secundaria menciona "visualización AR para colocación de muebles" en la renovación de Shopping — [DigitalThriveAI](https://www.digitalthriveai.com/en-us/resources/ai-and-automation/google-unveils-ai-powered-google-shopping-overhaul/); **no se encontró fuente primaria** de un "see it in your space" generativo de Google.

### Inferences
- Coste por uso: 2D ≈ $0,02–0,08 por visualización (se paga cada vez que un cliente lo usa, escala con tráfico); 3D ≈ $0,5–50 por SKU una sola vez + CDN (se amortiza con el tráfico). Para tiendas pequeñas con pocas visitas por SKU, el 2D es más barato; para catálogos con mucho tráfico, el 3D.
- Para el comprador de mobiliario "medio" (¿pega con mi salón?), el 2D generativo con una foto del salón es suficiente y más "realista" (iluminación coherente generada) que un GLB con reflejos horneados en AR. Para "¿cabe en este hueco de 1,80 m?" el 2D es poco fiable salvo que se haga estimación de profundidad y escala, que los modelos generativos no garantizan.
- Esto encoge el mercado accesible de Site Hassle: su pitch mezcla dos "jobs" (look + fit) y el primero ya se resuelve por $0,04 sin 3D.

### Gaps
- Precio por imagen de OpenAI gpt-image (openai.com devolvió 403); Ideogram no investigado.
- No hay estudios comparativos de realismo percibido 2D generativo vs AR 3D en conversión de mobiliario (solo claims de proveedores).

---

## P6. Costes y restricciones de entrega: hosting/CDN, USDZ en iOS, model-viewer, Draco/KTX2, Scene Viewer en Android

### Takeaway
El stack de entrega es gratuito y estándar (`<model-viewer>` Apache-2.0 genera el USDZ al vuelo en iOS, Shopify convierte a USDZ automáticamente), pero en noviembre de 2026 el modo AR nativo de Android (Scene Viewer, dentro de la Google app) **se cierra al abrirse en las versiones 17.68–17.72 de la Google app** según múltiples reportes abiertos sin respuesta de Google; no hay anuncio oficial de deprecación, pero el botón "ver en tu casa" en Android depende hoy de WebXR en Chrome como primera opción. Textura (no geometría) domina el tamaño del archivo; Draco/Meshopt comprimen la malla y KTX2 reduce la memoria GPU, no el archivo.

### Cited Findings
- `<model-viewer>`: `ar-modes` = webxr (Chrome 83+ Android, HTTPS, `xr-spatial-tracking` en iframes), scene-viewer (app nativa Android), quick-look (iOS). **Si no hay `ios-src`, el USDZ se genera al pulsar el botón AR en iOS**; los USDZ autogenerados no soportan animación; `ar-scale="fixed"`; `ar-placement` floor/wall — [modelviewer.dev](https://modelviewer.dev/examples/augmentedreality/). Licencia Apache 2.0, Google 2018–2025 — [modelviewer.dev](https://modelviewer.dev/docs/index.html).
- **Scene Viewer roto (oct–nov 2026):** issue #1797 abierto 26-oct-2026: "Google keeps stopping" al lanzar `intent://arvr.google.com/scene-viewer/1.0`; funciona en Google app 17.62.10, falla en 17.68.24, 17.70.11 y 17.72.13 beta (Galaxy S21+, Pixel 9, Pixel 10 Pro XL); 7 participantes, **sin respuesta de Google**; sin mención de deprecación — [GitHub arcore-android-sdk #1797](https://github.com/google-ar/arcore-android-sdk/issues/1797). Issue #1795 (StackOverflowError en cada lanzamiento tras la primera sesión, Pixel 8a) — [#1795](https://github.com/google-ar/arcore-android-sdk/issues/1795); #1752 (feb 2026, crash en Pixel 8a/Android 16, arreglado en 17.5.x y recaído) — [#1752](https://github.com/google-ar/arcore-android-sdk/issues/1752).
- Un proyecto web migró Android a "WebXR en navegador primero, Scene Viewer como fallback" porque "Scene Viewer se cierra ~30 ms después de lanzarse en las builds actuales (17.68–17.72) con cualquier modelo" — [GitHub PR](https://github.com/great-art-portfolio/art-website/pull/58).
- El evento `ar-status` de model-viewer se dispara al lanzar el intent, así que un fallo dentro de Scene Viewer no se detecta — [model-viewer discussion](https://github.com/google/model-viewer/discussions/1866).
- Documentación oficial de Scene Viewer sigue publicada sin aviso de deprecación (Android 7.0+, Google Play Services for AR) — [Google ARCore docs](https://developers.google.com/ar/develop/scene-viewer?hl=pl).
- Apple AR Quick Look: USDZ y .reality; iOS 12+/iPadOS 12+/visionOS 1+; Apple Pay y CTA vía parámetros de fragmento URL (`#callToAction=...&price=...&allowsContentScaling=0`); elemento `<model>` inline en Safari visionOS 26 — [Apple](https://developer.apple.com/augmented-reality/quick-look/).
- Límite práctico en Quick Look es memoria, no tamaño: USDZ de 1,6 MB con texturas 4096² falló; se arregló bajando a 2048² — [Apple Dev Forums](https://developer.apple.com/forums/thread/118710).
- Herramientas Apple: un proveedor afirma que Apple retiró usdzconvert/USDPython y que Reality Converter es una app GUI solo macOS (afirmación de tercero) — [Apify](https://apify.com/sergeyfaraday/glb-to-usdz.md); Reality Composer Pro requiere macOS 26.5+ — [Apple](https://developer.apple.com/augmented-reality/tools/). Alternativa open-source: `usdzip` de OpenUSD; convertidores online gratuitos GLB→USDZ (Innerscene) — [Innerscene](https://www.innerscene.com/tools/glb-to-usdz).
- Shopify: acepta GLB/USDZ hasta 500 MB; >15 MB auto-optimiza; genera ambas versiones — [Shopify](https://help.shopify.com/changelog/filter-product-media-by-media_type).
- Compresión: "Draco comprime algo más pero decodifica más lento y necesita un decoder 10× mayor"; orden recomendado: reducir texturas → cuantizar → Meshopt/Draco; "las texturas normalmente dominan el tamaño"; **KTX2 cambia la huella en GPU, no el tamaño de archivo** (PNG 4 MB y WebP 200 KB de 2048² ocupan ambos ~22 MB de VRAM) — [Cinevva guide](https://app.cinevva.com/guides/optimize-glb-for-web). Un add-on vende "3–6× menos que el exportador de Blender" (testimonio) — [SuperHive](https://superhivemarket.com/products/glb-optimizer).
- Hosting de terceros como referencia de precio: Sketchfab licencia AR sin app desde $129/mes; Modelry plataforma 3D/AR $13/mes — [Sketchfab](https://sketchfab.com/blogs/enterprise/?p=8647).

### Inferences
- Con GLB de 3–5 MB, el coste de CDN es despreciable: 10.000 aperturas AR/mes × 4 MB = 40 GB ≈ unos pocos euros en cualquier CDN (inferencia; no se buscaron tarifas CDN específicas).
- El riesgo de plataforma real hoy es Android: si Site Hassle vende "botón AR" y en noviembre 2026 Scene Viewer se cierra en la Google app actual, la demo falla en la mitad del parque de móviles salvo que implementen WebXR como primera opción (lo que model-viewer permite, pero obliga a probar en dispositivos reales y a depender de Chrome).
- Generar USDZ no requiere un Mac si se usa la autoconversión de model-viewer o de Shopify, pero la calidad de materiales tras la conversión automática es justo lo que hay que revisar a mano (gap documentado por Shopify con el error de conversión).

### Gaps
- No existe comunicado oficial de Google sobre el futuro de Scene Viewer; solo issues abiertos. Estado a confirmar en el momento de la decisión.
- Tarifas concretas de CDN/hosting 3D y estado oficial de usdzconvert no verificados con fuente primaria.

---

## P7. Patentes, IP y restricciones de plataforma relevantes

### Takeaway
Existe litigio activo de patentes en EE. UU. precisamente contra la función "ver en mi habitación" de retailers de muebles (AR Design Innovations vs Ashley, Ethan Allen, La-Z-Boy, Rove Concepts, City Furniture, Walmart; y un caso 2025 con otras dos patentes), sin resoluciones públicas; en Europa el riesgo más concreto es de **licencia de modelo**: Hunyuan3D 2.1/Omni excluye la UE y Meshy Free exige atribución CC BY.

### Cited Findings
- AR Design Innovations (ARDI) demandó en 2020 a Ashley Furniture, Ethan Allen y La-Z-Boy por sus apps AR alegando infracción de la patente '572 (solicitada en oct 2003, adquirida por ARDI en abr 2020; ARDI no fabrica productos) — [Womble Bond Dickinson](https://www.womblebonddickinson.com/us/node/20164), [Mondaq](https://www.mondaq.com/unitedstates/intellectual-property/942614/augmented-realityvirtual-reality-litigation-update-ar-design-innovations-litigations).
- Demandas posteriores con la misma patente: Rove Concepts (jun 2023, E.D. Tex.) — [Ex Parte](https://ai-lab.exparte.com/case/dct/txed/2:23-cv-00037/doc/analysis/1); City Furniture "View in My Room" (S.D. Fla.) — [Ex Parte](https://ai-lab.exparte.com/case/dct/flsd/1:23-cv-20127/doc/analysis/1); Walmart (E.D. Tex.) — [Ex Parte](https://ai-lab.exparte.com/case/dct/txed/2:23-cv-00310/doc/analysis/1). Cuestión central: si "3D scene" cubre una vista AR con cámara real — [Ex Parte](https://ai-lab.exparte.com/case/dct/txed/2:23-cv-00037/doc/analysis/1).
- Caso 2025 (E.D. Tex., 2:25-cv-00677) con patentes '785 y '883 sobre prueba virtual y visualización de producto — [Ex Parte](https://ai-lab.exparte.com/case/dct/txed/2:25-cv-00677/doc/analysis/1).
- Licencia Hunyuan3D 2.1: no aplica en UE, UK ni Corea del Sur; >1 M MAU requiere licencia; outputs no pueden entrenar otros modelos; aviso obligatorio "Powered by…" opcional, pero hay que declarar que Tencent no está afiliado al servicio — [LICENSE](https://raw.githubusercontent.com/Tencent-Hunyuan/Hunyuan3D-2.1/main/LICENSE).
- Meshy Free: CC BY 4.0 (atribución obligatoria incluso en uso comercial); planes de pago: licencia privada — [docs Meshy](https://docs.meshy.ai/en/webapp/pricing).
- TRELLIS.2: MIT, pero nvdiffrast/nvdiffrec (NVIDIA) con licencia propia — [GitHub](https://github.com/microsoft/TRELLIS.2).
- Apple: el contenido de la galería Quick Look no puede reproducirse comercialmente sin consentimiento; AR Quick Look se integra con Apple Pay vía parámetros URL — [Apple](https://developer.apple.com/augmented-reality/quick-look/).

### Inferences
- Para un vendedor español el riesgo de patente estadounidense es bajo mientras venda a tiendas europeas, pero cualquier plan "global" con clientes en EE. UU. hereda el riesgo de la campaña ARDI, que ya ha apuntado a retailers medianos (Rove, City Furniture), no solo a gigantes.
- Si el pipeline "ya probado" de Site Hassle usa Hunyuan3D (el modelo abierto más popular en 2025 para PBR), está fuera de licencia en la UE; vale la pena preguntar qué modelo usa exactamente.
- Las imágenes del catálogo del comerciante son suyas o del fabricante; generar derivados 3D de productos de terceros (p. ej. un distribuidor que vende marcas) puede necesitar permiso del fabricante — no investigado (gap).

### Gaps
- Estado procesal actual de los casos ARDI (sentencias, acuerdos, claim construction): no encontrado.
- Patentes europeas sobre AR retail: no investigadas.
- Derechos sobre fotos de fabricante para generar derivados 3D: no investigado.

---

## Modelo de coste bottom-up por SKU (nov 2026): tres escenarios

### Takeaway
El coste de generación IA es ≈ $0,5–2 por SKU y no es un foso; la calidad aceptable sin humano solo es plausible en mobiliario macizo y mate (como el travertino de Pietra), y cae a un dígito en vidrio/cromo/tela/patas finas; con QA humano el coste sube a 10–45 €/SKU en España (3–15 € offshore) y el estudio tradicional sigue en $50–350/SKU. Las tasas de aceptabilidad y rework son **estimaciones propias** basadas en los fallos documentados: nadie publica cifras auditadas.

### Cited Findings (inputs del modelo, con fuente)
- Generación API: Tripo $0,20–0,30; Meshy ≈ €0,6–0,7 (Pro); Rodin $0,29–0,50 (suscripción) o $0,40–1,20 (revendedores) — [developers.tripo3d.ai](https://developers.tripo3d.ai/), [docs Meshy](https://docs.meshy.ai/en/webapp/pricing), [meshy.ai/pricing](https://www.meshy.ai/pricing), [hyper3d.ai/pricing](https://hyper3d.ai/pricing), [Runware](https://runware.ai/models/hyper3d-rodin-gen-2).
- Post-proceso IA: retopología 5–40 créditos ($0,05–0,40); textura 10–30 créditos; conversión 5–10 — [developers.tripo3d.ai](https://developers.tripo3d.ai/), [docs Meshy](https://docs.meshy.ai/en/webapp/pricing).
- Latencia 99–195 s por modelo — [HackerNoon](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show).
- Tarifas humanas: España 25–60 €/h — [Twine](https://www.twine.net/es/find/3d-designers/es/seville); offshore $15–78/modelo — [Freelancer](https://www.freelancer.com.au/projects/blender/photorealistic-furniture-modeling); Fiverr $50–200 — [Fiverr](https://fiverr.com/mamun3dwork/provide-3d-product-glb-gltf-and-usdz-models); Sayduck $179+ — [Sayduck](https://www.sayduck.com/pricing); Augment $210–265 — [Augment](https://www.augment.com/pricing/); estudio $350+ — [cgifurniture](https://cgifurniture.com/3d-rendering-guide/ar-modeling-services); ARitize3D $4/SKU — [Digismoothie](https://www.digismoothie.com/app/aritize3d).
- Requisitos de aceptación (4 MB, ≤2K, PBR, escala m, pivote en base) — [Shopify Partners](https://help.shopify.com/partners/resources/creating-3d-models/3d-model-standards-checklist).

**Tabla comparativa por SKU (nov 2026)**

| Escenario | Tiempo por SKU | Coste directo por SKU | Tasa de calidad aceptable (estimación) | Tasa de rework | Qué NO cubre |
|---|---|---|---|---|---|
| **A. IA 100 % automática** (1 foto + medidas → gen → reescalado bbox → decimado → GLB; USDZ autogenerado por model-viewer/Shopify) | Máquina: 2–4 min generación + <1 min post-proceso; con 10 concurrentes, 10 SKUs en ~5–10 min; **humano: 0** | $0,20–0,70 por intento (API); con media de 2 intentos + retopo/textura: **$0,6–2,0/SKU**; GPU propia (TRELLIS.2, 24 GB) coste marginal pero sin precio investigado | Inferencia a partir de los fallos documentados: **mobiliario macizo mate (piedra, madera maciza, cerámica): ~50–70 %** "publicable"; **tela/cojines: ~30–50 %**; **patas finas, metal cromado, vidrio, lámparas: ~10–25 %**. Ningún proveedor publica esta cifra | No hay rework: se regenera (cada reintento $0,2–0,7) o se descarta; el 30–80 % restante llega a la ficha con defectos (cara trasera inventada, reflejos horneados, agujeros) si no hay filtro humano | Proporciones internas (fondo) si solo hay frontal; PBR correcto en metal/vidrio; UV/quads que pide Shopify; comprobación en iPhone + Android real |
| **B. IA + QA/fix humano** (A + revisión visual, reescalado/pivote, corrección de materiales, decimado, test en dispositivos; rebuild parcial cuando falla) | **20–60 min** humano en casos buenos; 1–3 h si hay que remodelar patas/partes finas (estimación; ver P3) | IA $0,6–2 + humano: **España (30–45 €/h): 10–45 €/SKU** típico, 45–135 € con rebuild; **offshore (8–15 €/h): 3–15 €/SKU**, 10–45 € con rebuild. Referencia de mercado: ARitize3D vende a $4/SKU "simple" — [Digismoothie](https://www.digismoothie.com/app/aritize3d) | **~80–90 %** aceptable tras fix (estimación); el 10–20 % restante requiere modelado manual (→ escenario C) | 10–20 % de SKUs pasan a rebuild completo; 1 ronda de revisión con el comerciante es estándar en el sector (Sayduck incluye 1) — [Sayduck](https://www.sayduck.com/pricing) | Catálogos con muchas variantes de acabado (cada acabado reflectante es un retexturizado manual); productos con transparencia |
| **C. Estudio / freelance tradicional** (modelado desde fotos + planos, PBR, UV manual, optimización web) | **2–6 h** por modelo sencillo-medio (inferencia desde tarifas hora y precios por modelo); plazo de entrega días a 2–3 semanas — [Sayduck](https://www.sayduck.com/pricing) | **Fiverr $50–200** (simple) / $400–600 complejo — [Fiverr](https://fiverr.com/agniesleos/create-3d-models-in-glb-or-gltf-format-for-ar-purposes); **Sayduck desde $179**; **Augment $210–265**; **estudio desde $350**; rango sector $100–1.000+ — [Framesixty](https://framesixty.com/ar-product-visualization/); **España freelance 40–60 €/h × 3–6 h = 120–360 €**; **offshore $15–78/modelo** — [Freelancer](https://www.freelancer.com.au/projects/blender/photorealistic-furniture-modeling) | **≥95 %** con 1 ronda de revisión (estándar del sector; inferencia) | 1 ronda incluida; extras de pago — [Sayduck](https://www.sayduck.com/pricing) | Velocidad (días/semanas, no minutos) y coste para catálogos de cientos de SKUs |

### Inferences
- El único número del pitch que la IA cambia de verdad es el escenario A: de $100–350 a <$2 por SKU. Pero A solo es vendible sin vergüenza en la categoría donde Site Hassle hizo su prueba (piedra maciza). En el resto del mobiliario, el producto real es B, cuyo coste está dominado por **minutos humanos**, no por créditos de IA, y ahí el precio de referencia ya lo marcan ARitize3D ($4/SKU) y los freelancers offshore ($15–40/modelo). Una cuota mensual por número de productos debe compararse contra "pago único de $4–40 por SKU".
- La escalabilidad a catálogos arbitrarios es la pregunta correcta: el coste de IA escala linealmente y barato; el QA humano escala linealmente y caro; y la tasa de aceptabilidad **cae** al salir de "macizo y mate". El foso, si existe, sería un clasificador que predice qué SKUs van a salir bien y un flujo de QA eficiente, no "la IA".
- Pregunta concreta para el emprendedor: en Pietra by Bianca, ¿cuántos SKUs se intentaron, cuántos se publicaron sin tocar, cuántos minutos humanos llevó cada uno y qué modelo (y licencia) usa el pipeline? Sin esos cuatro datos la frase "ya probado" no es verificable.

### Gaps
- Tasas de aceptabilidad y rework: **estimaciones propias**; no hay datos publicados por ningún proveedor ni estudio independiente sobre mobiliario.
- Precio de alquiler GPU para self-host de TRELLIS.2 y coste CDN no investigados; afectan poco al total (centavos por SKU) pero quedan sin cifra.
