# Generadores IA image-to-3D / text-to-3D: modelos de negocio, precios y UX (Tripo, Meshy, Kaedim, CSM, Luma Genie, Hyper3D Rodin, Sloyd, 3D AI Studio, Alpha3D, TRELLIS/Hunyuan3D hosteados)

Fecha de investigación: 2026-11-09. Precios en USD salvo indicación. Cuando la página oficial no era accesible (Tripo 403, Kaedim /pricing 404, csm.ai sin DNS, alpha3d.io vacía) se usan agregadores (CostBench, con fecha de verificación) y se marca como tal. Las conversiones crédito→USD son cálculo propio a partir de las cifras citadas.

## Fichas por producto (lanzamiento, cliente objetivo, precios, financiación, QC, formatos, UX, quejas)

### Takeaway
El mercado se divide en tres modelos: (1) SaaS autoservicio por créditos a ~$0,10–0,70 por modelo texturizado (Tripo, Meshy, 3D AI Studio, Sloyd, CSM, Rodin), sin garantía de calidad y con "reintentos gratis" como único colchón; (2) human-in-the-loop enterprise a ~$400 por asset (Kaedim); (3) APIs hosteadas de modelos abiertos a $0,02–0,53 por generación (TRELLIS, Hunyuan3D, Tripo en fal/Replicate). Ninguno de los diez vende "modelos de mobiliario a escala real para fichas de producto" como función definida.

### Cited Findings

