# Amenazas de plataforma y sustitución tecnológica para "Site Hassle" (foto → 3D → AR web para tiendas de muebles/decoración)

> Fecha de corte: 8 de noviembre de 2026. Cada hecho lleva fecha y fuente. Etiquetas: **[CONFIRMADO]** = fuente primaria (empresa, regulador, documentación oficial); **[SECUNDARIO]** = prensa/analistas/blogs de agencia; **[NO CONFIRMADO]** = rumor, afirmación de un solo vendedor o sin fuente primaria localizada.
>
> Resumen ejecutivo en una línea: **ninguna gran plataforma (Shopify, Google, Apple, Amazon) genera hoy modelos 3D a partir de fotos de catálogo de forma nativa y gratuita** para la tienda independiente; pero (a) todas ellas ya han construido o están construyendo la *experiencia de visualización en tu casa* con imágenes generativas 2D (Google AI Mode ago-2026, Meta jul-2026, Pinterest sep-2026, Wayfair feb-2025), (b) la generación foto→3D se ha comoditizado (APIs a 0,10–0,60 $/modelo; pesos abiertos MIT como TRELLIS.2) y ya hay ≥6 apps de Shopify que la ofrecen desde 0–33 $/mes, y (c) el comercio agéntico desplaza parte del tráfico fuera de la ficha de producto donde vive el botón AR. La amenaza principal no es que Shopify "copie la función", sino que el valor del 3D-AR en ficha se erosione por los dos lados: sustitución 2D generativa y comoditización de la producción.

---

## 1. Shopify: 3D/AR nativo, escáner 3D, Shopify Magic/Sidekick, señales de generación nativa de 3D y política de apps

### Takeaway
Shopify tiene soporte nativo de 3D/AR en ficha de producto desde 2018 (Quick Look) y un escáner 3D gratuito en la app iOS desde septiembre de 2023, pero **a noviembre de 2026 no hay ninguna señal confirmada (Editions Winter '26, changelog, Tinker, Sidekick) de que Shopify vaya a generar modelos 3D a partir de fotos de catálogo**. Su inversión en media con IA es 2D (generación/edición de imágenes en Sidekick, app Tinker). Su política de App Store no prohíbe apps que dupliquen funciones nativas; el riesgo real es la absorción progresiva de funciones ("platform absorption"), no la expulsión.

### Cited Findings

#### Línea temporal Shopify (3D/AR y media IA)

| Fecha | Hecho | Estado | Fuente |
|---|---|---|---|
| sep-2018 | Shopify habilita AR Quick Look (USDZ) en tiendas vía Safari iOS 12; el comerciante aporta el modelo. | CONFIRMADO | [Shopify VR blog (Medium)](https://medium.com/shopify-vr/c2716593823f); [AppleInsider, 13-jul-2018](https://appleinsider.com/articles/18/07/13/ar-quick-look-brings-augmented-reality-to-safari-in-ios-12) |
| 2019–2020 | Modelos 3D (GLB) como "product media" nativo; al subir un GLB Shopify activa `model-viewer` y botón AR en temas compatibles. El help center exige "un tema que soporte modelos 3D y vídeo" y sugiere "contratar a un Shopify Partner" para crear los modelos. | CONFIRMADO | [Shopify Help – 3D models](https://help.shopify.com/en/manual/products/product-media/3d-models) |
| 19-sep-2023 | Changelog: "3D scanner for the Shopify app on iOS Pro models", ligado al lanzamiento de iOS 17. Solo iPhone/iPad Pro (LiDAR). No menciona precio ni Android. | CONFIRMADO | [Shopify changelog](https://changelog.shopify.com/posts/3d-scanner-for-the-shopify-app-on-ios-pro-models); [Help center – 3D scanner](https://help.shopify.com/cs/manual/products/product-media/3d-scanner) |
| 2023–2026 | El escáner sigue requiriendo iPhone/iPad Pro; fuentes secundarias discrepan sobre si "es gratis" o "puede tener costes según plan". No se localizó confirmación oficial de precio. | SECUNDARIO | [WebsiteBuilderExpert](https://www.websitebuilderexpert.com/news/shopify-3d-scanner/); [ecomappguide, feb-2026](https://ecomappguide.pages.dev/posts/2026/02/shopify-app-3d-scanner-guide) |
| 6-may-2025 | Changelog: "Image generation now available in Sidekick" (imágenes 2D guardables en Content > Files). | CONFIRMADO | [Shopify changelog](https://changelog.shopify.com/posts/image-generation-now-available-in-sidekick) |
| dic-2025 (Winter '26 "RenAIssance") | 150+ novedades: Sidekick proactivo, creación de apps admin y edición de temas por lenguaje natural, Agentic Storefronts, Rollouts (A/B nativo), SimGym, edición de fotos de producto con IA en el editor de archivos (quitar fondo, escenas lifestyle). **Ningún anuncio de generación 3D desde fotos.** Un resumen de agencia menciona "3D models, AR previews" solo como parte del catálogo ya existente. | SECUNDARIO (resúmenes de agencias; no se localizó la página oficial de Editions con listado 3D) | [Shopifreaks](https://www.shopifreaks.com/highlights-of-shopify-winter-26-edition-the-renaissance-edition/); [Meetanshi](https://meetanshi.com/blog/shopify-editions-winter-2026/); [Glaze Digital](https://glazedigital.com/blogs/news/shopify-editions-winter-2026) |
| 26-mar-2026 (año no verificado en fuente primaria) | **Tinker by Shopify**: app móvil gratuita con 100+ herramientas de IA para imagen/vídeo/marca. El help center lista "3D Figurine Generator", "3D Floor Plan Generator", "Background Generator", "Product Lifestyle Shot". Son generadores de **imágenes 2D con estética 3D**, no de mallas GLB/USDZ para AR. | CONFIRMADO (existencia/herramientas) · SECUNDARIO (fecha) | [Shopify Help – Tinker](https://help.shopify.com/ar/manual/ai-powered-tools/tinker); [LetsDataScience](https://letsdatascience.com/news/shopify-launches-tinker-for-merchant-creativity-98822144); [Pasilobus](https://www.pasilobus.com/fr/blogs/articles/shopify-just-launched-a-free-ai-creative-app-called-tinker) |
| 24-mar-2026 | Agentic Storefronts activado por defecto para comerciantes elegibles en EE. UU.: descubrimiento en ChatGPT, Microsoft Copilot, Google AI Mode y Gemini; el checkout se completa en la tienda del comerciante (ver §5). | SECUNDARIO (múltiples fuentes; no se recuperó el post del newsroom) | [TrueProfit](https://trueprofit.io/blog/shopify-agentic-storefronts); [Doolpa](https://doolpa.com/news/shopify-agentic-storefronts-live-chatgpt-copilot-gemini-march-2026) |
| Summer '26 Edition (2026) | No se localizó ninguna función de 3D ni de media de producto relevante en la cobertura disponible; el único post encontrado era copy genérico. | NO CONFIRMADO | [IceCube Digital](https://www.icecubedigital.com/?p=57192) |

#### Política de apps y "platform absorption"
- Los requisitos oficiales del App Store **no contienen ninguna regla contra apps que repliquen funciones nativas de Shopify**. La regla 1.1.5 ("Create unique apps") dice solo: "App must not be identical to other apps you've published to the Shopify App Store". Lo prohibido es otra cosa: saltarse checkout, marketplaces, agencias, lending, billing fuera de plataforma, apps que no usen APIs de Shopify (2.2.1). La 2.2.5 exige que las extensiones admin "provide novel functionality or content". — [shopify.dev – App Store requirements](https://shopify.dev/docs/apps/launch/shopify-app-store/app-store-requirements) **[CONFIRMADO]**
- Una guía de terceros afirma que "apps generally shouldn't replicate existing Shopify functionality unless they add something meaningfully new or better" — no está en el texto oficial. — [Cleverence](https://www.cleverence.com/amp/articles/shopify-dev-documentation/questions-about-app-type-restrictions-for-app-store-submissions-4827/) **[SECUNDARIO]**
- Jul-2026: Shopify lanzó funciones nativas (marketing WhatsApp, etiquetas de devolución UPS, pagos multidivisa) que solapan con apps de terceros; análisis de agencia sobre cuándo cancelar apps solapadas. — [Ecommerce Fastlane](https://ecommercefastlane.com/hopify-platform-absorption-app-decision/) **[SECUNDARIO]**

#### Competencia dentro del App Store (foto → 3D ya existe)
- 3Dify "Photo to 3D Model": generación desde una o varias imágenes, GLB en storefront, plan gratuito de 3 generaciones/mes. — [Shopify App Store](https://apps.shopify.com/3dify) **[CONFIRMADO listado]**
- "AI 3D Model Generator": 2-3 imágenes → modelo en 3-10 min. — [Shopify App Store](https://apps.shopify.com/ai-3d-models-generator) **[CONFIRMADO listado]**
- FreakoutAI 3D Model Generator; "3D AI Generator: Photo to 3D" (spacecheck); Instant 3D. — [FreakoutAI](https://apps.shopify.com/freakout-ai); [spacecheck](https://apps.shopify.com/spacecheck); [Instant 3D](https://apps.shopify.com/instant-3d) **[CONFIRMADO listados]**
- Apps de escaneo con móvil con planes gratuitos: Supra 3D Capture (3 escaneos/mes gratis), 3D Scan & Show (2 escaneos de bienvenida), Doly. — [Supra](https://apps.shopify.com/supra-3d-capture); [3D Scan & Show](https://apps.shopify.com/3d_scan_products) **[CONFIRMADO listados]**

### Inferences
- Shopify ha elegido la vía "el comerciante aporta el modelo" (escáner LiDAR, partners) y la vía "IA 2D" (Sidekick, Tinker). No hay indicio de que quiera asumir el coste de inferencia y el soporte de calidad de un pipeline foto→malla a escala; es coherente con que Tinker tenga un "3D Figurine Generator" (imagen) y no un "GLB generator".
- Que no exista regla anti-duplicación significa que Shopify no expulsará a Site Hassle; pero tampoco le protegerá: si añade "generate 3D model" como botón en product media (técnicamente trivial con una API tipo Tripo/Meshy), lo haría sin preaviso, como hizo con el escáner en 2023.
- El riesgo de plataforma más inmediato en Shopify **no es Shopify**: es que el App Store ya tiene ≥6 apps "photo to 3D" con planes gratuitos lanzadas entre 2025 y mayo de 2026. El precio de referencia del nicho es 0–33 $/mes, no un SaaS por catálogo.

### Gaps
- No se recuperó la página oficial de Shopify Editions Winter '26 ni Summer '26 (solo resúmenes de agencias); conviene verificar en shopify.com/editions.
- No se encontraron ofertas de empleo ni patentes de Shopify sobre reconstrucción 3D generativa (no se hizo búsqueda específica en portales de empleo/USPTO por límite de llamadas).
- Precio oficial del escáner 3D (gratis vs. por plan) no confirmado por Shopify.
- Cuota de comerciantes que usan 3D/AR nativo en Shopify: dato no publicado.

---

## 2. Google: Shopping 3D/AR, try-on generativo, AI Mode "en tu habitación", Nano Banana, Scene Viewer/ARCore, Android XR

### Takeaway
Google mantiene el 3D/AR en Shopping (solo EE. UU., CA, AU, JP, IN; solo "home goods and shoes"; solo listados gratuitos; Google no genera mallas, solo 360-spins) y Scene Viewer sigue documentado sin aviso de retirada. Pero su apuesta estratégica desde 2025 es **imagen generativa**: try-on de ropa (may-2025), inspiración de habitaciones (sep-2025) y, desde agosto de 2026, **subir la foto de tu salón a AI Mode y pedir "muéstrame cómo quedaría un sofá de terciopelo verde esmeralda" → mockup en tu espacio**, sin modelo 3D del comerciante.

### Cited Findings

#### Línea temporal Google

| Fecha | Hecho | Estado | Fuente |
|---|---|---|---|
| 2019–2020 | Resultados 3D/AR en Search (Scene Viewer); IKEA publica >10.000 productos en 3D/AR en Google Search. | SECUNDARIO | [Mixed News](https://mixed-news.com/en/ikea-products-ar-models-google-search/); [SERoundtable](https://www.seroundtable.com/amp/google-search-3d-objects-with-augmented-reality-27533.html) |
| 17-nov-2022 | "View in my space" para zapatillas en resultados de búsqueda; "any brand with 3D assets for sneakers or home goods can participate". | SECUNDARIO | [Tom's Guide](https://www.tomsguide.com/news/google-now-lets-you-shop-for-sneakers-in-ar-heres-how); [Android Central](https://www.androidcentral.com/apps-software/googles-new-ar-shopping-features-help-you-avoid-picking-the-wrong-product) |
| Vigente (©2026) | Merchant Center: 3D/AR limitado a US, CA, AU, JP, IN; atributo `virtual_model_link` "for home goods and shoes only"; formatos glTF/glb; **Google genera 360-spins con IA ("generated by Google") pero no modelos 3D**; AR "view in your space" solo en listados gratuitos con badge 3D, no en Shopping Ads. | CONFIRMADO | [Google Merchant Center Help](https://support.google.com/merchants/answer/13675100?hl=en) |
| Vigente (nov-2026) | Documentación de Scene Viewer sin banner de deprecación; requisitos: ARCore, Android 7.0+, Google Play Services for AR. Lo deprecado es Sceneform (2021) y el formato .sfb, no Scene Viewer. | CONFIRMADO (ausencia de aviso) | [Google Developers – Scene Viewer](https://developers.google.com/ar/develop/scene-viewer); [SceneView comparison](https://sceneview.github.io/comparison) |
| 20-may-2025 (I/O) | AI Mode shopping: try-on virtual de ropa con foto del usuario (Search Labs, EE. UU.; "custom image generation model for fashion"); checkout agéntico "buy for me" con Google Pay. Sin mención a 3D/AR. | CONFIRMADO | [Google Keyword blog](https://blog.google/products/shopping/google-shopping-ai-mode-virtual-try-on-update/) |
| 24-jul-2025 | Google anuncia que AI Mode generará "outfit and room design inspiration" en otoño (expansión de Vision Match). | SECUNDARIO | [ccstartup](https://ccstartup.com/blog/2025/07/24/googles-ai-mode-will-soon-give-you-outfit-room-design-inspo) |
| sep-2025 | "AI Mode can now help you search and explore visually": prompts tipo "maximalist inspo for my bedroom" devuelven imágenes generadas shoppables (Gemini 2.5 + Lens/Image Search). | CONFIRMADO | [Google Keyword blog](https://blog.google/products/search/search-ai-updates-september-2025/) |
| nov-2025 | Actualización de compras navideñas en AI Mode, centrada en ropa/productos ("cozy sweaters…"), imágenes shoppables. | SECUNDARIO | [BGR](https://bgr.com/2025399/google-search-ai-mode-gemini-shopping-black-friday); [Neowin](https://www.neowin.net/news/google-adds-new-ai-features-to-make-your-holiday-shopping-easier/) |
| ene-2026 | Universal Commerce Protocol (UCP) con Walmart, Target, Shopify y 20+ socios; AP2 (Agent Payments Protocol) como capa de mandatos/autorización, "sin superficie de consumo masiva aún". | SECUNDARIO | [AskPhill](https://askphill.com/blogs/blog/agentic-commerce-for-shopify-protocols-platforms-and-what-to-prioritize-in-2026) |
| feb-2026 | "Nano Banana 2" (Gemini 3.1 Flash Image Preview) pasa a ser el modelo de imagen por defecto en la app Gemini; guías de consumo sobre "poner muebles en la foto de tu habitación"; límites: proporciones de muebles "derivan", texturas artificiales. | SECUNDARIO / NO CONFIRMADO (nomenclatura inconsistente entre fuentes) | [House Digest](https://www.housedigest.com/2009670/ai-diy-tool-google-gemini-nano-banana); [meltflexai](https://www.meltflexai.com/blog/how-to-redesign-room-nano-banana-pro) |
| may-2026 (I/O) | Gafas Android XR (Samsung/Google, monturas Gentle Monster/Warby Parker) con Gemini multimodal; lanzamiento "este otoño"; XREAL Project Aura a finales de oct-2026. **No se encontró ninguna función de compra/visualización de muebles confirmada** para las gafas. | SECUNDARIO | [Engadget I/O 2026 liveblog](https://www.engadget.com/2176173/google-io-live-blog-gemini-ai/); [TestingCatalog](https://www.testingcatalog.com/google-and-xreal-launch-aura-android-xr-glasses.md) |
| 25-ago-2026 | Post oficial "5 ways to upgrade your home decor with Google Search": búsquedas de "home decor inspo" +300 % en un mes; en AI Mode "simply upload a photo of your room" y pregunta qué sofá encaja; puedes pedir "Can you show me what an emerald green velvet sofa could look like?" y ver "a mockup right in your space". Lens y Circle to Search para encontrar similares. **Sin mención a 3D/AR.** | CONFIRMADO | [Google Keyword blog](https://blog.google/products-and-platforms/products/search/home-decor-tips/) |

### Inferences
- Google ha pasado de "el comerciante sube un GLB y lo mostramos en AR" (2019–2022, alcance geográfico y de categoría estrecho, nunca llegó a España) a "el consumidor sube la foto de su salón y nosotros generamos el producto dentro" (2025–2026, cualquier producto con imágenes en el feed). La segunda vía **no necesita al comerciante ni a su plugin**: usa las imágenes 2D de Merchant Center.
- Scene Viewer no está deprecado, pero tampoco ha recibido inversión visible desde 2022; es infraestructura en mantenimiento. El riesgo de "sunset" a 24 meses es bajo-medio y, si ocurriera, afectaría a todos los proveedores de web-AR Android por igual (WebXR sería el sustituto).
- Para España/UE el 3D/AR de Google Shopping es irrelevante hoy (no disponible). Lo que sí llegará a usuarios españoles es AI Mode con generación de imágenes, que es el sustituto 2D.

### Gaps
- No se encontró una declaración de Google que compare o priorice explícitamente generativo 2D vs. 3D/AR; la inferencia se basa en dónde han puesto los lanzamientos.
- Disponibilidad de la función "sube la foto de tu habitación" fuera de EE. UU. (¿España?) no confirmada.
- Datos de uso de "view in your space" en Google nunca publicados.

---

## 3. Apple: AR Quick Look, Object Capture, visionOS, `<model>` en Safari, Apple Pay, deprecación de USDZ

### Takeaway
Apple sigue invirtiendo en el visor 3D nativo del navegador: el elemento HTML `<model>` llegó a visionOS 26 (2025) y a iPhone/iPad/Mac con Safari 27 / iOS 27 (otoño 2026), aceptando **USDZ y glTF**. No hay ningún indicio de deprecación de AR Quick Look ni de USDZ, ni de que Apple construya "shopping AR" propio más allá del botón Apple Pay en Quick Look (2020). Apple es un habilitador de plataforma que abarata el visor, no un competidor que genere modelos.

### Cited Findings

| Fecha | Hecho | Estado | Fuente |
|---|---|---|---|
| 13-jul-2018 (iOS 12) | AR Quick Look para USDZ en Safari, Mail, Messages, etc. | CONFIRMADO (prensa + Apple gallery) | [AppleInsider](https://appleinsider.com/articles/18/07/13/ar-quick-look-brings-augmented-reality-to-safari-in-ios-12); [Apple AR Quick Look gallery](https://developer.apple.com/augmented-reality/quick-look/usdz/) |
| 13-feb-2020 | Quick Look admite botón de compra con Apple Pay y banners personalizados dentro de la vista AR. | CONFIRMADO | [TechCrunch](https://techcrunch.com/2020/02/13/apple-expands-quick-look-to-let-retailers-sell-things-directly-in-augmented-reality) |
| jun-2021 (WWDC21) | Object Capture (fotogrametría) en RealityKit 2 / macOS Monterey; Wayfair y Etsy como adoptantes tempranos. | CONFIRMADO (prensa de la keynote) | [GeoWeek News](https://www.geoweeknews.com/articles/apple-debuts-its-own-api-for-reality-capture-and-3d-object-creation-but-where-s-the-lidar/); [InfoQ](https://www.infoq.com/news/2021/06/arkit-5-realitykit-2/) |
| 2025 (WWDC25) | Sesión "What's new in RealityKit" (ARKit data vía RealityKit, manipulación de objetos); no se encontraron cambios anunciados en Object Capture. | SECUNDARIO | [WWDC25 session 287 index](https://nonstrict.eu/wwdcindex/wwdc2025/287/) |
| 2025 (visionOS 26) | Elemento HTML `<model>` para ver modelos 3D en páginas web en Safari de visionOS 26. La página de Quick Look sigue activa en developer.apple.com y lista Vision Pro entre los dispositivos con Quick Look para USDZ. | CONFIRMADO | [Apple AR Quick Look gallery](https://developer.apple.com/augmented-reality/quick-look/usdz/); [Apple ARKit gallery](https://developer.apple.com/arkit/gallery) |
| jun-2026 (WWDC26, sesión 204) → sep-2026 (Safari 27 / iOS 27) | `<model>` llega a iOS, iPadOS y macOS; acepta USDZ **o glTF** (varios `<source>`), `environmentmap` HDR, API JS de reproducción; se recomienda `<img>` de fallback; Chrome y Firefox no lo implementan. Safari 27: 83 nuevas funciones, 844 correcciones. | CONFIRMADO (sesión Apple) · SECUNDARIO (detalles) | [Apple WWDC26 session 204](https://developer.apple.com/videos/play/wwdc2026/204/); [Cinevva, 17-sep-2026](https://app.cinevva.com/news/2026-09-17-safari-27-model-element-webgpu-clip-planes); [Blake Crosley](https://blakecrosley.com/es/blog/html-model-element-apple-platforms) |
| nov-2026 | **No se encontró ningún aviso de deprecación de USDZ ni de AR Quick Look**, ni ningún anuncio de "shopping AR" en Safari/Apple Pay posterior a 2020. | CONFIRMADO (ausencia) | búsquedas en developer.apple.com y prensa; ver fuentes anteriores |

### Inferences
- Apple reduce el coste de *mostrar* 3D (un `<model>` nativo sin JavaScript de terceros) pero no el de *producir* el modelo. Para un plugin, el `<model>` nativo es una amenaza a la capa "visor" (la parte más commodity) y una oportunidad para la capa "modelo".
- Que `<model>` acepte glTF además de USDZ reduce la fricción histórica de convertir a USDZ para iOS: un pipeline que solo produzca GLB podrá servir a Safari 27+ sin conversión. Esto rebaja aún más la barrera de entrada para competidores.
- Apple no ha movido Object Capture hacia "foto única → modelo"; sigue siendo fotogrametría multi-imagen orientada a desarrolladores. No es un sustituto directo de un pipeline generativo.

### Gaps
- No se recuperaron las notas oficiales de WebKit para Safari 27 (solo cobertura secundaria y el índice de la sesión WWDC26).
- Cuota de uso de AR Quick Look en e-commerce: Apple nunca la ha publicado.
- No se investigaron específicamente las funciones de imagen de Apple Intelligence (Image Playground) para "producto en mi casa"; no apareció nada relevante en las búsquedas.

---

## 4. Amazon y marketplaces (Wayfair, IKEA, Temu/AliExpress, Otto, Zalando): ¿regalan el 3D y la visualización?

### Takeaway
Amazon ofrece 3D/AR **gratis** a vendedores ("no cost for adding 3D models and AR"), con escaneo desde la app Seller (iOS) y proveedores certificados, y en enero de 2025 sustituyó las imágenes 360° por GLB; pero **no genera modelos 3D a partir de fotos para el vendedor** (la asociación con Hexa es para su propio catálogo y no se encontró como herramienta de Seller Central). Los grandes del hogar han pivotado de AR-3D a generativo 2D: Wayfair retiró Decorify (foto de habitación) por Muse (feb-2025), Pinterest lanza Restyle (sep-2026) y Meta Muse Image (jul-2026). No se encontró nada específico de Temu/AliExpress/Otto/Zalando.

### Cited Findings

#### Amazon

| Fecha | Hecho | Estado | Fuente |
|---|---|---|---|
| Vigente (nov-2026) | Página oficial: "There is no cost for adding 3D models and augmented reality to your Amazon product listings". Tres vías: subir GLB vía Image Manager, contratar proveedor del Service Provider Network ("3D Product Modeling"), o escanear con "Create 3D Models" en la app Amazon Seller. Categorías: View in 3D (zapatos, gafas, muebles, juguetes, electrónica), View in Your Room (muebles, decoración, pared), Virtual Try-On (zapatos, gafas). **No menciona IA foto→3D.** | CONFIRMADO | [Amazon – 3D models and AR](https://sell.amazon.com/tools/3d-ar) |
| 2024 (sin fecha exacta) | Foro de vendedores: "Generate 3D models for free with iOS mobile scanning" para vendedores con Brand Registry en EE. UU.; un blog añade que el procesado "es gratis solo por tiempo limitado" y requiere aprobación. | SECUNDARIO | [Seller Forums](https://sellercentral.amazon.com/seller-forums/discussions/t/33bb149b-1dfb-4334-ac37-410137358732); [Emplicit](https://emplicit.co/3d-content-on-amazon-listings/) |
| 2024 | VNTANA primer integrador de la "3D Publishing API" de Amazon; Nextech3D.ai certificado como proveedor externo de 3D. | CONFIRMADO (notas de prensa de las empresas) | [PRWeb – VNTANA](https://www.prweb.com/releases/vntana-brings-3d-assets-at-scale-to-amazoncom-as-the-first-to-integrate-with-amazons-3d-publishing-api-302173964.html); [Nasdaq – Nextech3D.ai](https://www.nasdaq.com/press-release/nextech3dai-certified-amazons-3d-model-external-content-provider-poised-major-growth) |
| sin fecha | Amazon añade 3D a fichas mediante Hexa (Tel Aviv), que convierte 2D→3D con IA, para su propio catálogo. | SECUNDARIO | [Chain Store Age](https://chainstoreage.com/amazon-partners-ai-based-visualization-platform); [HomePage News](https://homepagenews.com/retail-articles/amazon-offering-marketplace-partners-3d-visuals-via-hexa) |
| 10-dic-2024 | Amazon: reconocimiento de habitación con IA y visualización multi-producto en View in Your Room. | SECUNDARIO | [AR Insider](https://arinsider.co/2024/12/10/whats-next-in-e-commerce-amazons-3d-breakthrough-sets-a-new-standard/) |
| 20-ene-2025 | Amazon discontinúa el 360° Product View; GLB pasa a alimentar View in 3D y View in Your Room. | SECUNDARIO (PR de VNTANA / blogs de proveedores) | [CGI Furniture](https://cgifurniture.com/blog/amazon-3d-product-view-360-vs-ar/) |
| 2023 (citado por proveedores) | "Estudio de Amazon": +9 % de ventas medias con View in Your Room activado. No se localizó la fuente primaria. | NO CONFIRMADO | [CGI Furniture](https://cgifurniture.com/blog/amazon-glb-model/) |
| 3-mar-2026 | Amazon lanza "canvas" agéntico en Seller Central (dashboards por prompt) gratis en US/UK. Un medio afirma que genera fotos lifestyle desde una foto de producto; el resto lo describe solo como analítica → probable confusión. | CONFIRMADO (canvas analítico) · NO CONFIRMADO (imágenes) | [About Amazon](https://www.aboutamazon.com/news/innovation-at-amazon/amazon-sellers-canvas-artificial-intelligence); [WebProNews](https://www.webpronews.com/amazon-bets-big-on-ai-generated-product-images-challenging-sellers-to-rethink-how-they-sell-online/) |
| 2024–2026 | Generador de imágenes IA gratuito en la consola de Amazon Ads (US, CA, FR, DE, IT, MX, ES, UK) para creatividades lifestyle 2D. | CONFIRMADO | [Amazon Ads](https://advertising.amazon.com/resources/whats-new/ai-image-generator-page-now-available-in-amazon-advertising-console) |
| 2026 | Amazon exige etiquetar personas generadas por IA en listados tras ley de Nueva York. | SECUNDARIO | [IADS](https://www.iads.org/member/news/amazon-cracks-down-on-use-of-ai-images-by-sellers-after-new-york-law) |

#### Wayfair, IKEA, Pinterest, Meta

| Fecha | Hecho | Estado | Fuente |
|---|---|---|---|
| 22-jun-2022 | IKEA Kreativ (Ingka): escáner de escena para crear réplica 3D de tu habitación, iOS/desktop en EE. UU.; limitado al catálogo IKEA US según roundups 2026. **No se encontró ningún dato de adopción 2025-2026.** | SECUNDARIO | [Decor8 roundup 2026](https://blog.decor8.ai/post/the-12-best-ai-powered-interior-design-tools-for-2026); [VRScout](https://vrscout.com/news/you-can-now-delete-your-furniture-using-ikeas-ar-app) |
| 2023 | Wayfair Decorify: foto de habitación → imágenes fotorrealistas shoppables (generativo); "175.000 diseños" acumulados. | CONFIRMADO (Wayfair) | [About Wayfair](https://www.aboutwayfair.com/category/company-news/wayfair-launches-decorify-a-virtual-room-styler-powered-by-generative-ai) |
| 11-feb-2025 | Wayfair lanza Muse y **retira Decorify**; Muse genera escenas desde texto (no desde la foto del usuario) y enlaza productos. Crítica de Business of Home (28-mar-2025): "it's not really a design tool, it's an inspiration engine"; no vincula con precisión a SKUs reales. | CONFIRMADO (PR Wayfair) · SECUNDARIO (análisis) | [Wayfair PR](https://s24.q4cdn.com/589059658/files/doc_news/Wayfair-Introduces-New-AI-Powered-Tool-Muse-to-Inspire-and-Personalize-the-Home-Shopping-Experience-2025.pdf); [Furniture Today](https://www.furnituretoday.com/e-commerce/wayfair-retools-its-consumer-ideation-experience-replacing-decorify-with-muse); [Business of Home](https://businessofhome.com/articles/wayfair-s-new-tool-shows-ai-s-strengths-and-limitations.html) |
| 9-jul-2026 | Meta: visualización de habitación con IA sobre Muse Image; el comprador sube foto de su espacio y Meta AI coloca productos del catálogo de la marca (mismo feed que los anuncios); compra en la web de la marca. Sin mención a 3D/AR. | CONFIRMADO (Retail Dive sobre anuncio Meta) | [Retail Dive](https://www.retaildive.com/news/meta-muse-image-ai-powered-room-visualization-feature/824841/) |
| 17-sep-2026 | Pinterest Restyle (beta US/CA; rollout oct-2026): foto de tu habitación → añadir/sustituir muebles y decoración, incluidos los de Pins; cambiar luz/pintura/estilo. Sustituye en la práctica a "Try On for Home Décor" (AR con cámara, 2022). | CONFIRMADO (TechCrunch) | [TechCrunch](https://techcrunch.com/2026/09/17/pinterest-teases-a-new-restyle-feature-that-lets-you-redesign-your-room-with-ai/); [Furniture Today – AR 2022](https://www.furnituretoday.com/technology/pinterest-adds-new-ar-feature-for-home-decor) |
| 2026 | Temu / AliExpress / Otto / Zalando: **no se encontró ninguna noticia** sobre visualización de habitación con IA o AR en 2026. | GAP | — |

#### ¿Le importa a la pyme?
- Un análisis de eMarketer (ene-2025) sobre datos de ene-2024: el 66 % de los adultos de EE. UU. "no conoce, no ha usado o no le interesa" las apps de compra con AR; otro gráfico: casi el 40 % no ha usado AR/VR para comprar pero le interesaría. Titular de eMarketer: "AR shopping stalls in standalone apps" (contenido tras paywall, HTTP 403). — [eMarketer chart](https://www.emarketer.com/chart/c/358176/nearly-40-of-online-consumers-havent-used-arvr-shopping-interested-trying-358176); [eMarketer article](https://www.emarketer.com/content/ar-shopping-stalls-standalone-apps) **[SECUNDARIO]**
- Clutch, 17-mar-2026: "58 % de los consumidores ha comprado tras usar AR" (solo titular; metodología no vista). — [BusinessWire](https://www.businesswire.com/news/home/20260317918865/en/Clutch-Report-58-of-Consumers-Have-Made-a-Purchase-After-Using-Augmented-Reality) **[NO CONFIRMADO]**
- Ya existen apps Shopify de "ver en mi habitación" **sin modelo 3D** (composición 2D desde la foto de producto): "My Room Visualiser" ("no 3D models, no AR app, every product covered from day one"), extensión Chrome Roomcanvas. — [Shopify App Store](https://apps.shopify.com/my-room-visualiser); [Chromeboard](https://www.chromeboard.com/extension/roomcanvas-see-furniture-mooiablnlplhkibihmkdenjjhoelhkjm) **[CONFIRMADO listados]**

### Inferences
- Amazon demuestra que un marketplace con escala puede ofrecer 3D/AR gratis y aun así depender de que el vendedor escanee o pague a un proveedor: la producción del modelo sigue siendo el cuello de botella, no el visor. Eso es exactamente lo que un plugin foto→3D vende; pero si Amazon activara la vía Hexa (2D→3D) para vendedores, el precedente de "gratis" sería inmediato.
- La trayectoria Decorify→Muse (Wayfair), Try On→Restyle (Pinterest) y Muse Image (Meta) muestra que los jugadores con más datos de muebles han concluido que **la imagen generativa en la foto del cliente convierte mejor que el AR en tiempo real**, o al menos es más barata de escalar a todo el catálogo. Un marketplace con millones de SKU no puede modelar todo en 3D; una pyme con 300 SKU sí podría — es el único hueco del argumento.
- Para la pyme española, las funciones de Amazon/Wayfair/IKEA no están disponibles en su tienda propia; la pregunta es si su cliente *espera* la función. Los datos de eMarketer sugieren que la demanda de AR es minoritaria y que la "expectativa" la fijarán Google AI Mode, Meta y Pinterest con imágenes 2D, no con AR.

### Gaps
- No hay fuente primaria del "+9 % de ventas" de Amazon ni de métricas de uso de View in Your Room.
- Estado actual (2026) y mercados de IKEA Kreativ: sin datos; el informe anual FY25 de Ingka no fue revisado.
- Temu, AliExpress, Otto, Zalando: sin resultados; requeriría búsqueda directa en sus newsroom.
- No se encontró ninguna encuesta 2025-2026 específica sobre uso de AR para comprar muebles en España/UE.

---

## 5. Sustitución por IA generativa 2D y comercio agéntico: ¿se ve el botón AR cuando compra un agente?

### Takeaway
La evidencia de 2025-2026 es consistente: las superficies de descubrimiento (Google AI Mode, Meta AI, Pinterest, Gemini/Nano Banana, Wayfair) han estandarizado el "producto en la foto de tu habitación" como imagen generada, no como AR con malla 3D. En comercio agéntico, OpenAI retiró Instant Checkout en marzo de 2026 tras ~12–30 comerciantes activos y Shopify devolvió el checkout a la tienda del comerciante (Agentic Storefronts, 24-mar-2026): el agente descubre y el usuario aterriza en la ficha para pagar, así que el visor 3D/AR **sí puede verse, pero solo en el último paso y sin influir en la selección**, que la hace el agente con texto e imágenes 2D.

### Cited Findings

#### Sustitución 2D generativa (ver tablas de §2 y §4 para fechas)
- Google, 25-ago-2026: subir foto de la habitación a AI Mode y obtener "a mockup right in your space" de un sofá concreto; búsquedas "home decor inspo" +300 % en un mes. — [Google Keyword](https://blog.google/products-and-platforms/products/search/home-decor-tips/) **[CONFIRMADO]**
- Meta, 9-jul-2026: Muse Image coloca productos del catálogo de la marca en la foto del comprador. — [Retail Dive](https://www.retaildive.com/news/meta-muse-image-ai-powered-room-visualization-feature/824841/) **[CONFIRMADO]**
- Pinterest Restyle, 17-sep-2026, sustituye en la práctica el AR de 2022. — [TechCrunch](https://techcrunch.com/2026/09/17/pinterest-teases-a-new-restyle-feature-that-lets-you-redesign-your-room-with-ai/) **[CONFIRMADO]**
- Wayfair, 11-feb-2025: Decorify (foto del usuario) → Muse (texto → escena); 175.000 diseños en Decorify. — [Furniture Today](https://www.furnituretoday.com/e-commerce/wayfair-retools-its-consumer-ideation-experience-replacing-decorify-with-muse) **[CONFIRMADO]**
- Gemini/Nano Banana como herramienta de consumo para "ver muebles en mi habitación", con límites de proporción y textura señalados por reseñas. — [House Digest](https://www.housedigest.com/2009670/ai-diy-tool-google-gemini-nano-banana) **[SECUNDARIO]**
- Limitación del 2D generativo frente al 3D: Business of Home sobre Muse: no vincula con precisión a SKUs reales; reseñas de Nano Banana: "proporciones de muebles derivan". — [Business of Home](https://businessofhome.com/articles/wayfair-s-new-tool-shows-ai-s-strengths-and-limitations.html); [ai-room-designer review](https://ai-room-designer.pages.dev/blog/nano-banana-pro-just-changed-interior-design/) **[SECUNDARIO]**

#### Comercio agéntico — línea temporal

| Fecha | Hecho | Estado | Fuente |
|---|---|---|---|
| sep-2025 | OpenAI + Stripe: Agentic Commerce Protocol (ACP) open-source; Instant Checkout en ChatGPT. | SECUNDARIO | [Idukki](https://idukki.io/blog/agentic-checkout-explained-acp-and-instant-checkout.md) |
| ene-2026 | Google Universal Commerce Protocol (UCP) con Walmart, Target, Shopify, 20+ socios; AP2 como capa de mandatos. | SECUNDARIO | [AskPhill](https://askphill.com/blogs/blog/agentic-commerce-for-shopify-protocols-platforms-and-what-to-prioritize-in-2026) |
| ene–mar-2026 | OpenAI cobra 4 % por transacción en Instant Checkout. | SECUNDARIO | [EcomCrew](https://www.ecomcrew.com/openai-pulls-back-on-chatgpt-instant-checkout/) |
| 16-feb-2026 | "Buy it in ChatGPT" abierto a todos los usuarios de EE. UU. (una fuente). | NO CONFIRMADO | [Pulse](https://www.pulse.bot/ecommerce/news/shopify-launches-agentic-storefronts-in-chatgpt-as-openai-shifts-away-from-native-instant-checkout-30a7b347-6e66-497d-96c0-0f7f54033bef/) |
| 4/6/20-mar-2026 (fechas discrepan) | OpenAI retira Instant Checkout nativo; el checkout vuelve al sitio del comerciante; "la primera versión no ofrecía la flexibilidad deseada". Adopción: ~12 comerciantes activos (un medio) o ~30 comerciantes Shopify a feb-2026 (Forrester). | SECUNDARIO (múltiples fuentes; sin post primario de OpenAI) | [EcomCrew](https://www.ecomcrew.com/openai-pulls-back-on-chatgpt-instant-checkout/); [Forrester blog](https://www.forrester.com/blogs/what-it-means-that-the-leader-in-agentic-commerce-just-pulled-back/embed/); [Spree Commerce](https://spreecommerce.org/openai-just-blinked-nobody-seems-to-want-to-shop-inside-chatgpt/) |
| 24-mar-2026 | Shopify Agentic Storefronts: activado por defecto para comerciantes elegibles (EE. UU.); descubrimiento en ChatGPT, Copilot, Google AI Mode y Gemini; **la compra se completa en la tienda del comerciante**; sin comisiones adicionales; pedidos atribuidos a IA ×11 entre ene-2025 y mar-2026. Cifras de tiendas discrepan (4,8 M vs 5,6 M). | SECUNDARIO | [TrueProfit](https://trueprofit.io/blog/shopify-agentic-storefronts); [Doolpa](https://doolpa.com/news/shopify-agentic-storefronts-live-chatgpt-copilot-gemini-march-2026); [Weaverse](https://studio.weaverse.io/blogs/shopify-agentic-storefront-is-live-in-chatgpt-heres-what-developers-need-to-do-this-week) |

### Inferences
- En el modelo que ha sobrevivido (descubrimiento en el agente, pago en la tienda), el agente selecciona con los datos estructurados del catálogo (texto, atributos, imágenes 2D, precio). Un GLB/USDZ **no es un input que hoy consuman ChatGPT, Gemini o Copilot** para rankear productos. El 3D/AR solo aporta valor si el usuario llega a la ficha y decide interactuar; es un "cierre", no un "descubrimiento".
- La ventaja residual del 3D frente al 2D generativo es la **fidelidad dimensional** ("true-to-scale") y la **coherencia con el SKU real** — justo lo que critican de Muse y Nano Banana. Pero esa ventaja solo se monetiza si el consumidor la percibe y si los retornos por "no cabe / no era así" son un dolor cuantificado para la tienda. No se encontró evidencia de que los consumidores prefieran AR a mockups 2D.
- Los grandes publican mockups 2D porque escalan a todo el catálogo sin coste de modelado; un plugin foto→3D compite por el mismo "job to be done" con un coste marginal mayor y una experiencia que requiere más pasos (abrir AR, apuntar al suelo). A 24 meses es más probable que el 2D generativo mejore en escala y fidelidad (modelos con control de dimensiones) que que el AR gane adopción masiva.

### Gaps
- No se encontró ningún dato cuantitativo (A/B) que compare conversión de AR-3D vs. mockup 2D generativo en muebles.
- No se recuperó el post oficial de OpenAI ni el del newsroom de Shopify sobre Agentic Storefronts; las cifras de adopción (12 vs 30 comerciantes) son de prensa/analistas.
- Perplexity shopping: no se investigó específicamente por límite de llamadas.
- Disponibilidad de Agentic Storefronts para comerciantes de España (la mayoría de fuentes hablan de "eligible US merchants").

---

## 6. Comoditización open-source y competidores: ¿cuánto cuesta replicar "foto → 3D → AR" hoy?

### Takeaway
El pipeline completo se puede montar en semanas con componentes gratuitos o casi: visor (`<model-viewer>` de Google, `<model>` de Apple, Three.js/R3F), AR nativo (Quick Look + Scene Viewer, sin SDK), generación (TRELLIS.2 MIT con 24 GB VRAM; APIs hosted a 0,10–0,60 $/modelo texturizado) y WebAR avanzado (8th Wall open-source MIT desde mar-2026). Ya hay competidores directos en Shopify con generación IA desde fotos (Visuality lanzado 21-may-2026, desde 32,99 $/mes; Insiti lanzado 20-may-2026, plan gratuito hasta 3 productos, Creator 22 $/mes; 3Dify gratis 3 generaciones/mes). Gotcha clave: las licencias Hunyuan3D 2.x **excluyen la UE**.

### Cited Findings

#### Modelos de generación 3D (2025–2026)

| Fecha | Modelo | Licencia / acceso | VRAM | Fuente |
|---|---|---|---|---|
| 21-ene-2025 | Hunyuan3D 2.0 (Tencent) | Pesos abiertos, "Community License" — **excluye UE, UK y Corea del Sur** | 6 GB forma / 16 GB con textura | [Cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026) |
| 25-mar-2025 | TRELLIS (Microsoft) text models | MIT | — | [Cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026) |
| 13-jun-2025 | Hunyuan3D 2.1 (forma 3,3B + PBR 2B) | Community License (excluye UE; tope 1 M MAU) | 10/21/29 GB | [Cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026) |
| 16-sep-2025 | Hunyuan 3D 3.0 | **Solo hosted** (Tencent Cloud API), sin pesos | — | [Cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026) |
| 19-nov-2025 | SAM 3D Objects (Meta) | Abierto, SAM License | — | [Cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026) |
| 16-dic-2025 | **TRELLIS.2 (4B, Microsoft)** | **MIT** | 24 GB mín. | [Cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026) |
| 28-ene-2026 | Hunyuan 3D 3.1 (plataforma global) | Hosted; 20 generaciones gratis/día | — | [Cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026) |
| 9-mar-2026 | Tripo P1.0 / H3.1 | Hosted, pago para uso comercial | — | [Cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026) |
| may/sep-2026 | Pixal3D (Tencent ARC) + multi-view | **MIT** (única apertura notable de 2026) | modo low-VRAM | [Cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026) |
| 12-ago-2026 | Meshy 7 | Hosted; descarga requiere Pro+ | — | [Cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026) |

Nota: la tabla procede de una sola fuente agregadora (Cinevva, con producto propio); los hitos de TRELLIS.2 (MIT) y de licencias Hunyuan deberían verificarse en GitHub/Hugging Face. **[SECUNDARIO]**

#### Coste por modelo vía API (nov-2026, fuentes de terceros, discrepantes)
- Meshy: créditos; imagen→3D 20–30 créditos; a 20 $/1.000 créditos (Pro) ≈ **0,40–0,60 $/modelo texturizado**; una guía dice que la API exige plan Business de 120 $/mes. — [ModelsLab comparison](https://modelslab.com/meshy-api-alternative); [Sloyd price comparison](https://sloyd.ai/blog/3d-ai-price-comparison) **[SECUNDARIO]**
- Tripo: 1 crédito = 0,01 $; imagen→3D 20 (30 texturizado) ≈ **0,10–0,30 $/modelo**; otra fuente (Runware) ≈ 0,50–0,60 $. — [ModelsLab](https://modelslab.com/meshy-api-alternative); [3D AI Studio](https://www.3daistudio.com/blog/best-3d-model-generation-apis-2026) **[SECUNDARIO]**
- ModelsLab (vendedor con API propia a 0,075 $/modelo) es la fuente de varias comparativas: sesgo evidente. **[SECUNDARIO]**

#### Visor y AR web
- `<model-viewer>` (Google) es lo que Shopify activa nativamente al subir un GLB; Scene Viewer (Android) y Quick Look (iOS) no requieren SDK. — [Shopify Help – 3D models](https://help.shopify.com/en/manual/products/product-media/3d-models); [Google Scene Viewer docs](https://developers.google.com/ar/develop/scene-viewer) **[CONFIRMADO]**
- `<model>` nativo en Safari 27 / iOS 27 (otoño 2026) acepta USDZ y glTF. — [Apple WWDC26 204](https://developer.apple.com/videos/play/wwdc2026/204/) **[CONFIRMADO]**
- 10-mar-2026: Niantic Spatial libera el framework de 8th Wall bajo **MIT**; SLAM como binario con licencia comercial/no comercial; VPS, Maps y Hand Tracking excluidos; servicios hosted (editor cloud, Studio) cerrados. — [Road to VR](https://www.roadtovr.com/niantic-webar-platform-8th-wall-open-source/); [Niantic Spatial blog](https://info.nianticspatial.com/blog/8th-wall-update-engine-distribution-and-open-source-plans) **[CONFIRMADO]**

#### Competidores que ya venden foto→3D→AR en Shopify
- **Visuality** (Inside Learning, Francia): "generate a model from a simple photo with AI on visuality.fr"; bloque de tema sin código; plan gratuito; Bronze 32,99 $/mes, Silver 42,99 $, Gold 64,99 $; listado lanzado 21-may-2026; 26 reseñas 5,0. — [Shopify App Store – Visuality](https://apps.shopify.com/visuality) **[CONFIRMADO listado]**
- **Insiti 3D & Augmented Reality** (Insiti.io): "turns the photos you already have into 3D models"; escala real con Quick Look / Scene Viewer / QR desktop; add-to-cart en el visor; eventos de embudo; plan gratuito hasta 3 productos en AR; Creator 22 $/mes; lanzado 20-may-2026; 2 reseñas. — [Shopify App Store – Insiti](https://apps.shopify.com/insiti-ar-viewer) **[CONFIRMADO listado]**
- **Zakeke**: configurador 2D/3D + AR + try-on, con comisión 1,7–1,9 % por venta; no es foto→3D. — [Shopify App Store – Zakeke](https://apps.shopify.com/zakeke-interactive-product-designer?locale=sv) **[CONFIRMADO listado]**
- 3Dify, AI 3D Model Generator, FreakoutAI, spacecheck, Instant 3D: ver §1. Herramientas standalone que exportan GLB/USDZ para subir a Shopify: Neural4D, Sloyd, Meshy, Alpha3D, Luma. — [Shopify for Small Brands](https://shopifyforsmallbrands.com/blog/best-ai-3d-model-generators-for-ecommerce) **[SECUNDARIO]**
- Angle 3D y SwiftXR: no se investigaron por límite de llamadas (gap).

### Inferences
- Coste marginal de producir un modelo vía API hosted: 0,10–0,60 $. Un catálogo de 500 muebles cuesta 50–300 $ en inferencia bruta (sin QA humano). Cualquier precio mensual "por número de productos" tiene que justificarse con **control de calidad, escala dimensional verificada, variantes/materiales y soporte**, no con la generación en sí.
- La exclusión de la UE en las licencias Hunyuan3D 2.x es relevante para un vendedor español: obliga a TRELLIS.2 (MIT, 24 GB VRAM) / Pixal3D, o a APIs hosted (dependencia de un tercero que puede subir precios o cerrar descargas, como Meshy 7 "Pro+ para descargar").
- Que Visuality e Insiti hayan lanzado en la misma semana de mayo de 2026 con planes gratuitos y precios de 22–65 $/mes indica que la ventana de "primero en Shopify con IA foto→3D" ya se cerró; la diferenciación tendrá que venir de vertical (muebles a escala), multi-plataforma (WooCommerce/PrestaShop, donde hay menos competencia) o del dato (analítica de uso AR → conversión/devoluciones).

### Gaps
- No se verificaron los READMEs de TRELLIS.2 / Hunyuan3D en GitHub (fuente única agregadora).
- Precios oficiales de Meshy/Tripo (docs.meshy.ai, docs.tripo3d.ai) no consultados directamente.
- Angle 3D, SwiftXR, Cubic y la calidad real foto única→malla "true-to-scale" de Visuality/Insiti: sin evidencia independiente.
- Competencia en WooCommerce/PrestaShop no analizada.

---

## 7. Regulación y otros riesgos: AI Act (Art. 50), protección del consumidor, accesibilidad (EAA), Core Web Vitals

### Takeaway
Desde el 2 de agosto de 2026 aplican las obligaciones de transparencia del AI Act (Art. 50): marcado legible por máquina de salidas sintéticas (para sistemas ya en mercado, prórroga hasta el 2 de diciembre de 2026) y la guía de la Comisión considera *deepfake* una imagen publicitaria generada por IA "capaz de inducir a error sobre la apariencia real, características o uso del producto"; multas hasta 15 M€ o 3 % de la facturación. La EAA aplica desde el 28 de junio de 2025 (EN 301 549 / WCAG 2.1 AA) pero no hay guía específica para visores 3D/canvas. En rendimiento, los visores 3D son "lo más pesado de la página" y afectan LCP/CLS si no se cargan de forma progresiva; los umbrales de Google son LCP ≤ 2,5 s, INP ≤ 200 ms, CLS ≤ 0,1.

### Cited Findings

#### AI Act – Artículo 50
- Aplicación desde el 2-ago-2026; proveedores de sistemas que generan imagen/audio/vídeo/texto sintético deben marcar las salidas de forma legible por máquina y ofrecer detección; deployers deben revelar deepfakes; **prórroga hasta el 2-dic-2026 solo para la obligación de marcado de sistemas ya en el mercado**; multas hasta 15 M€ o 3 % de facturación mundial; sin efecto retroactivo sobre contenido anterior al 2-ago-2026. — [Cooley, 3-ago-2026](https://www.cooley.com/news/insight/2026/2026-08-03-eu-ai-act-transparency-obligations-take-effect-2-august-2026) **[SECUNDARIO – despacho jurídico]**
- Otras fuentes afirman que las obligaciones aplican de inmediato a todos los sistemas; el conflicto sobre la prórroga debe resolverse con el DOUE/guía de la Comisión. — [Harper Macleod](https://www.harpermacleod.co.uk/insights/eu-ai-transparency-rules-now-in-force/); [Mondaq](https://www.mondaq.com/data-protection/1827450/show-me-the-ai-the-eu-ai-acts-transparency-obligations-now-apply) **[SECUNDARIO]**
- La Comisión publicó directrices, un Código de Buenas Prácticas voluntario e iconos de etiquetado en cuatro variantes. — [Akin Gump](https://www.akingump.com/en/insights/ai-law-and-regulation-tracker/guidelines-on-transparency-obligations-under-the-eu-ai-act) **[SECUNDARIO]**
- Guía de la Comisión según despacho alemán: "an AI-generated advertising image is a deepfake if it is capable of misleading the viewer as to the actual appearance, characteristics or use of the product" → etiquetado obligatorio en retail online desde ago-2026. — [GvW, ago-2026](https://www.gvw.com/en/news/blog/detail/ai-generated-content-in-online-retail-new-labelling-requirements-for-deepfakes-from-august-2026) **[SECUNDARIO]**
- Aplicación a fotografía de producto / moda: análisis sectoriales sobre el 2-ago-2026. — [Graswald](https://www.graswald.ai/blog/the-eu-ai-act-and-ai-generated-fashion-imagery-what-you-need-to-know-before-2nd-august-2026); [Marszal Studio](https://marszalstudio.pl/en/eu-ai-act-product-photography-2026/) **[SECUNDARIO]**

#### Protección del consumidor / publicidad engañosa
- Reino Unido, mar-2026: la ASA prohíbe un anuncio de "robot puppy" con contenido IA tras quejas de clientes engañados; a oct-2026 no hay ley británica de etiquetado de imágenes IA, pero aplican las normas de publicidad engañosa. — [STV News](https://news.stv.tv/world/robot-puppy-facebook-ad-banned-as-customers-report-being-misled-by-ai-content) **[SECUNDARIO]**
- Singapur, feb-2026: respuesta parlamentaria — la CPFTA cubre reclamaciones engañosas con contenido IA; "hasta ahora CASE y CCS no han recibido quejas" sobre anuncios engañosos generados con IA. — [MTI Singapore](https://www.mti.gov.sg/newsroom/written-reply-to-pqs-on-regulations-for-advertisements-that-make-false-claims-by-using-ai-generated-images) **[CONFIRMADO]**
- Nigeria (FCCPC), borrador 2026: una brecha material entre la representación IA y el producto real "en apariencia, acabado, dimensiones o embalaje" puede ser engañosa. — [FCCPC draft](https://fccpc.gov.ng/wp-content/uploads/2026/04/FCCPC-Consumer-Protection-Regulations-Guidance-Notes-2026-Exposure-Draft.pdf) **[CONFIRMADO – borrador]**
- EE. UU.: FTC Sección 5 sobre imágenes IA que tergiversan materialmente el producto; Nueva York exige divulgar "synthetic performers" y Amazon obliga a etiquetar personas IA en listados. — [Loeb & Loeb, ago-2026](https://www.loeb.com/en/insights/passle/2026/08/aigenerated-advertising-when-is-disclosure-required-and-when-is-it-not-enough); [IADS](https://www.iads.org/member/news/amazon-cracks-down-on-use-of-ai-images-by-sellers-after-new-york-law) **[SECUNDARIO]**
- Varias fuentes de vendedores citan "multa media FTC de 2,3 M$" y una "sentencia federal del 11-jun-2026": no verificables. — [Rewarx](https://www.rewarx.com/blogs/june-11-2026-ai-liability-changes-ecommerce-sellers) **[NO CONFIRMADO – descartar]**

#### Accesibilidad (EAA)
- La EAA aplica desde el 28-jun-2025 a la mayoría de tiendas online de consumo, incluidas las de fuera de la UE que venden a consumidores de la UE; estándar técnico EN 301 549 (WCAG 2.1 AA; WCAG 2.2 como referencia práctica 2026); transitoria hasta 28-jun-2030 para contratos/servicios anteriores. — [Bird & Bird](https://www.twobirds.com/en/insights/2025/a-guide-to-navigating-the-european-accessibility-act-for-online-retailers-service-providers-and-plat); [Consentmo – Shopify guide](https://www.consentmo.com/blog-posts/european-accessibility-act-shopify-merchants-guide); [NextChapter](https://www.nextchapter-ecommerce.com/en/blog/posts/entrance-into-force-of-the-european-accessibility-act-eaa-/) **[SECUNDARIO]**
- El criterio más aplicable a un visor 3D es WCAG 1.1.1 "Non-text content" (alternativa textual); **ninguna fuente encontrada aborda específicamente visores 3D/canvas/WebGL bajo la EAA**. — [Strix](https://strix.net/en/insights/blog/digital-accessibility-in-e-commerce---what-do-you-need-to-know) **[SECUNDARIO]**

#### Rendimiento / Core Web Vitals
- Umbrales "good": LCP ≤ 2,5 s, INP ≤ 200 ms, CLS ≤ 0,1 (percentil 75). — [Google Search Central](https://developers.google.com/search/docs/appearance/core-web-vitals?hl=ja) **[CONFIRMADO]**
- Cylindo (act. 15-sep-2026): >70 % de compradores de muebles empiezan en móvil; un visor 3D que bloquea el hilo principal eleva LCP, inyectar elementos tras el layout eleva CLS; recomienda decimación de polígonos, texturas WebP/KTX2 y **carga progresiva (imagen estática primero, modelo después)**; un sofá 3D que tarda 8 s en móvil "la mayoría nunca lo verá". — [Cylindo blog](https://blog.cylindo.com/optimizing-3d-viewer-load-speed-for-mobile-first-shoppers) **[SECUNDARIO – vendedor]**
- Guía 2026: "la mayoría de proyectos de visor 3D fallan porque el módulo 3D se convierte en lo más pesado de la página". — [AcquireConvert](https://acquireconvert.com/ai-product-photos/3d-product-viewer) **[SECUNDARIO]**

### Inferences
- Para Site Hassle el AI Act crea dos obligaciones: como *proveedor* (si opera el modelo generativo) marcar las salidas de forma legible por máquina antes del 2-dic-2026; y para sus clientes como *deployers*, el riesgo de que un render 3D/AR que no refleje fielmente el producto se considere "deepfake publicitario". Paradójicamente esto **favorece al 3D a escala real frente al mockup 2D generativo**: un GLB verificado dimensionalmente es más defendible que una imagen de Nano Banana con "proporciones que derivan". Es un argumento comercial, no una barrera.
- La fuente de riesgo de devoluciones/disputas es la fidelidad del modelo (color, acabado, dimensiones); el valor del producto depende de un QA que hoy ningún competidor barato garantiza. No hay datos de reguladores que cuantifiquen quejas por imágenes IA (Singapur: cero quejas a feb-2026).
- La EAA no bloquea visores 3D; exige alternativa textual y operabilidad por teclado. Es un coste de implementación pequeño pero obligatorio para vender a tiendas de la UE.
- Rendimiento: un plugin que inyecte `model-viewer` sin poster/lazy-load en la ficha de producto degrada LCP/CLS de la página más importante para SEO del comerciante; es un riesgo de *churn* del plugin, no regulatorio.

### Gaps
- Texto oficial de la Comisión (directrices Art. 50) no consultado directamente; el criterio "deepfake publicitario" procede de un despacho.
- Ninguna estadística de reguladores de la UE/España sobre quejas o devoluciones atribuibles a imágenes IA.
- Ninguna guía oficial de EAA/W3C encontrada sobre visores 3D/canvas en e-commerce.
- Sin datos de campo (CrUX) sobre el impacto real de `model-viewer` en LCP/INP en tiendas Shopify.

---

## Escenarios a 24 meses (nov-2026 → nov-2028): qué es probable que lance cada plataforma y qué le queda al vendedor de plugins

> Probabilidades son juicio del investigador a partir de las trayectorias documentadas arriba, no datos.

| Plataforma | Lo más probable que lance (24 meses) | Probabilidad | Impacto en un plugin foto→3D→AR | Lo que deja al plugin |
|---|---|---|---|---|
| **Shopify** | Generación de imagen 2D "producto en escena/habitación" en Sidekick/Tinker llevada a la ficha de producto (ya tiene background removal, lifestyle shots, "3D figurine" como imagen). Botón "Generate 3D model" en product media vía API de terceros: posible pero sin señal alguna hoy. Expansión del escáner 3D (hoy solo iPhone Pro). Agentic Storefronts extendido a más países. | 2D en ficha: alta · GLB nativo desde fotos: baja-media · Escáner ampliado: media | Si Shopify añade un botón nativo, el precio del plugin cae a cero en Shopify (precedente escáner 2023). La política de App Store no protege ni expulsa. | Vertical (muebles a escala real, variantes/materiales), QA humano, analítica AR→conversión/devoluciones, WooCommerce/PrestaShop donde Shopify no llega. |
| **Google** | Despliegue internacional de "sube la foto de tu habitación" en AI Mode (lanzado EE. UU. ago-2026); mockups con control dimensional mejorado; agentes que compran vía UCP/AP2. Scene Viewer en mantenimiento (riesgo de sunset bajo-medio; WebXR como sustituto). 3D/AR en Shopping seguirá limitado a 5 países y 2 categorías, sin España. | 2D internacional: alta · Sunset Scene Viewer: baja-media | El consumidor español tendrá "ver en mi salón" gratis en Google sin que la tienda haga nada; la expectativa de AR 3D no se genera desde Google. | Fidelidad dimensional verificada (lo que Google no promete), AR en la propia tienda para el último paso. |
| **Apple** | `<model>` consolidado en iOS 27+ (USDZ y glTF), posible AR desde `<model>`; sin generación de modelos; sin deprecación de Quick Look. | Alta (ya en marcha) | Abarata el visor; el plugin no puede cobrar por "el visor", solo por el modelo y la integración. | Producción y QA de modelos; integración Quick Look + `<model>` + Scene Viewer sin que el comerciante toque código. |
| **Amazon** | Extender la vía Hexa (2D→3D con IA) a vendedores con Brand Registry, probablemente gratis o "gratis por tiempo limitado" como el escaneo; más IA 2D en Ads. Nada de esto llega a la tienda propia del comerciante. | Media | Fija el ancla "el 3D es gratis en el marketplace"; presiona los precios por producto del plugin. | La tienda propia, donde Amazon no está; exportación de GLB del plugin a Amazon/Google como argumento ("un modelo, todos los canales"). |
| **Meta / Pinterest / Wayfair** | Meta Muse Image y Pinterest Restyle a disponibilidad general y a Europa; integración con catálogos de anuncios; Wayfair/IKEA sin volver al AR. | Alta | Normaliza el mockup 2D como estándar de "ver en mi casa"; el AR 3D pasa a ser nicho premium. | Argumento "lo que ves es el SKU real a escala" frente a inspiración 2D; útil solo si el comerciante sufre devoluciones por tamaño/aspecto. |
| **Open source / APIs** | Más pesos MIT (línea TRELLIS/Pixal3D), APIs ≤ 0,10 $/modelo, mejor fidelidad y control de escala desde una foto; competidores Shopify (Visuality, Insiti, 3Dify) añadirán WooCommerce/PrestaShop. | Alta | El coste de replicar el pipeline tiende a cero; el precio "por número de productos" no se sostiene por la generación. | Operación (QA, variantes, re-generación al cambiar fotos), SLA, datos, multi-plataforma, cumplimiento AI Act/EAA empaquetado. |
| **Regulación** | Aplicación plena del marcado Art. 50 (2-dic-2026), primeros casos de "deepfake publicitario" en retail UE, auditorías EAA. | Alta | Coste de cumplimiento para todos; ventaja relativa para 3D fiel frente a 2D generativo. | Un plugin "compliance-ready" (marcado C2PA/metadata, alt-text, teclado) es un diferenciador pequeño pero real en la UE. |

**Conclusión para el consultor:** la tesis "las plataformas y la IA generativa comoditizarán o puentearán el producto" está **bien sustentada en los ejes de comoditización (APIs a céntimos, pesos MIT, ≥6 apps Shopify competidoras con planes gratuitos desde may-2026) y de sustitución 2D (Google ago-2026, Meta jul-2026, Pinterest sep-2026, Wayfair feb-2025)**, y **débil en el eje "Shopify lo hará nativo"** (ninguna señal confirmada a nov-2026; el escáner de 2023 y Tinker apuntan a otra dirección). El hueco defendible que queda no es "foto→3D→AR" como feature, sino **fidelidad dimensional verificada + operación multi-plataforma + cumplimiento UE** para tiendas de muebles con un problema cuantificado de devoluciones; si el emprendedor no puede demostrar ese problema con datos de sus primeros clientes, la ventaja frente a los mockups 2D gratuitos de las plataformas será difícil de vender.