**Tripo (tripo3d.ai, de VAST, Pekín)**
- Planes (CostBench, verificado 20-oct-2026; Pro/Max/Team re-verificados 5-nov-2026): Free $0 / 200 créditos (~13 modelos, 1 tarea concurrente); Pro $20/mes o $240/año / 3.000 créditos (~200 modelos); Max $90/mes o $1.080/año / 25.000 créditos (~1.660 modelos); Team $110/usuario/mes ($55 anual) / 90.000 créditos; el plan Free es no comercial (CC BY 4.0), hasta 15 descargas/mes y almacenamiento de 10 modelos; "coste oculto" marcado: dificultades de cancelación — [CostBench Tripo](https://www.costbench.com/software/ai-3d-generation/tripo-ai/)
- Conflicto en créditos gratis: varias fuentes dicen 300 créditos/mes en Free y Pro a $19,90/mes con 3.000 créditos; una fuente da 600 (probablemente obsoleta) — [WebSearch agregado; p. ej. CostBench hidden costs](https://costbench.com/software/ai-3d-generation/tripo-ai/hidden-costs/)
- Consumo en la web app (review Unite.AI, publicada 21-nov-2025, actualizada 30-mar-2026): generar modelo 35 créditos, generar textura 10 créditos; refine/rig/export sin cifra publicada; se puede "acelerar la generación gastando créditos adicionales" sin cantidad especificada — [Unite.AI](https://www.unite.ai/tripo-review)
- Otra tabla (cutout.pro, sin fecha fiable) lista Refine 30 créditos, Rigging 25, Export 5 — [cutout.pro vía WebSearch](https://www.cutout.pro/learn/?p=751)
- API oficial (developers.tripo3d.ai): "1 credit = $0.01 USD"; Text to 3D 10–20 créditos; Image to 3D 20–30; Multiview to 3D 20–30; Texture 10–30; Format Convert 5–10; Retopology 10–40; Segmentation & Completion 30–50; Auto Rig 25; formatos "GLB, FBX, OBJ, USDZ and other mainstream formats" — [Tripo Developers](https://developers.tripo3d.ai/)
- En fal.ai (tripo3d/tripo/v2.5/image-to-3d): $0,20 sin texturas, $0,30 texturas estándar, $0,40 HD; estilo y quad +$0,05 cada uno; GLB por defecto, FBX en modo quad; PBR incluido; parámetro `auto_size` "for meter-based scaling" — [fal.ai Tripo v2.5](https://fal.ai/models/tripo3d/tripo/v2.5/image-to-3d)
- Enterprise: packs de 500.000 / 1M / 2M créditos como compra única en AWS Marketplace — [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-hwlbvx7vubh7c)
- Financiación 2026: Serie A $50M (25-mar-2026); ~$200M (1-jun-2026, unicornio, liderada por Ince Capital); Serie B y B+ ~$446M (1-sep-2026, Matrix Partners China según InvestGame / MPCi según DealStreetAsia); total divulgado ~$846M; Bloomberg informa planes de IPO en Hong Kong — [AI Weekly](https://aiweekly.co/alerts/tripo-ai-hits-10m-users-as-vast-raises-200m); [InvestGame](https://investgame.net/news/matrix-partners-china-has-led-a-446m-series-b-and-b-into-vast-maker-of-tripo-ai-in-its-fourth-round-of-2026/); [DealStreetAsia](https://www.dealstreetasia.com/stories/tripo-ai-series-b-rounds-493956); [The Standard HK](https://www.thestandard.com.hk/finance/article/339006/Alibaba-Baidu-backed-3D-modeling-startup-Vast-plans-Hong-Kong-IPO-Bloomberg-reports)
- Usuarios: ~10M individuales y ~90.000 estudios/empresas (jun-2026); 20M+ según cobertura de Bloomberg; Tripo declara 6,5M+ creadores y 700+ clientes industriales — [AI Weekly](https://aiweekly.co/alerts/tripo-ai-hits-10m-users-as-vast-raises-200m); [IBTimes](https://www.ibtimes.co.uk/vast-beijing-startup-3d-models-ai-1800193)
- Trustpilot: 4,3–4,5 sobre 513 reseñas (12 % de 1 estrella); quejas: "Not much control over the output in the program itself" (18-may-2026), topología "still not perfect", hay que reintentar, gestión de créditos frustrante; la empresa no responde a reseñas negativas — [Trustpilot Tripo](https://www.trustpilot.com/review/tripo3d.ai?page=5)
- UX: Tripo Studio ofrece "One-click" (modelo texturizado completo) o "Build & Refine"; retexturizado por partes segmentadas; reseñas G2: UI "remarkably clean" pero un usuario pide un asistente tipo walkthrough y dice que se gastan créditos "without necessarily knowing what to expect from the outcome"; en Free no se pueden descargar modelos — [G2 Tripo Studio](https://www.g2.com/products/tripo-studio/reviews); [chatgate.ai](https://chatgate.ai/post/tripo-studio)
- Quejas top (CostBench/ToolRadar): imperfecciones del modelo y control de calidad, necesidad de postprocesado, límites del free tier y "complicated pricing", personalización limitada, más apto para borradores — [ToolRadar](https://toolradar.com/compare/tripo-ai-vs-meshy); [CostBench Meshy vs Tripo](https://www.costbench.com/compare/meshy-vs-tripo-ai/)

**Meshy (meshy.ai)**
- Planes (página oficial en EUR, 2026-11): Free €0 / 100 créditos / hasta 10 assets / 1 tarea concurrente / sin reintentos gratis; Pro €19 / 1.000 créditos / hasta 100 assets / 4 reintentos gratis por tarea; Premium €38 / 3.000 / 12 reintentos; Ultra €95 / 8.000 / 40 reintentos; Studio €67 (5.500 créditos compartidos, €9,5/asiento); Enterprise custom; 50 % dto. primer mes; Free = CC BY 4.0 (comercial con atribución), de pago = "Private & Customer owned"; descargas .fbx .obj .usdz .glb .stl .blend — [Meshy Pricing](https://www.meshy.ai/pricing)
- Mismos planes en USD (CostBench): Pro $20 / 1.000; Premium $40 / 3.000; Studio $70 / 4.000; Ultra $100 / 10.000 — [CostBench Meshy vs Tripo](https://www.costbench.com/compare/meshy-vs-tripo-ai/); StackSheriff (27-abr-2026): Pro $20/mes o $16 anual — [StackSheriff](https://stacksheriff.com/ai-tools/meshy-ai-pricing/)
- Créditos web app (docs oficiales): Text to 3D 20 (Meshy 6) / 10 (6 Lite); Image to 3D 20 (Meshy 7.1 o 6), 25 con Ultra 2K/4K, 10 con 6 Lite; Retexture 10 (15 a 8K); Remesh 0; Rigging 0; Animación 0 por clip; Smart Topology 5–20; fallos no se cobran, cancelaciones se reembolsan — [Meshy docs webapp pricing](https://docs.meshy.ai/en/webapp/pricing)
- Créditos API (docs oficiales): Text-to-3D preview 20 (meshy-7.1/6) o 5 (lite/t2); refine 10 (2K/4K) o 15 (8K); Image-to-3D meshy-7.1: 20 solo malla / 30 2K / 30 4K / 35 8K; Retexture 10/15; Remesh 5; Rigging 5; sin precio USD por crédito publicado; "contact sales" para volumen — [Meshy API pricing](https://docs.meshy.ai/en/api/pricing); [meshy.ai/api](https://www.meshy.ai/api)
- Límites API: 20 RPS (Pro–Studio), 100 RPS Enterprise; retención de assets API 3 días (planes normales), 14 días Studio, indefinida Enterprise; SLA 99,9 %, ISO 27001, SOC 2 Type II — [meshy.ai/api](https://www.meshy.ai/api)
- Financiación: Serie B ~$400M (jul-2026) a valoración $1.500M, liderada por IDG Capital, Matrix Partners China y Monolith; fundada 2021 por Ethan (Yuanming) Hu — [Silicon Valley Investclub](https://siliconvalleyinvestclub.com/2026/07/23/meshy-raises-400-million-at-a-1-5-billion-valuation/); [AlphaMaven](https://alpha-maven.com/news/venture-capital/meshy-scoops-up-400m-at-15b-valuation)
- Tracción (declarada por la empresa, no auditada): ARR $15M (nov-2025) → $30M (mar-2026) → >$40M (abr-2026) → >$100M (sep-2026); usuarios registrados 6M (nov-2025) → 12M+ (jul-2026) → 15M+ (sep-2026); Owler estima ingresos de solo $5,5M (conflicto) — [aiidelist](https://aiidelist.com/blog/meshy-100m-arr-ai-3d.md); [VIR](https://vir.com.vn/meshy-unveils-ai-gaming-platform-reaches-30-million-arr-148141.html); [multiples.vc](https://multiples.vc/private-comps/meshy-ai)
- Quejas: resultados image-to-3D irregulares, topología, low-poly inmaduro; un usuario de r/unity: "ai doesn't know what a hard surface is"; malla demasiado densa para móvil (43k triángulos); quejas de facturación/reembolsos; la API tiene opción autoSize para "estimate real-world scale", y una guía advierte que un prop de 1 m puede importarse a 100 m en el motor — [Techraisal](https://www.techraisal.com/blog/meshy-ai-pros-cons-pricing-reviews); [Sorceress blog](https://sorceress.games/blog/mesh-meshy-ai-image-to-3d-textured-glb); [Meshy docs text-to-3D](https://docs.meshy.ai/hi/webapp/text-to-3d)
- Calidad comparada (HackerNoon, may-2026): Tripo v3.1 gana en geometría de malla blanca; Meshy 6 gana en textura con entrada multivista — [HackerNoon](https://hackernoon.com/lang/so/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show)

**Kaedim (kaedim3d.com) — human-in-the-loop**
- Posicionamiento: "The platform for high quality 3D production at scale"; verticales Product design, Games y "E-commerce & Marketing: Create CGI without the shoot"; "Make unlimited revisions. Your asset, your call."; "Your desired output, back to you in hours"; logos Amazon, EA, Rebellion, Newell Brands, CBS; casos: Lowe's 75 % tiempo ahorrado y 14x más assets, Shark Ninja $600K/año, Casio 6,4x más rápido — [Kaedim home](https://www.kaedim3d.com/)
- Pipeline (docs oficiales): hasta 10 imágenes → preprocesado → reconstrucción 2D→3D → "Our art team verifies and cleans all outputs", lo que "guarantees users get a production-ready 3D model, every time"; "10x speedup compared to traditional art outsourcing"; formatos OBJ, OBJ (pre-modifiers), FBX, MTL, USD, GLB, GLTF; "Currently, we're primarily focusing on enterprise customers" — [Kaedim docs](https://docs.kaedim3d.com/welcome/how-kaedim-works)
- Precios (CostBench, verificado 27-sep/28-oct-2026; la página oficial /pricing devuelve 404): Trial $50 pago único / 5 créditos / 7 días (auto-renueva a Indie); Indie $400/mes / 20 créditos = "up to 20 geometries or 1 complete asset" / exceso $22/crédito; Pro $1.200/mes / 60 créditos = "up to 60 geometries or 3 complete assets" / exceso $16/crédito; Enterprise 100+ créditos, cotización — [CostBench Kaedim](https://costbench.com/software/ai-3d-generation/kaedim/)
- Otra página de CostBench da tiers distintos (Starter $149, Studio $500, abr-2026) y varios agregadores dicen que ya solo hay contratos custom con piloto de 1–3 assets: datos inconsistentes — [WebSearch; aitoolsatlas](https://aitoolsatlas.ai/tools/kaedim-3d/pricing)
- Investigación 404 Media (sep-2023): artistas humanos pagados "$1 to $4 per model", 15 minutos por envío, a veces modelando "from scratch" sin IA; Kaedim actualizó su web para reconocer el papel de los artistas — [TechSpot](https://www.techspot.com/news/100076-startup-ai-made-3d-models-2d-art-actually.html); [Fabbaloo](https://fabbaloo.com/news/ai-startup-exposed-the-use-of-humans-in-3d-model-generation); [Gigazine](https://gigazine.net/gsc_news/en/20230907-kaedim-generating-ai-3d-model-human-labor/)
- Financiación: pre-seed dic-2020; Serie A $15M liderada por a16z Games (mar-2024); Clay dice $10M y Caplight $16M (conflicto) — [GamesBeat](https://gamesbeat.com/kaedim-raises-15m-to-fund-ai-based-3d-asset-creation-solutions/); [UKTechNews](https://www.uktechnews.info/?p=6138)
- Lanzamiento: web app cubierta por CG Channel en agosto de 2022 — [CG Channel](https://www.cgchannel.com/2022/08/ai-based-web-app-kaedim-turns-2d-concepts-into-3d-assets/)

**CSM — Common Sense Machines (csm.ai)**
- Planes (CostBench, "verificado" 30-may-2026 pero marcado 40 % confianza/no re-verificado; www.csm.ai no resolvía DNS el 2026-11-09): Tinkerer gratis / 10 créditos únicos / glTF, OBJ, FBX / CC BY 4.0; Maker $20/mes / ~100 créditos / licencia comercial; Creative Pro $60/mes / ~400 créditos; Startup $499/mes / API; Studio $2.000/mes / API completa, Slack; Enterprise custom — [CostBench CSM](https://www.costbench.com/software/ai-3d-generation/csm/)
- Sloyd estima ~1 crédito por modelo en el plan de $20 → ~$200 por 1.000 generaciones — [Sloyd price comparison](https://sloyd.ai/blog/3d-ai-price-comparison)
- Quejas: "Implementation can be lengthy, potentially taking months", configuración compleja — [CostBench CSM](https://www.costbench.com/software/ai-3d-generation/csm/)
- Financiación: $2,5M (VCBacked) vs $7,6M en dos rondas (Seedtable); inversores Toyota Ventures, Glasswing, Intel Capital — [VCBacked](https://www.vcbacked.co/company/common-sense-machines); [Seedtable](https://seedtable.com/startups/Common_Sense_Machines,_Inc.-4NMAWJ3)

**Luma Genie (lumalabs.ai)**
- Lanzado el 1-nov-2023 como research preview gratuito en Discord ("Free during research preview"); 100.000 usuarios en 4 semanas; Luma levantó $43M Serie B (a16z) en ene-2024 a valoración $200–300M — [TechCrunch](https://techcrunch.com/2024/01/09/luma-raises-43m-to-build-ai-that-crafts-3d-models/)
- Estado 2026: la página standalone de Genie "now redirects into Luma's main platform"; precio de Genie "no longer published separately"; planes de Luma ~$30/$90/$300 al mes; free con topes diarios y marca de agua — [godofprompt](https://godofprompt.ai/tools/luma-genie)
- Un directorio lista el modelo API "genie-3d" con fecha "Released 2025-08-05", limitado al tier Pro (actualizado abr-2026) — [LLM Reference](https://www.llmreference.com/model/genie-3d)
- La página lumalabs.ai/genie actual no menciona Genie — [Luma](https://lumalabs.ai/genie)

**Hyper3D Rodin (hyper3d.ai, de Deemos)**
- Página oficial: Free $0 "Pay per result" — previsualizas y "only spend credits when you confirm one"; créditos directos $1,50 cada uno; 10 assets privados; Creator $30/mes ($24 anual, $288) "~60 models", redos 20 geometría / 6 materiales; Business $120/mes ($96 anual, $1.152) "~416 models", API completa, 120 rpm (240 en tiers altos), redos 50/15, High-Poly Quads; Enterprise con "AI+Artist support for near-production-ready assets", on-premise, LoRA custom; la página mostraba "Prices can't be shown right now" y precios tachados — [Hyper3D pricing](https://hyper3d.ai/pricing)
- CostBench (verificado 5-nov-2026): Free con 10 créditos iniciales sin renovación; créditos se gastan en la descarga, no en la generación; una fuente (baja confianza) reporta ~40 créditos por descarga de modelo Gen-2 v2; "Geometry refinement and part decomposition" descritos como "quite expensive" con ~1 día de espera; contratos auto-renovables sin cancelación intra-periodo — [CostBench Rodin](https://costbench.com/software/ai-3d-generation/rodin-hyper3d/)
- API vía WaveSpeed (Rodin v2.5): $0,40 por generación base, HighPack +$0,80 — [WaveSpeed Rodin](https://wavespeed.ai/models/hyper3d/rodin-v2.5/image-to-3d)
- Picassoia señala que la aritmética no cuadra: 20–35 créditos × $1,50 = $30–52 por modelo frente a ~$0,50/modelo en suscripción — [Picassoia](https://blog.picassoia.com/rodin-gen-2-5-hyper3d-image-to-3d-pricing-and-quality)

**Sloyd (sloyd.ai, Oslo)**
- Planes oficiales: Guest $0 / 1 generación IA al día / GLB-OBJ / uso personal; Plus $15/mes ($12,50 anual) / "Unlimited core generation" (text & image to 3D, retexturizado 4K, rigging, skybox) + 50 créditos / 2 generaciones paralelas / uso comercial sin reventa; Pro $50/mes ($41,67 anual) / 350 créditos / 5 paralelas / reventa; top-up $12 = 100 créditos; créditos solo para extras: Split to parts 20, Multi-image to 3D 20, Ultra high 500K tris 5, Image to Scene 30; plugins Unity/Unreal/Blender; formatos GLB, OBJ, FBX — [Sloyd pricing](https://www.sloyd.ai/pricing)
- API oficial (prepago): "USD 1 = 75 API credits"; trial $12 = 900 créditos; image-to-3D geometría 10 créditos, +10 textura, +5 texto, +10 multi-imagen, +5 quads, +10 ≥500K polys; text-to-3D ejemplo 25 créditos; retexture 15; split to parts 40 — [Sloyd API pricing](https://www.sloyd.ai/api/pricing)
- Fundada en Oslo en 2021 (Andreas Edesberg, Avi Latner); seed €3M / $3,2M (jun-2024) con Autodesk, a16z Games Speedrun, Antler — [cavacopedia draft](https://cavac.at/cavacopedia/Draft%3ASloyd%20AI); [startupintros](https://startupintros.com/news/2024-06-11-sloyd-seed); [FinSMEs](https://finsmes.com/?p=320206)

**3D AI Studio (3daistudio.com) — agregador de modelos (Meshy, Rodin, Tripo…)**
- Página oficial: Basic 1.000 créditos/mes (hasta 100 assets); Studio 3.500 créditos (hasta 600 assets, multi-imagen); Pro 18.000 créditos (hasta 3.500 assets, 3 asientos); precios mensuales ilegibles en el scrape, anual -40 %; packs únicos sin caducidad: $34 / 2.000 créditos, $69 / 5.000, $399 / 35.000; Image to 3D 20 créditos; Text to 3D 20; Refine 5; Rigging 20; Animation 15; Texture AI, Remesh y LOD gratis; free credits al registrarse (cantidad no indicada); formatos GLB, OBJ, FBX, STL, USDZ, PLY; uso comercial en todos los planes; 7 días de devolución — [3D AI Studio pricing](https://www.3daistudio.com/pricing)
- Su propio blog dice "Free tier; paid from ~$9.99/mo", "1 Million+ users", exporta GLB y USDZ con PBR — [3D AI Studio blog](https://www.3daistudio.com/blog/top-alpha3d-ai-alternatives-for-3d-content-creation)
- Descrito por terceros como agregador que da acceso a Meshy, Rodin y Tripo — [stork.ai](https://www.stork.ai/compare/sloyd-ai-vs-3d-ai-studio)

**Alpha3D (alpha3d.io, e-commerce/AR)**
- Planes (CostBench, verificado 20-oct-2026): Tester $5/mes, Basic $17/mes, Creator $54/mes, Creator Pro $162/mes, Enterprise contact; "does not offer a free plan"; costes en créditos: GLB→FBX 7, rigging 15 (27 con conversión), UV unwrap 12, texturizado/segmentación hasta 61; quejas: fidelidad de detalle, poco control creativo, dependencia de la calidad del input — [CostBench Alpha3D](https://www.costbench.com/software/ai-3d-generation/alpha3d/)
- Snapshots anteriores (sin fecha fiable): pay-as-you-go ~$1 por modelo tras 50 gratis, o plan desde $0,99/mes; salida GLB para AR; "requires manual QA before deployment in customer-facing AR experiences" — [fitgap](https://us.fitgap.com/products/026630/alpha3d-ai); [SourceForge](https://www.sourceforge.net/software/product/Alpha3D)
- Competidor lo describe como "automating 3D content for e-commerce and AR, turning 2D product images into 3D models at scale" — [3D AI Studio blog](https://www.3daistudio.com/blog/top-alpha3d-ai-alternatives-for-3d-content-creation)
- La home oficial solo devolvió el tagline "The full AI 3D pipeline, in one place" (contenido JS no renderizado) — [alpha3d.io](https://www.alpha3d.io/)

### Inferences
- Precio real por modelo texturizado en SaaS (cálculo propio con las cifras citadas): Meshy Pro $20/1.000 cr = $0,02/cr → image-to-3D texturizado 30 cr = $0,60 (Premium $0,40; Ultra ~$0,30); Tripo Pro $20/3.000 cr = $0,0067/cr → 45 cr (35+10 según Unite) = $0,30, o ~$0,10 si son 15 cr/modelo como implica CostBench; 3D AI Studio pack $34/2.000 = $0,017/cr → 20 cr = $0,34 ($0,23 con el pack de $399); Sloyd Plus = ilimitado por $15 (coste marginal ~0); Rodin Creator $30/≈60 modelos = $0,50, Business $120/416 = $0,29; CSM Maker ~$0,20.
- Kaedim cuesta ~$400 por "complete asset" (Indie $400/1 asset; Pro $1.200/3 assets), es decir 600–4.000x el precio de un SaaS, y es el único con revisión humana en cada asset. Su promesa es "production-ready, every time" + revisiones ilimitadas, no "paga solo si apruebas".
- Rodin es el único SaaS con "pay per result" (créditos solo al confirmar/descargar); Meshy lo aproxima con reintentos gratis por tarea en planes de pago. Nadie ofrece reembolso por asset insatisfactorio.
- Tripo y Meshy ya han alcanzado escala de unicornio en 2026 con ingresos declarados de decenas a cientos de millones; el margen para competir en "generación cruda" es nulo; el hueco está en la capa de servicio (QC, escala, formatos e-commerce).

### Gaps
- Página oficial de precios de Tripo (403) y blog de Tripo (403): no pude confirmar créditos exactos por paso en la web app ni cuál de los dos valores (200 vs 300 créditos free) es el vigente.
- Fecha de lanzamiento público de Tripo y de Meshy: no encontrada en fuentes fiables (Meshy fundada en 2021 según tear sheet; Tripo sin dato).
- Fecha de fundación/lanzamiento de 3D AI Studio y Alpha3D: no encontradas.
- Precio USD por crédito en la API de Meshy y en los packs extra: no publicado; Meshy remite a "contact sales".
- Créditos incluidos por plan y créditos por descarga en Rodin: no publicados por el vendor; fuentes terceras se contradicen.
- Página de precios oficial de CSM y Kaedim no accesibles; todo son agregadores (CSM con 40 % de confianza según CostBench).
- Datos de usuarios/ingresos de Kaedim, CSM, Sloyd, Alpha3D, Hyper3D: no divulgados.

## ¿Cuánto cuesta una generación al usuario final en cada plataforma (créditos → USD) y cuánto la API por modelo?

### Takeaway
El usuario final paga entre ~$0,10 (Tripo Pro, estimación baja) y ~$0,60 (Meshy Pro, image-to-3D texturizado) por modelo en SaaS; en API, Tripo cobra $0,20–0,30 por image-to-3D (1 cr = $0,01) y Sloyd ~$0,27 (geometría+textura a $1 = 75 cr); Meshy no publica USD por crédito API.

### Cited Findings
- Tripo API: "1 credit = $0.01 USD"; Image to 3D 20–30 créditos; Texture 10–30; Retopology 10–40 — [Tripo Developers](https://developers.tripo3d.ai/)
- Tripo en fal.ai: $0,20 / $0,30 / $0,40 (sin textura / estándar / HD), quad y estilo +$0,05 — [fal.ai](https://fal.ai/models/tripo3d/tripo/v2.5/image-to-3d)
- Meshy Pro $20 → 1.000 créditos; image-to-3D meshy-7.1 texturizado 30 créditos (API), 20 (web app, +10 con textura) — [CostBench](https://www.costbench.com/compare/meshy-vs-tripo-ai/); [Meshy API pricing](https://docs.meshy.ai/en/api/pricing); [Meshy webapp pricing](https://docs.meshy.ai/en/webapp/pricing)
- Sloyd API: $1 = 75 créditos; image-to-3D 10 + textura 10 = 20 créditos; retexture 15 — [Sloyd API](https://www.sloyd.ai/api/pricing)
- 3D AI Studio: 20 créditos por image-to-3D; $34/2.000 créditos ($1,70 por 100) — [3D AI Studio](https://www.3daistudio.com/pricing)
- Rodin: créditos directos $1,50; Creator $30 ≈ 60 modelos; Business $120 ≈ 416 modelos — [Hyper3D](https://hyper3d.ai/pricing)
- Kaedim: Indie $400/20 créditos (1 asset completo), exceso $22/crédito; Pro $1.200/60 créditos (3 assets), exceso $16/crédito — [CostBench Kaedim](https://costbench.com/software/ai-3d-generation/kaedim/)
- CSM Maker $20/100 créditos, ~1 crédito/modelo — [CostBench CSM](https://www.costbench.com/software/ai-3d-generation/csm/); [Sloyd blog](https://sloyd.ai/blog/3d-ai-price-comparison)

### Inferences
- Tabla de coste por modelo texturizado (cálculo propio): Tripo web $0,10–0,30 · Tripo API $0,30–0,60 (image-to-3D 20–30 cr + textura 10–30 cr) · fal Tripo $0,30–0,45 · Meshy Pro $0,60 / Premium $0,40 / Ultra $0,30 · Sloyd API $0,27 · Sloyd Plus ~$0 marginal (ilimitado) · 3D AI Studio $0,23–0,34 · Rodin $0,29–0,50 (suscripción) o $1,50+/crédito directo · CSM ~$0,20 · Kaedim ~$400.
- El free tier real para un e-commerce: Meshy 100 cr = 3 modelos texturizados/mes con licencia CC BY; Tripo 200–300 cr = ~5–13 modelos no comerciales; Sloyd 1/día personal; Rodin 10 créditos iniciales (menos de una descarga si cuesta ~40); 3D AI Studio créditos iniciales sin cifra; Alpha3D sin free.

### Gaps
- USD por crédito API de Meshy y precio de packs extra: no publicados.
- Créditos exactos por paso en la web app de Tripo (página oficial inaccesible).

## ¿Quién tiene human-in-the-loop o "paga solo si apruebas", y a qué precio?

### Takeaway
Solo Kaedim tiene revisión humana en cada asset (~$400 por asset completo vía Indie/Pro, o contrato enterprise); Rodin Enterprise ofrece "AI+Artist support" sin precio; Rodin Free es el único "pay per result" (créditos al confirmar). Nadie promete reembolso si el asset no se aprueba.

### Cited Findings
- Kaedim: "Our art team verifies and cleans all outputs", "guarantees users get a production-ready 3D model, every time"; "Make unlimited revisions. Your asset, your call." — [Kaedim docs](https://docs.kaedim3d.com/welcome/how-kaedim-works); [Kaedim home](https://www.kaedim3d.com/)
- Kaedim precios: Trial $50 (5 créditos), Indie $400 (20 cr = 1 asset completo), Pro $1.200 (60 cr = 3 assets), exceso $22/$16 por crédito — [CostBench Kaedim](https://costbench.com/software/ai-3d-generation/kaedim/)
- Kaedim artistas cobraban $1–4 por modelo (2023) — [TechSpot](https://www.techspot.com/news/100076-startup-ai-made-3d-models-2d-art-actually.html)
- Rodin Free: "Pay per result", "only spend credits when you confirm one"; Enterprise: "AI+Artist support for near-production-ready assets" — [Hyper3D](https://hyper3d.ai/pricing)
- Meshy: reintentos gratis por tarea 4 (Pro) / 12 (Premium) / 40 (Ultra) / 100 (Enterprise); fallos no se cobran — [Meshy pricing](https://www.meshy.ai/pricing); [Meshy docs](https://docs.meshy.ai/en/webapp/pricing)
- Rodin redos: Creator 20 geometría / 6 materiales; Business 50 / 15 — [Hyper3D](https://hyper3d.ai/pricing)
- Nextech ARitize3D (fuera de la lista, e-commerce mobiliario): "human-in-the-loop QA" para "accurate fabrics, woods, metals, and lighting", SLAs por catálogo, sin precio público — [Nextech AR furniture](https://www.nextechar.com/industries/furniture-home-decor)

### Inferences
- El "colchón de calidad" del SaaS son reintentos/redos (coste cero para el usuario pero sin garantía de resultado); el de Kaedim es trabajo humano facturado a ~$20/crédito. Entre $0,50 y $400 no hay oferta intermedia con garantía explícita, salvo servicios AR de e-commerce con QA humana y precio opaco (Nextech).

### Gaps
- Precio por asset de Kaedim en contratos enterprise y si sigue vendiendo Indie/Pro (web oficial de precios 404; agregadores contradictorios).
- Precio de "AI+Artist" de Rodin Enterprise: no publicado.

## ¿Quién ofrece USDZ/AR o viewer embebible para e-commerce?

### Takeaway
USDZ lo exportan Meshy, Tripo (API), 3D AI Studio y Kaedim (USD); ninguno de los diez ofrece un viewer/AR embebible para fichas de producto como producto; eso lo venden terceros (Vizbl, Nextech ARitize3D, apps Shopify).

### Cited Findings
- Meshy: descargas .fbx .obj .usdz .glb .stl .blend — [Meshy pricing](https://www.meshy.ai/pricing)
- Tripo API: "GLB, FBX, OBJ, USDZ and other mainstream formats" — [Tripo Developers](https://developers.tripo3d.ai/)
- 3D AI Studio: GLB, OBJ, FBX, STL, USDZ, PLY — [3D AI Studio](https://www.3daistudio.com/pricing)
- Kaedim: OBJ, FBX, MTL, USD, GLB, GLTF — [Kaedim docs](https://docs.kaedim3d.com/welcome/how-kaedim-works)
- Sloyd: GLB, OBJ, FBX (sin USDZ) — [Sloyd pricing](https://www.sloyd.ai/pricing)
- CSM free: glTF, OBJ, FBX — [CostBench CSM](https://www.costbench.com/software/ai-3d-generation/csm/)
- Alpha3D: GLB, FBX (USDZ no mencionado) — [CostBench Alpha3D](https://www.costbench.com/software/ai-3d-generation/alpha3d/)
- fal Hunyuan3D: GLB y OBJ; Replicate TRELLIS: GLB — [fal Hunyuan](https://fal.ai/hunyuan-3d); [Replicate TRELLIS](https://replicate.com/firtoz/trellis)
- Vizbl: "Embed the viewer with a single line of HTML", botón para Shopify/WordPress, "True scale… accurate to ±5 mm", mobiliario como vertical principal — [Vizbl](https://vizbl.pages.dev/)
- Nextech ARitize3D: GLB y USDZ, "One-click WebAR and 360° spins", QR para desktop, "true scale" — [Nextech AR](https://www.nextechar.com/industries/furniture-home-decor)
- Shopify sirve USDZ a iOS y GLB a Android, por lo que una tienda necesita ambos — [WebSearch; Crystallize](https://crystallize.com/blog/3dar-furniture-product-configurator)

### Inferences
- Para una ficha de producto hacen falta GLB + USDZ + escala en metros + viewer; los generadores cubren solo los dos primeros. La integración (model-viewer, Shopify 3D, QA de escala) queda para el comerciante o para un intermediario.

### Gaps
- Si Rodin, CSM y Alpha3D exportan USDZ hoy: no confirmado en fuentes primarias.

## ¿Dónde está la fricción de UX para un dueño de e-commerce novato?

### Takeaway
La fricción no está en el botón "generar" sino en lo que viene después: elegir modelo/versión, texturizar como paso separado con coste propio, créditos consumidos sin saber el resultado, topología/escala que hay que arreglar en Blender, licencias del free tier y formatos; la observación de Jorge sobre Tripo coincide con reseñas que piden un walkthrough y critican precios "complicados".

### Cited Findings
- Tripo: flujo = prompt/imagen → generar (35 cr, "a couple of minutes") → pestaña Texture → describir y "Generate Texture" (10 cr, "a few minutes"); "Some cleanup and guidance are needed for complex designs"; costes de refine/rig/export no divulgados — [Unite.AI](https://www.unite.ai/tripo-review)
- Tripo G2: un usuario pide un asistente tipo walkthrough; se gastan créditos "without necessarily knowing what to expect from the outcome"; en Free no se puede descargar — [G2](https://www.g2.com/products/tripo-studio/reviews)
- Tripo quejas: "complicated pricing", postprocesado necesario, control limitado — [ToolRadar](https://toolradar.com/compare/tripo-ai-vs-meshy); [Trustpilot](https://www.trustpilot.com/review/tripo3d.ai?page=5)
- Tripo Studio: modos "One-click" vs "Build & Refine"; retexturizado por partes — [chatgate.ai](https://chatgate.ai/post/tripo-studio)
- Meshy: resultados image-to-3D irregulares, falla en superficies duras ("ai doesn't know what a hard surface is"), mallas de 43k tris demasiado densas; un prop de 1 m puede importarse a 100 m — [Techraisal](https://www.techraisal.com/blog/meshy-ai-pros-cons-pricing-reviews); [Sorceress](https://sorceress.games/blog/mesh-meshy-ai-image-to-3d-textured-glb)
- Meshy 7 modelos/versiones múltiples (7.1, 6, 6 Lite, T2, T2.5) con costes distintos y deprecaciones (lowpoly retirado 30-oct-2026) — [Meshy API models](https://docs.meshy.ai/en/api/models); [Meshy API pricing](https://docs.meshy.ai/en/api/pricing)
- CSM: "Setup can be complex and may require significant training" — [CostBench CSM](https://www.costbench.com/software/ai-3d-generation/csm/)
- Rodin: refinado y descomposición "quite expensive" y ~1 día; aritmética de créditos confusa ($1,50/cr directo vs ~$0,50/modelo en plan) — [CostBench Rodin](https://costbench.com/software/ai-3d-generation/rodin-hyper3d/); [Picassoia](https://blog.picassoia.com/rodin-gen-2-5-hyper3d-image-to-3d-pricing-and-quality)
- Alpha3D: "requires manual QA before deployment in customer-facing AR experiences" — [fitgap](https://us.fitgap.com/products/026630/alpha3d-ai)
- Escala: Tripo `auto_size` (metros) y Meshy `autoSize` ("estimate real-world scale") existen como parámetros de API, no como garantía — [fal Tripo](https://fal.ai/models/tripo3d/tripo/v2.5/image-to-3d); [Meshy docs](https://docs.meshy.ai/hi/webapp/text-to-3d)

### Inferences
- Para un dueño de tienda de muebles el recorrido "subir foto → descargar GLB/USDZ a escala y publicarlo" implica hoy 5–8 decisiones técnicas (modelo IA, textura/PBR, polycount, remesh, escala en metros, formato, licencia, viewer). Un producto de función única que colapse eso en "sube la foto y las medidas → recibe GLB+USDZ validados" no existe entre los diez.

### Gaps
- No encontré hilos de Reddit de primera mano sobre escala/medidas en Tripo o Meshy (solo citas de segunda mano); la evidencia de queja sobre "true-to-scale" es fina.

## Precios de API hosteada para TRELLIS, Hunyuan3D 2.x/3.x y Tripo en fal.ai / Replicate (finales de 2026)

### Takeaway
A 2026-11: TRELLIS cuesta $0,02/generación en fal y ~$0,038 en Replicate; Hunyuan3D v3/v3.1 en fal $0,225 (Rapid/Geometry) a $0,375 (Pro/Normal) + $0,15 por PBR; Hunyuan3D-2 en Replicate ~$0,044; Tripo v2.5 en fal $0,20–0,40. Hunyuan3D 2.1 ya no aparece con precio propio en fal.

### Cited Findings
- fal-ai/trellis: "Your request will cost $0.02 per generation"; salida GLB (también Radiance Fields / 3D Gaussians) — [fal TRELLIS](https://fal.ai/models/fal-ai/trellis)
- Replicate firtoz/trellis: "approximately $0.038 to run", "26 runs per $1", Nvidia A100 80GB, ~28 s; GLB con texturas — [Replicate TRELLIS](https://replicate.com/firtoz/trellis)
- Replicate tencent/hunyuan3d-2: ~$0,044/run, 22 runs por $1, Nvidia L40S, ~46 s; salida trimesh exportable a GLB/OBJ — [Replicate Hunyuan3D-2](https://replicate.com/tencent/hunyuan3d-2)
- fal-ai/hunyuan3d-v3/image-to-3d: Geometry $0,225; Normal $0,375; LowPoly $0,45; add-ons +$0,15 cada uno (PBR, multi-view, custom face count); ejemplo Normal+PBR $0,525; GLB (~64 MB) y OBJ; ~1 minuto — [fal Hunyuan3D v3](https://fal.ai/models/fal-ai/hunyuan3d-v3/image-to-3d)
- fal Hunyuan 3D v3.1: Pro text/image-to-3D $0,375; Rapid $0,225; PBR +$0,15; Part Splitter $0,45; Smart Topology $0,75; GLB y OBJ; hasta 1,5M caras — [fal Hunyuan 3D](https://fal.ai/hunyuan-3d)
- Tripo v2.5 en fal: $0,20 / $0,30 / $0,40; quad y estilo +$0,05 — [fal Tripo](https://fal.ai/models/tripo3d/tripo/v2.5/image-to-3d)
- Hunyuan3D 2.1 en otros hosts: Eachlabs $0,30 por ejecución; WaveSpeed desde $0,40; SaladCloud afirma $0,009 autohosteado "saving 94% over FAL" (implica ~$0,15 en fal, no confirmado) — [Eachlabs](https://www.eachlabs.ai/tencent/hunyuan-3d/hunyuan-3d-v2-1); [WaveSpeed](https://wavespeed.ai/zh-TW/models/wavespeed-ai/hunyuan3d/v2.1); [SaladCloud](https://blog.salad.com/hunyuan3d-2-1/)
- Rodin v2.5 en WaveSpeed: $0,40 base, HighPack +$0,80 — [WaveSpeed Rodin](https://wavespeed.ai/models/hyper3d/rodin-v2.5/image-to-3d)

### Inferences
- Coste de cómputo por modelo con PBR vía API abierta: ~$0,02–0,05 (TRELLIS) a ~$0,375–0,525 (Hunyuan3D v3 Normal/Pro + PBR); un servicio que cobre $5–20 por mueble validado tendría un margen bruto de cómputo >90 % incluso generando 3–5 candidatos por producto.
- Replicate es 2x más caro que fal para TRELLIS pero sigue por debajo de $0,05; la diferencia es irrelevante frente al coste de QC.

### Gaps
- Precio de Hunyuan3D 2.1 y 2.0 multi-view en fal.ai: no encontrado (fal solo lista v3/v3.1).
- Tripo en Replicate: no verificado.

## Comparativa: precio por modelo usable, quién garantiza la calidad y si alguien vende "muebles a escala real para fichas de producto"

### Takeaway
Nadie entre los diez vende "true-to-scale furniture models for product pages" como función definida; los más cercanos son servicios AR de e-commerce (Vizbl ±5 mm, Nextech ARitize3D con QA humana, YourLightAR $19/mes) y Kaedim/Alpha3D como "e-commerce" genérico. La calidad solo la garantiza Kaedim (humanos, ~$400/asset); el resto vende créditos y reintentos.

### Cited Findings
- Vizbl: "True scale in the customer's own room, accurate to ±5 mm"; "Furniture & Home" como vertical líder; sube fotos o modelos existentes y la IA "generates the rest"; embed con una línea de HTML; sin precio por modelo ni QA humana mencionada — [Vizbl](https://vizbl.pages.dev/)
- Nextech ARitize3D: fotos o CAD → modelos AR-ready, GLB/USDZ, WebAR, "human-in-the-loop QA", "Bulk model generation + SLAs", "Most pilots go live in days"; sin precio — [Nextech AR](https://www.nextechar.com/industries/furniture-home-decor)
- YourLightAR (app Shopify): desde $19/mes con cupo de modelos IA; "true-to-scale AR previews" — [Shopify App Store](https://apps.shopify.com/yourlightar)
- Kaedim vertical "E-commerce & Marketing: Create CGI without the shoot"; cliente Lowe's (retail de hogar) 14x más assets — [Kaedim](https://www.kaedim3d.com/)
- Alpha3D: "automating 3D content for e-commerce and AR" — [3D AI Studio blog](https://www.3daistudio.com/blog/top-alpha3d-ai-alternatives-for-3d-content-creation)
- Fiverr: freelancers crean "3d glb, gltf, usdz models for shopify, amazon and ar" — [Fiverr](https://fiverr.com/dima_maksimuk/create-3d-glb-gltf-usdz-models-for-shopify-amazon-and-ar)
- Escala como parámetro, no como garantía: Tripo `auto_size` (metros), Meshy `autoSize` — [fal Tripo](https://fal.ai/models/tripo3d/tripo/v2.5/image-to-3d); [Meshy docs](https://docs.meshy.ai/hi/webapp/text-to-3d)
- Vendors citan −40 % devoluciones en mobiliario/decoración con AR, sin fuente — [Vizbl](https://vizbl.pages.dev/)

### Inferences
- Precio por modelo *usable* (no por generación): si la tasa de aceptación de un SaaS ronda 1 de cada 3–5 intentos (reseñas hablan de "keep retrying"), el coste real sube a $0,60–3 por modelo usable más el tiempo del usuario en Blender; Kaedim entrega 1 usable por ~$400. El hueco de mercado está entre $5 y $50 por mueble validado a escala con GLB+USDZ.
- Quién garantiza: Kaedim (humanos, enterprise); Nextech (QA humana, catálogo B2B); Rodin (no cobra hasta que confirmas la preview, pero no garantiza); resto: nadie.
- Propuesta "sube foto + medidas → GLB/USDZ a escala verificado para tu ficha" no existe como producto de función única con precio público.

### Gaps
- Tasa de aceptación real por generación (cuántos intentos hasta un modelo usable): ninguna fuente la cuantifica.
- Precios por modelo de Vizbl y Nextech: no publicados.
- Dimensiones/precisión de escala de los generadores IA (error típico en cm): ningún vendor la publica; solo Vizbl promete ±5 mm (sin método).
