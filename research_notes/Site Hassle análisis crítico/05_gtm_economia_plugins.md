# Economía del go-to-market de un plugin/SaaS low-ticket (19–99 €/mes) para tiendas pequeñas en Shopify, WooCommerce y PrestaShop (a noviembre de 2026)

> Notas de investigación para el análisis crítico de "Site Hassle" (foto → modelo 3D con IA + botón AR, cobro mensual por nº de productos, primero pymes de mueble/decoración en WooCommerce y PrestaShop en España, luego Shopify, luego Europa). Todas las cifras llevan fecha y fuente; lo que es estimación propia está marcado **[EST]**. Convención: "paying store" = tienda con plan de pago activo.

---

## 1. Economía del Shopify App Store: distribución de ingresos, tiempos, reviews, revenue share, ads, conversión y churn

### Takeaway
El App Store es un mercado de cola ultra-larga: según el único análisis público con datos de 2026 (Barn2, oct-2026), 16 apps se llevan el 40,6 % de los ingresos y la mitad de las apps comparte el 0,6 %; la quinta parte más joven de apps ingresa ~190 $/mes de media. Los benchmarks de operadores sitúan el churn SMB en 3–5 %/mes y la conversión trial→pago en 15–35 %; no existe CPC oficial publicado para App Store Ads y la visibilidad depende cada vez más del badge Built for Shopify (que a Barn2 le costó ~6 meses y 1.000 usuarios gratuitos conseguir).

### Cited Findings

**Tamaño y concentración**
- Shopify reportó en su 10-K >21.000 apps a cierre de 2025 (vs >16.000 un año antes), 21 M de instalaciones de apps en 2025 y >1.300 M$ pagados a desarrolladores en 2025 (dato oficial recogido en fuente secundaria, consultado nov-2026) — [MobiLoud, Shopify Statistics](https://www.mobiloud.com/blog/shopify-statistics/)
- Barn2 (Katie Keith, 19-oct-2026; scrape de 4.438 apps el 7-sep-2026, datos Store Leads 12 meses hasta ago-2026): de 1.675 apps con precio público, **las 16 mayores capturan el 40,6 % de los ingresos, las 83 mayores el 72,2 %, y la mitad inferior se reparte el 0,6 %**. La app "del medio" ingresa 2.500–5.200 $/mes antes de la comisión de Shopify; la mayor ~9 M$/mes (≈2.500× la mediana). El quintil de apps más antiguas ingresa ~19.100 $/mes de media frente a **~190 $/mes el quintil más joven** (rango ajustado 130–280 $). La autora avisa de que el modelo puede errar en un factor 2 en cualquier dirección — [Barn2, "The Average Shopify App Is Doing Worse Than You Think"](https://barn2.com/blog/shopify-app-store-saturation/)
- Barn2, mismo artículo: apps por cada 1.000 tiendas pasaron de 5,5 (jul-2023) a 8,8 (2026); las apps crecen >28 %/año mientras las tiendas crecen 10–14 %/año; **una app típica pierde ~4 tiendas por cada 10 que gana en 12 meses**; la correlación entre nota media y éxito es nula; su propia app tiene 10 reseñas y compite con apps "similares" de 3.526, 4.434 y 411 reseñas; **conseguir el badge Built for Shopify le llevó ~6 meses y ~1.000 usuarios gratuitos** — [Barn2](https://barn2.com/blog/shopify-app-store-saturation/)
- GapQuery (Shawn North, 24-abr-2026, act. 26-may-2026; 13.786 apps): la **mediana de app de pago "probablemente ingresa <1.000 $ MRR"**; top 10 % de una categoría ≈ ≥5.000 $ MRR; top 2 % ≈ 50.000 $; top 1 % ≈ 100.000 $+; **9.539 apps tienen <10 reseñas y "esencialmente no ganan nada"**; 32 % de las apps no tienen plan de pago. Ratio instalaciones:reseña ≈ 30–100:1 (las apps nuevas y agresivas pidiendo reseña ~1:30). Todo son estimaciones por triangulación (precio de entrada × reseñas × conversión), no datos revelados — [GapQuery](https://www.gapquery.com/blog/how-much-do-shopify-apps-make)
- GapQuery no publica qué % de apps supera 1k/10k/100k MRR; Barn2 tampoco. **No existe una fuente pública que lo mida** (ver Gaps).

**Revenue share**
- Documentación oficial Shopify (consultada nov-2026): **0 % sobre el primer 1.000.000 $ de ingresos brutos acumulados (lifetime) por cuenta Partner, 15 % por encima**; el ingreso anterior al 1-ene-2025 no cuenta; cuota única de 19 $ por cuenta Partner; desarrolladores con ≥20 M$/año en App Store o ≥100 M$ de facturación pagan 15 % desde el primer dólar — [shopify.dev, Revenue share](https://shopify.dev/docs/apps/launch/distribution/revenue-share)
- El esquema pasó de "reset anual" (anunciado en 2024, recogido por TechCrunch) a "lifetime" (cambio de 2025) — [Barchart, "Shopify developers lose annual revenue share break"](https://www.barchart.com/story/news/32186933/shopify-developers-lose-annual-revenue-share-break-as-program-moves-to-lifetime-model); [TechCrunch](https://techcrunch.com/?p=2171395)

**Ranking, reviews y cambios 2025–2026**
- Changelog oficial 30-oct-2025: las apps **Built for Shopify** obtienen spotlight en la home del App Store, colocación en páginas de categoría y badges clicables, además del boost de ranking y el filtro de búsqueda ya existentes — [shopify.dev changelog](https://shopify.dev/changelog/posts/built-for-shopify-apps-get-priority-visibility-across-the-shopify-app-store)
- Changelog 17-sep-2025 (citado por Ranksy): el badge BFS mejora el ranking en App Store y en Sidekick (asistente IA); las reseñas incentivadas pueden llevar a demotion o delisting — [Ranksy, App Store Optimization](https://ranksyapp.com/guides/shopify-app-store-optimization)
- Factores de ranking documentados: señales de comportamiento desde feb-2023 (CTR, tasa de instalación, retención post-instalación), BFS como multiplicador, velocidad de reseñas como señal de salud, y "60 % de las instalaciones vienen de búsqueda" (dato Shopify citado por la agencia) — [BigMoves Marketing](https://www.bigmoves.marketing/blog/shopify-app-store-ranking-algorithm-overview-of-shopify-app-store-ranking-factors)
- Hilo de desarrolladores (2025): quejas de que Shopify eliminó cientos de reseñas genuinas al endurecer el tratamiento de reseñas incentivadas/falsas — [Shopify dev community](https://community.shopify.dev/t/serious-concerns-about-the-recent-shopify-app-review-changes/36117)
- Consejo recurrente en foros para las primeras 50–100 instalaciones: outreach founder-a-founder, emails personalizados y soluciones gratis a cambio de feedback; **ninguna fuente da un plazo típico en semanas/meses** — [Shopify Community, "Struggling to get installs"](https://community.shopify.com/t/struggling-to-get-installs-for-a-shopify-app-any-advice/583477)

**App Store Ads**
- Oficial: modelo CPC por subasta, solo Partners con app publicada, presupuesto diario en USD, ubicaciones en búsqueda, categorías y home. **Shopify no publica CPCs** — [shopify.dev, App Store ads](https://shopify.dev/docs/apps/launch/marketing/advertising)
- Única referencia de precio encontrada: rango genérico 0,50–2,00 $/clic para anuncios Shopify de comerciantes (NO específico de App Store Ads ni de la categoría 3D/AR; no sirve como benchmark) — [NestScale](https://nestscale.com/blog/shopify-advertising-costs.html)

**Conversión y churn**
- Benchmark operador (Taylor Sicard, act. jul-2026, datos mayoritariamente 2025): **churn mensual 3–5 % "normal" para apps SMB; <3 % fuerte; >6 % alarma** (6 %/mes = perder >50 % de la base en un año). Trial con tarjeta: 25–35 % sano, <15 % riesgo; freemium sin tarjeta: 3–5 % sano, <2 % riesgo. Payback CAC <12 meses sano, >18 meses alarma. Cita ChartMogul 2026 (~200 productos): opt-in trial ~8,9 %, trial con tarjeta ~31,4 %, freemium ~5,6 % — [Taylor Sicard, Shopify Ecosystem Benchmark Report 2026](https://taylorsicard.com/blog/shopify-ecosystem-benchmark-report-2026)
- Mismo autor en otro post: la app Shopify mediana convierte 15–20 % de instalaciones en trial a pago — [Taylor Sicard, free-to-paid](https://taylorsicard.com/blog/shopify-app-free-to-paid-conversion)
- Fuente discrepante (vendor): churn de apps Shopify "5–12 %/mes" por la facilidad de instalar/desinstalar con un clic — [WeArePresta, 2026](https://wearepresta.com/shopify-churn-rate-the-2026-definitive-strategic-guide-to-merchant-retention/)
- GapQuery asume free→paid 10–30 % en freemium (20 % en sus ejemplos) — [GapQuery](https://www.gapquery.com/blog/how-much-do-shopify-apps-make)
- Un desarrollador de apps encontró que el trial de 7 días maximizaba conversión (un solo dato, no controlado) — [AppJubilee](https://blog.appjubilee.io/free-trial-length-impact-installs/)

**Adquisiciones / múltiplos**
- Listings Acquire.com (consultados nov-2026): suite de apps Shopify, 150k$ ARR / 130k$ beneficio TTM, pedido 2,5× beneficio / 2,2× ingresos — [Acquire.com listing](https://app.acquire.com/public/6icp3do1he-high-margin-shopify-apps-suite-150k-arr-130k-ttm-profit-over-1k-merchants-turnkey-ownership); app CDP pedida a 4,2× beneficio / 3,2× ingresos — [Acquire.com listing](https://app.acquire.com/public/ocgyjfo1t7-a-shopify-app-integrating-a-customer-data-platform-with-shopify); listing Flippa con múltiplo 4,3× ingresos y **churn total 11 %** — [Flippa](https://flippa.com/11991879)
- Guía broker 2026: la mayoría de apps Shopify se venden a 3–5× beneficio neto; el churn reduce el múltiplo — [Taylor Sicard, What Shopify apps sell for](https://taylorsicard.com/blog/what-shopify-apps-sell-for-2026)
- Barn2 revisó 28 listings de venta: 4 anunciaban un ARR >25 % superior al real del año reportado (el peor, +61 %) — [Barn2](https://barn2.com/blog/shopify-app-store-saturation/)

### Inferences
- Para una app nueva de nicho (3D/AR) sin reseñas, el escenario base documentado es el quintil joven de Barn2: **~130–280 $/mes de ingresos durante el primer año**, i.e. 3–6 tiendas de pago a 49 €/mes. Eso es consistente con "9.539 apps con <10 reseñas no ganan nada" (GapQuery).
- Las reglas de 2025–2026 (boost BFS, home spotlight BFS, Sidekick favoreciendo BFS, purga de reseñas incentivadas) hacen que el camino orgánico pase por conseguir BFS, que exige base instalada y meses de trabajo (Barn2: 6 meses + 1.000 usuarios gratis) — incompatible con "founder a tiempo parcial que cobra desde el día 1".
- El 0 % de comisión hasta 1 M$ es irrelevante para el caso: el problema no es la comisión sino el volumen.
- Con churn 5 %/mes (dentro del rango "normal" de 3–5 % y por debajo del 11 % del listing de Flippa), la vida media de un cliente es ~20 meses y el LTV bruto a 49 €/mes ≈ 980 € — pero el LTV neto cae mucho si cada tienda exige producción de modelos (ver §6).

### Gaps
- No existe ningún dato público (Shopify, Marketplace, encuestas) sobre el **% de apps que superan 1k/10k/100k MRR**; solo estimaciones por triangulación (GapQuery, Barn2). Shopify prohíbe a terceros publicar instalaciones/MRR.
- **CPC de App Store Ads en la categoría 3D/AR**: no hay fuente pública; solo se conoce dentro del Partner Dashboard.
- **Tiempo a 100 instalaciones de pago**: ninguna fuente con muestra; solo anécdotas.
- No encontré la encuesta "State of Shopify Apps" ni hilos verificables de Hilal/Nick Disabato con datos de 2025–2026.

---

## 2. Realidad de la monetización en WooCommerce

### Takeaway
WooCommerce no tiene un canal de pago integrado comparable al App Store: el Marketplace oficial deja un 70 % al vendedor y exige aplicación + revisión sin plazos publicados; CodeCanyon pasó a un 50 % plano en jul-2026 y vende licencias one-time; la vía propia (Freemius/Lemon Squeezy) depende de un plugin gratuito en wp.org que convierte a pago típicamente en el 1–5 %. El soporte se multiplica por la fragmentación PHP/hosting/temas (HPOS, Blocks) y la piratería está documentada aunque sin % de mercado fiable.

### Cited Findings
- **WooCommerce Marketplace oficial** (doc consultado nov-2026): modelo de revenue share "con el **70 % de las ventas para el vendedor**"; requiere solicitar cuenta de partner en woocommerce.com/partners, luego enviar el producto a revisión (funcionalidad, seguridad, compatibilidad, UX) con demo e instrucciones de prueba; se exige "modelo de monetización claro y sostenible" (venta directa, suscripciones u otro), mantener/actualizar el producto y dar soporte continuo. Existe una "SaaS Billing API" enlazada, pero **no se publican plazos de aprobación ni estadísticas de tamaño del marketplace** — [developer.woocommerce.com, Woo Marketplace getting started](https://developer.woocommerce.com/docs/woo-marketplace/getting-started/)
- **CodeCanyon/Envato**: desde el 1-jul-2026 Envato retiró el modelo de autor exclusivo por tramos (que llegaba al 87,5 % para el autor) y pasó a **50 % plano** para todos; cuota fija de comprador ~4 $ en plugins WP — [ChargePanda, CodeCanyon alternatives 2026](https://www.chargepanda.com/blog/post/envato-alternatives-wordpress-plugin-authors); [PureThemes](https://purethemes.net/envato-author-exclusivity-merchant-of-record/). Análisis antiguo de Freemius: precio medio de plugin WP en CodeCanyon 18,91 $ y **ingreso neto medio por venta <10 $** tras impuestos (dato de ~2016, desfasado pero indicativo del one-time low-ticket) — [Freemius, CodeCanyon by the numbers](https://freemius.com/blog/codecanyon-wordpress-plugins-analysis/)
- **Conversión freemium**: artículo Freemius (23-jul-2026) recoge benchmarks externos: freemium típico 2–5 % (COO de Aperty, sin fuente), **2,1 % típico en freemium con features bloqueadas y hasta 7,4 % con PLG fuerte** (American Impact Review), 0,9–3,6 % free→paid en 9 meses (Panto AI). **Ninguna de estas cifras es de plugins WordPress** y Freemius no publica su conversión agregada — [Freemius, increase freemium upgrades](https://freemius.com/blog/increase-freemium-upgrades-wordpress-plugin-theme/)
- Freemius: tasa de supervivencia a 3 años del plugin medio del repositorio ~10–20 %; los freemium tienen 200 % más probabilidad de seguir actualizados a 3 años — [Freemius, Freemium plugins outlive free ones](https://freemius.com/blog/freemium-wordpress-plugins-outlive-free-ones/); [Addendio](https://addendio.com/freemium-plugins-200-likely-updated-3-years)
- Freemius, informe de transparencia 2022: 498 productos nuevos hicieron su primera venta ese año; la suscripción anual más cara vendida fue 3.360 $ (no publica ARPU ni renovación) — [Freemius blog](https://freemius.com/blog/?p=11558). Cledara: gasto medio de sus clientes en Freemius 41 $ (muestra propia) — [Cledara](https://www.cledara.com/marketplace/freemius)
- Caso Pootle Pagebuilder: ~9.000 $ en licencias el primer mes con <4.000 instalaciones activas (caso de éxito del propio vendor) — [Freemius](https://freemius.com/blog/success-story-of-pootle-pagebuilder-with-freemius/)
- **Piratería**: estudio USENIX/Georgia Tech citado por prensa: plugins pirateados costaron 228.000 $ a desarrolladores **dentro de su dataset** (no extrapolable al mercado); no existe % de mercado fiable de plugins "nulled" — [CPO Magazine](https://www.cpomagazine.com/?p=27327); [Security Scientist](https://www.securityscientist.net/blog/12-questions-and-answers-about-nulled-plugins-themes-malware-risk/)
- **Carga de compatibilidad (HPOS)**: FooSales dice que su refactor HPOS fue "solo unos días de actualización y pruebas" (página de marketing) — [FooSales](https://www.foosales.com/is-your-store-ready-for-high-performance-order-storage-hpos/); Toolset WooCommerce Blocks siguió "más de un año" marcado incompatible con HPOS — [Toolset forums](https://toolset.com/forums/topic/toolset-woocommerce-blocks-are-thus-far-incompatible-with-hpos); hilos wp.org con avisos de incompatibilidad HPOS/PHP persistentes tras actualizar — [wordpress.org support](https://wordpress.org/support/topic/incompatible-with-latest-php-versions-and-woo-hpos-support/)
- Cuota de WooCommerce en tiendas nuevas en España cayó 1,3 pp en 2025 (ShopRank vía Ecommerce News, 26-feb-2026) — [Ecommerce News EU](https://ecommercenews.eu/shopify-dominant-software-new-stores/)

### Inferences
- Para un SaaS (backend propio que genera 3D), WooCommerce no es un "marketplace de distribución" sino un conector: el patrón de Zakeke/Tidio/Klaviyo es publicar un plugin gratuito en wp.org como integración y cobrar en su propia web — la adquisición ocurre fuera de WordPress (SEO, ads, partners), **no la regala el ecosistema** [EST: inferencia del modelo, no verificada con cada empresa].
- Con 2,1 % de conversión freemium (benchmark no-WP) se necesitan ~4.800 instalaciones activas para 100 tiendas de pago; alcanzar miles de instalaciones activas en wp.org para un plugin de nicho (3D mueble) es un proyecto de SEO/reseñas de 12–24 meses [EST].
- El 30 % del Marketplace Woo + la obligación de soporte y revisión lo hace equivalente en coste a Shopify >1 M$ pero sin el tráfico del App Store.

### Gaps
- No hay datos públicos de **ARPU, renovación o churn de plugins Woo** (Freemius no los publica).
- No encontré el plazo medio de aprobación del Woo Marketplace ni el nº de extensiones listadas.
- No pude documentar con fuentes cómo Zakeke/Tidio/Klaviyo/Smart Product Viewer adquieren usuarios Woo concretamente (solo el patrón general).

---

## 3. PrestaShop Addons y la base PrestaShop en España

### Takeaway
PrestaShop está en contracción clara: Store Leads cuenta 143.062 tiendas activas (nov-2026) frente a 220.112 en el pico de 2022 (−35 %), con −17 % interanual, y solo el 6,4 % de las tiendas nuevas en España de 2025 eligieron PrestaShop (Shopify 41 %). España sigue siendo el 2.º mercado (15.106 tiendas, 10,6 %), pero vender ahí exige pagar 99 €/producto/año de validación en Addons, una comisión no publicada, y soportar la migración 1.7→8→9 (dos saltos de Symfony).

### Cited Findings
- Store Leads (consultado nov-2026): tiendas PrestaShop activas por cierre de año: 2020 188.899 → 2021 218.906 → 2022 215.205 → 2023 213.532 → 2024 191.715 → 2025 170.545 → **2026 (a la fecha) 143.062**; pico 220.112 en 2022-Q3; **−17 % interanual en 2026-Q3**. **Francia 21.575 tiendas (15,1 %), España 15.106 (10,6 %)**, 2.º mercado mundial. Sin desglose de versiones — [Store Leads, PrestaShop report](https://storeleads.app/reports/PrestaShop)
- ShopRank (324.000 tiendas nuevas europeas, 2025; vía Ecommerce News 26-feb-2026): en **España, Shopify 41 % de las tiendas nuevas, PrestaShop 6,4 %**; Francia PrestaShop 5,4 %; Italia 3,9 %. En los 7 mercados: Shopify 148.044 tiendas nuevas, WooCommerce 99.140, **PrestaShop 9.747** — [Ecommerce News EU](https://ecommercenews.eu/shopify-dominant-software-new-stores/)
- Afirmación discrepante de un vendor de servicios PrestaShop: "~30 % de cuota en tiendas pequeñas/medianas en España" citando BuiltWith/Store Leads (finales 2025; conflicto de interés, no conciliable con el 6,4 % de nuevas) — [Velsof](https://www.velsof.com/?p=2245)
- **Addons (docs oficiales, nov-2026)**: Standard Seller requiere cuenta partner profesional, **cuota anual de validación de 99 € por producto**, aceptar términos y **cuenta bancaria europea**; Stripe obligatorio; retención de fondos 45 días; liquidación mensual el día 1. Premium Seller tiene "comisión reducida" (degresiva según facturación) y soporte de un Solution Engineer. Solo los Official Partners pueden distribuir módulos gratuitos. **El % de comisión estándar NO figura en la página**; el plazo de validación tampoco — [docs.cloud.prestashop.com, Getting started](https://docs.cloud.prestashop.com/1-getting-started); [PrestaShop Premium Seller](https://growth.prestashop.com/premium_seller_partnership)
- PrestaShop 9: salto de **dos versiones mayores de Symfony** (a 6.4) con deprecaciones/eliminaciones, cambio de controladores (lo más crítico para módulos), tema Hummingbird en Bootstrap 5 (9.1 → 5.3.3), eliminación de dependencias como Guzzle; recomendación: tiendas 1.6 requieren rebuild limpio, 1.7 deben pasar por 8.2 antes de 9; el Update Assistant 7 marca módulos incompatibles pero "la migración sigue requiriendo pruebas cuidadosas" — [mypresta.rocks, PS9 compatibility](https://mypresta.rocks/blog/prestashop-9-compatibility-all-our-modules-are-ready); [mypresta.rocks, migration guide](https://mypresta.rocks/knowledge-base/guides/prestashop-9-migration); [BelVG](https://belvg.com/blog/prestashop-cache.html); [AGTI](https://blog.agti.eng.br/?p=104)
- Ecosistema de agencias en España (referencia de canal): Marketing4ecommerce lista 5 agencias Shopify Premier Partner y 31 Shopify Plus Partner en España (2026) — [Marketing4ecommerce](https://marketing4ecommerce.net/agencias-shopify-partners-espana/)

### Inferences
- A −17 %/año, la base española de ~15.100 tiendas PrestaShop serían ~12.500 en nov-2027 y ~10.400 en nov-2028 [EST, extrapolación lineal del ritmo global]; el subconjunto mueble/decoración con fotos de producto decentes y presupuesto para un plan de 49 €/mes es una fracción pequeña (sin dato; ver investigación de mercado de otros investigadores).
- El canal Addons añade coste fijo (99 €/año/módulo), ventanas de cobro largas (45 días) y una comisión opaca: para un plan de 49 €/mes recurrente, la fricción administrativa es desproporcionada. Las tiendas PrestaShop en España son alcanzables sobre todo vía agencias/freelancers PrestaShop, que viven precisamente de las migraciones 1.7→8→9 y tienen poco incentivo en un plugin de 49 €/mes [EST].
- Mantener compatibilidad 1.7 + 8 + 9 a la vez (tres ramas de Symfony/Bootstrap) para una base en contracción es la peor relación esfuerzo/mercado de las tres plataformas.

### Gaps
- **Comisión estándar de PrestaShop Addons**: no publicada en las páginas accesibles; el PDF de términos Premium devolvió 404.
- **Volúmenes de venta de los módulos top**: no hay datos públicos.
- Desglose por versión (1.6/1.7/8/9) de la base española: Store Leads no lo muestra en la página pública.

---

## 4. Carga de mantenimiento multiplataforma (Shopify + WooCommerce + PrestaShop)

### Takeaway
Shopify impone una versión de API nueva cada trimestre (soporte 12 meses, delisting si se usan recursos no soportados tras el plazo), obligó GraphQL para apps nuevas desde abr-2025 y cerró checkout.liquid (2024–2025) y Scripts (jun-2026); WooCommerce exige compatibilidad HPOS/Blocks/PHP; PrestaShop 9 rompe módulos por el salto de Symfony. No encontré testimonios cuantificados en horas/mes por plataforma; la evidencia indirecta (Barn2, dev solo con 7 apps) apunta a que los founders en solitario se concentran en una sola plataforma.

### Cited Findings
- **Shopify API versioning** (doc oficial, nov-2026): nueva versión estable **cada 3 meses**; cada versión soportada ≥12 meses con ≥9 meses de solapamiento; a nov-2026 están sin soporte 2025-04/07/10 y la última estable es 2026-10; Shopify recomienda actualizar cada trimestre; la CLI bloquea deploys de extensiones con versión >12 meses; **si una app sigue usando recursos no soportados tras el plazo, se deslista del App Store, se bloquea su instalación ≥7 días y los merchants ven avisos en el admin** — [shopify.dev, Versioning](https://shopify.dev/docs/api/usage/versioning)
- **GraphQL obligatorio**: desde el 1-abr-2025 todas las apps públicas nuevas deben usar solo GraphQL; REST Admin API marcada "legacy"; migración a las nuevas product APIs GraphQL para apps públicas con fecha 1-feb-2025; los plazos de migración de apps existentes "se anunciarán" (no encontré fecha final de apagado REST) — [shopify.dev changelog](https://shopify.dev/changelog/starting-april-2025-new-public-apps-submitted-to-shopify-app-store-must-use-graphql); [Shopify Partners blog, All-in on GraphQL](https://www.shopify.com/partners/blog/all-in-on-graphql)
- **checkout.liquid**: fin de las páginas in-checkout el 13-ago-2024 y de Thank you/Order status el 28-ago-2025 (incluye script tags); Shopify Scripts hasta el 30-jun-2026 → Shopify Functions (fuentes secundarias de vendors) — [Braze docs](https://www.braze.com/docs/help/release_notes/deprecations/shopify_checkout/); [Fudge.ai](https://www.fudge.ai/blog/shopify-checkout-extensibility/)
- Un desarrollador en solitario con 7 apps Shopify (Irlanda) afirma que la revisión de apps se ha endurecido, en particular los webhooks GDPR y los endpoints de cumplimiento obligatorios, "lo que añade overhead para solo devs" — [dev.to, 7 Shopify apps as a solo developer](https://dev.to/jmsdevlab/how-i-built-7-shopify-apps-as-a-solo-developer-in-ireland-2nfp)
- Barn2: badge BFS ≈ 6 meses + 1.000 usuarios gratuitos; mantiene **una** app Shopify como extensión de un negocio WooCommerce consolidado — [Barn2](https://barn2.com/blog/shopify-app-store-saturation/)
- WooCommerce HPOS: "unos pocos días" para un refactor bien estructurado (FooSales) frente a >1 año de incompatibilidad en Toolset; cada vez que un plugin base (p.ej. Subscriptions) declara compatibilidad, las extensiones dependientes deben actualizar — [FooSales](https://www.foosales.com/is-your-store-ready-for-high-performance-order-storage-hpos/); [Toolset forums](https://toolset.com/forums/topic/toolset-woocommerce-blocks-are-thus-far-incompatible-with-hpos); [WooCommerce developer blog archive](https://developer.woocommerce.com/archive/page/27)
- PrestaShop 9: dos saltos de Symfony, cambio de controladores, Bootstrap 5, dependencias eliminadas (ver §3) — [mypresta.rocks](https://mypresta.rocks/blog/prestashop-9-compatibility-all-our-modules-are-ready)
- Guía de costes de apps Shopify: tarifas de desarrollador 100–200+ $/h en Norteamérica/Europa Occidental, 30–80 $/h en Europa del Este/Asia (contexto para valorar horas de mantenimiento) — [eSEOspace](https://eseospace.com/blog/shopify-app-maintenance-ongoing/)

### Inferences
- Solo en Shopify, el calendario fijo es: 4 bumps de versión API/año (+ revisión de deprecaciones por changelog), cumplimiento BFS/GDPR, y migraciones estructurales cada 12–24 meses (GraphQL, Checkout Extensibility, Functions). **[EST]** Para una app pequeña bien construida, 4–8 h/mes de media en Shopify; WooCommerce 4–10 h/mes (PHP 8.x, HPOS, Blocks/Interactivity, temas y hostings dispares → más soporte que código); PrestaShop 6–12 h/mes si se soportan 1.7+8+9. Total **15–30 h/mes solo de mantenimiento**, antes de soporte a clientes y producción de modelos. Para un founder con ~40–60 h/mes disponibles, el mantenimiento triplataforma consume del 30 al 75 % del tiempo.
- La evidencia de "founders solos eligen UNA plataforma" es indirecta pero consistente: Barn2 (Woo → una app Shopify tras años), el solo dev de 7 apps (todas Shopify), y los nuevos entrantes 3D/AR de 2026 (Insiti, Visuality, Spacecheck) lanzan solo en Shopify (§7).

### Gaps
- **No encontré testimonios con horas/mes por plataforma** de desarrolladores (ni en Reddit ni en Indie Hackers con las búsquedas realizadas); la estimación de horas es propia.
- No encontré fecha de apagado final de REST Admin API para apps existentes.

---

## 4b. Venta directa a pymes españolas: CAC, cierre, agencias como reseller, sensibilidad al precio

### Takeaway
Los benchmarks outbound B2B (vendors, 2025–2026) sitúan la respuesta a cold email en 3–6 % y las reuniones en ~0,5–2 % por cada 100 emails; los programas de partners SaaS pagan 15–30 % recurrente, lo que sobre 49 €/mes deja 7–15 €/mes por tienda a la agencia, un incentivo insignificante. No encontré datos primarios españoles de CAC por canal ni de close rate en pymes; sí hay evidencia cualitativa de presión de costes (60 % de pymes españolas reportan aumento de costes) y de baja capacitación digital (eBay 2026).

### Cited Findings
- Cold email B2B: tasa de respuesta media ~3,43 % (Instantly 2026 Benchmark Report) y 5,8 % (blended, bajando desde 6,8 % en 2023); SaaS es el sector con bandejas más saturadas; **reuniones agendadas: 0,5–2 % por cada 100 emails, ~1 % típico** — [Instantly](https://instantly.ai/blog/meeting-email-metrics-to-track-response-booking-rates/); [LeadHaste](https://www.leadhaste.com/blog/outbound-sales-benchmarks-2026); [Digital Bloom](https://thedigitalbloom.com/learn/cold-outbound-reply-rate-benchmarks/)
- LinkedIn: benchmark de respuesta 7 %+; llamada en frío conecta con 18,6 % y genera el 33,6 % de las citas de 2025 (Belkins, vendor) — [Belkins](https://belkins.io/blog/sales-follow-up-statistics.md)
- CAC orientativo SaaS pyme/autoservicio: 50–300 $ con payback 4–12 meses (calculadora de vendor, sin fuente primaria ni España) — [PayPro Global](https://payproglobal.com/es/calculadoras-de-metricas-saas/calculadora-de-costo-de-adquisicion-de-clientes-cac-saas/)
- Contexto España: "un SaaS B2B en España y Europa tiene un CAC elevado por los equipos comerciales y los ciclos de venta largos" — [TeamSystem](https://teamsystem.es/magazine/cac-customer-acquisition-cost/); el 60 % de las pymes españolas reportan aumento de costes y problemas de tesorería — [Sage](https://www.sage.com/es-es/blog/?p=18731); las pymes españolas "tienen dificultades para aprovechar su potencial digital por limitada concienciación, comprensión y capacitación" — [eBay Spain Report 2026](https://www.ebaymainstreet.com/sites/default/files/2026-04/eBay_Spain%20Report_2026_A4_ES_v2.pdf)
- Programas de partners SaaS: HubSpot 20 % recurrente hasta 3 años; Jotform 30 % de por vida para agencias o 30 % descuento reseller; rango habitual 15–30 %, 69 % con comisión recurrente (agregador) — [eesel, SaaS partner programs 2026](https://www.eesel.ai/es/blog/best-saas-partner-programs); [Tapfiliate](https://tapfiliate.com/es/blog/best-agency-partner-programs-gp/)
- Ecosistema de agencias Shopify en España: 5 Premier + 31 Plus Partners (2026) — [Marketing4ecommerce](https://marketing4ecommerce.net/agencias-shopify-partners-espana/)
- Itnig (podcast): episodios potencialmente relevantes sobre B2B sales y SaaS (Javier Llorden #143 sobre precio del producto y coste del comercial; Fracttal #280; StockAgile #187) — no pude extraer datos cuantitativos de pymes — [Itnig podcast](https://itnig.net/podcast)
- Comercio electrónico B2C España (ONTSI ed. 2025): 110.683 M€ en 2024 (+11,5 %) — [asest.es citando ONTSI](https://asest.es/story/volumen-de-negocio-comercio-electronico/)

### Inferences
- Funnel outbound **[EST]** para una pyme de mueble: 100 emails → 1 reunión → 25–35 % cierre (demo con modelo 3D del propio catálogo del prospecto) → **~0,3 clientes por cada 100 emails**; para 10 clientes/mes harían falta ~3.000 emails/mes cualificados (base española de tiendas de mueble/decoración es de pocos miles, se agota en meses). Además cada demo convincente exige producir 1–3 modelos del catálogo del prospecto antes de cobrar (coste de preventa, ver §6).
- Agencias: a 20–30 % de 49 € = **10–15 €/mes por tienda**; una agencia que coloque 10 tiendas gana 100–150 €/mes. Los programas de partners funcionan con ACV de miles de euros (HubSpot), no con 588 €/año. Lo que sí interesa a la agencia es facturar la implantación (horas), lo que empuja el modelo a "servicio" y no a SaaS.
- Sensibilidad al precio: 49 €/mes ≈ 588 €/año es comparable al coste de la propia suscripción Shopify Basic o del hosting Woo de una pyme; para una tienda de mueble con pocas decenas de pedidos/mes es una partida visible que se evalúa cada mes → churn alto en meses de baja venta [EST].

### Gaps
- **No hay datos públicos españoles** de CAC por canal, close rate ni tiempo de cierre para SaaS low-ticket a pymes; ni blogs/podcasts (Itnig, Product Hackers, Marketing4ecommerce) con cifras verificables en las búsquedas hechas.
- No encontré márgenes publicados de agencias ecommerce españolas como resellers de apps.

---

## 5. Benchmarks: tiempo a 10k € MRR en SaaS vertical bootstrapped, horas del founder y resultados de founders a tiempo parcial

### Takeaway
Los datos auto-reportados (TrustMRR, Indie Hackers, MicroConf) convergen en que la mayoría de productos indie no genera ingresos (54 % con 0 $ en datos Stripe-verificados; ~50 % entre 0–1k MRR), solo 2,4 % alcanza 100k ARR, la mediana a 10k MRR es 12–18 meses desde el primer cliente (3 años "típico" en otra muestra) y **las empresas con founder a tiempo completo crecen 2,2× más rápido que las de tiempo parcial** (MicroConf 2024).

### Cited Findings
- MicroConf (State of Independent SaaS 2024, página act. jun-2026): "las empresas con fundadores a tiempo completo crecen **2,2× más rápido** que las de fundadores a tiempo parcial; los equipos liderados por developers crecen 1,7× más rápido"; benchmarks de 469 founders encuestados (otras fuentes citan ~700 respuestas) — [MicroConf, 0–10k ARR](https://microconf.com/founders/0-10k-arr); [MicroConf, State of Independent SaaS](https://microconf.com/saas-this-year)
- TrustMRR (3.478 startups, citado 2025): **mediana 12–18 meses desde el primer cliente de pago hasta 10k MRR; "la mayoría nunca llega"**; a 50 $/mes hacen falta 200 clientes, a 9 $/mes 1.100+ — [dev.to, How to hit 10k MRR in 2025](https://dev.to/shayy/how-to-actually-hit-10k-mrr-in-2025-no-bs-just-what-works-204k)
- Indie Hackers (founders que publican gráficas): "**tres años de 0 a 10k MRR es lo típico**" — [Indie Hackers](https://www.indiehackers.com/post/heres-how-to-hit-10k-mrr-faster-891549221d)
- TrustMRR 2026 (10.150 productos listados): **solo 2,4 % de los productos indie alcanzan 100k ARR**; muestra autoseleccionada — [Techstartups](https://techstartups.com/?p=138900); [dev.to](https://dev.to/mateusz_buda_4d53f15c8429/only-5-indie-hackers-products-make-100kyear-22oo)
- Estadísticas indie 2026 (BetterLaunch, aprox.): ~50 % de los indie hackers activos entre 0 y 1k MRR; <5 % supera 100k; 1k–10k MRR descrito como "ingreso secundario/a tiempo parcial" — [Indie Hacker Business Statistics 2026](https://blog.mean.ceo/?p=11175)
- Datos Stripe-verificados de Indie Hackers (análisis antiguo): **>54 % de los productos no generan ningún ingreso** — [Indie Hackers](https://www.indiehackers.com/post/how-much-money-do-indie-hackers-products-make-74db9631f0) (la página devolvió 403 al verificar; cifra tomada del resumen de búsqueda)
- SaaStr: bootstrapping "funciona, pero añade 4 años al calendario" — [SaaStr](https://www.saastr.com/bootstrapping-in-saas-it-does-work-but-add-4-years-to-the-timeline)
- Agregador r/SaaS: los founders tardan ~228 días de media en llegar a 2k MRR — [Discury](https://digest.discury.io/pulse-saas-founders-first-2k-mrr-grind-e41a); "44 de 47 founders que llegaron a 10k MRR vendieron servicios manuales antes de escribir código" (muestra no verificable) — [Discury](https://discury.io/digest/playbook-how-bootstrapped-saas-founders-reach-ramen-profitability-8326)
- Tras 10k MRR es habitual un plateau de ~6 meses y se recomienda un segundo canal de adquisición entre 10k y 30k — [Alpesh Nakrani](https://alpeshnakrani.com/blog/bootstrapped-saas-lessons-0-100k-arr)

### Inferences
- Si la mediana a tiempo completo es 12–18 meses (y 3 años en muestras más honestas), el factor 2,2× de MicroConf sitúa al founder a tiempo parcial en **~27–40 meses** para 10k MRR en el caso mediano — y eso para productos puramente software, sin producción de contenido por cliente [EST].
- A 49 €/mes, 10k € MRR = 204 tiendas activas; con churn 5 % hay que captar ~10 tiendas/mes **solo para mantener** ese nivel (ver §8).
- "Servicio disfrazado de SaaS" (modelos 3D por cliente): el dato de Discury (vender servicios primero) describe precisamente la trampa: los ingresos iniciales llegan como servicio, y el founder a tiempo parcial no tiene horas para convertirlo en producto.

### Gaps
- MicroConf no expone públicamente la tabla horas/semana × ingresos; el PDF completo (stateofindiesaas.com) no se consultó.
- Todos los datasets son autoseleccionados (sesgo de supervivencia hacia arriba; los fracasos no publican).

---

## 6. La trampa de la producción de contenido: SaaS que requiere crear modelos 3D por cliente

### Takeaway
Un modelo 3D de producto hecho por humanos cuesta 179–650 $ (Sayduck desde 179 $, freelancers 200–500 $) con 2–3 semanas de plazo y una ronda de revisiones; la IA (Meshy, desde 20 $/mes) baja el coste marginal a céntimos pero los modelos fallan en escala, geometría y materiales (reflectantes, finos, blandos — justo textiles y tapicería), y exigen 15–30 min de trabajo por producto. Ninguna de las empresas "servicio+SaaS" (Threekit, Hexa, Sayduck, Levar, Zakeke) publica su mix servicios/suscripción; Threekit factura ~16–21 M$ con 220 clientes a 18k–500k $/año, es decir, enterprise, no low-ticket.

### Cited Findings
- **Sayduck** (pricing, nov-2026): creación de modelos 3D **desde 179 $ por modelo "muy simple"**, más caro según complejidad; plazo "de días a 2–3 semanas"; una ronda de revisiones incluida, cambios adicionales de pago; precios de suscripción no publicados (solo demo). Dealroom: ingresos de suscripciones de plataforma y servicios de modelado (sin cifras) — [Sayduck pricing](https://www.sayduck.com/pricing); [Dealroom Sayduck](https://app.dealroom.co/companies/sayduck)
- Mercado de modelado: **200–500 $ por modelo** freelance/encargo, ~2 semanas de entrega; con IA la malla sale en ~1 minuto pero el artículo estima **15–30 min de esfuerzo total del merchant por producto**; modelos generados no cumplen la spec de Shopify (escala real, quads, UVs manuales, ~4 MB); **los errores de escala son los más dañinos para AR; productos reflectantes, monocromos, finos o de materiales blandos se reconstruyen mal** — [eCommerce Fastlane, 27-ago-2026](https://ecommercefastlane.com/ai-3d-model-generators-shopify-product-pages/)
- Sketchfab/InVRsion: modelos de producto de complejidad media 180–650 $; freelancers 50–300 $; template-based 100–400 $ — [Sketchfab](https://sketchfab.com/blogs/enterprise/create-3d-models-cost); [Twikit](https://twikit.com/how-do-you-get-affordable-3d-models-made-of-your-products/)
- Meshy: plan gratuito 100 créditos/mes (~5 generaciones imagen→3D) con atribución CC BY 4.0 obligatoria; **de pago desde 20 $/mes** con propiedad total y acceso API — [eCommerce Fastlane](https://ecommercefastlane.com/ai-3d-model-generators-shopify-product-pages/)
- **Threekit**: 21 M$ ingresos 2024 (Latka; 11,4 M$ en estimación anterior), 220 clientes, **contratos de 18k $ a 500k $/año**, 81 empleados, 65 M$ levantados, valoración 300 M$; otra fuente: ~16 M$ y 92 empleados — [GetLatka Threekit](https://getlatka.com/companies/threekit); [Latka interview](https://www.audioscrape.com/podcast/saas-interviews-with-ceos-startups-founders/episode/how-threekit-plans-to-grow-into-their-300m-valuation-break-10m-revenue-this-year-66007); [Techlist](https://techlist.ai/threekit.com). **Sin desglose servicios vs suscripción**.
- **Hexa**: "cobra honorarios de servicio por la creación de modelos 3D e integración AR"; sus ingenieros construyen el modelo desde una sola imagen (sin financieros) — [SourceForge Hexa 3D](https://sourceforge.net/software/product/Hexa-3D)
- **Levar** (Shopify): Starter 59 $/mes (subida de modelos propios, hasta 20 modelos), Essentials 99 $/mes (40), tiers superiores hasta 100 modelos y "Custom # of models"; precio de construcción de modelos **no publicado** ("pricing poco transparente" según reseñas) — [Levar en Shopify App Store](https://apps.shopify.com/levar-final); [Digismoothie](https://www.digismoothie.com/app/levar)
- **Angle 3D** (Shopify): desde 39 $/mes; el equipo crea modelos bajo presupuesto ("3D artists provide fast and cost-effective modeling"); reseñas destacan que "el equipo lo hizo todo, desde la creación del modelo hasta la integración" y que "la curva para conseguir el modelo, texturas y opciones correctos es empinada" — [Angle 3D en Shopify](https://apps.shopify.com/angle-3d-configurator); [AppNavigator reviews](https://appnavigator.io/app/angle-3d-configurator/)
- **Zakeke**: Starter 69,90 $/mes (10 productos) + 1,9 % de transacción; Grow 129,90 $ (50) + 1,7 %; Scale 299,90 $ (100) + 1,5 %; 100 reseñas / 4,5; una reseña de 2026 denuncia cargos extra por límites de almacenamiento 3D introducidos en 2025 — [Zakeke en Shopify](https://apps.shopify.com/zakeke-interactive-product-designer)

### Inferences
- **Margen bruto [EST]**: si el pipeline IA funciona sin intervención, el COGS por modelo es <1 € (créditos Meshy/Tripo + GPU) y el margen bruto >85 %. Pero la evidencia de calidad (escala, materiales blandos, reflectantes) implica revisión humana: a 15–30 min/producto y 30–50 €/h de coste del founder, **10–25 € por modelo**; una tienda de mueble con 60 productos cuesta 600–1.500 € de producción en onboarding frente a 49 €/mes de ingreso → **payback del solo onboarding de 12–30 meses, i.e. igual o superior a la vida media del cliente con 5 % de churn (20 meses)**. El negocio solo cierra si el merchant hace el trabajo él mismo (y entonces compite con Insiti/Visuality/Spacecheck a 22–57 $/mes, §7).
- Los players que viven de esto son enterprise (Threekit: ACV ≥18k $) o cobran el modelado aparte (Sayduck 179 $+, Angle 3D bajo presupuesto, Levar opaco). **Nadie en el mercado ofrece "modelos ilimitados incluidos" a 49 €/mes**; eso es una señal de que la economía no lo permite.
- Para mueble/decoración (textiles, tapizados, cristal, lacados brillantes) las limitaciones de la IA coinciden con el catálogo típico → mayor tasa de retoque manual que en productos rígidos y texturizados.

### Gaps
- **Ningún dato público sobre el % de ingresos por servicios** de Sayduck, Hexa, 3D Cloud, Threekit, Zakeke o Levar.
- No encontré tarifas de creación de modelos de Zakeke ni de Levar (solo "contactar").
- No hay estudios de calidad/aceptación de modelos IA específicamente en mueble tapizado.

---

## 7. Respuesta competitiva: qué cuesta a Insiti, Zakeke, Visuality o Angle 3D copiar "foto IA → 3D"

### Takeaway
Ya está copiado: en mayo de 2026 lanzaron en Shopify Insiti (Barcelona; Starter 57 $/mes con 10 modelos IA/mes) y Visuality (Francia; desde 32,99 $/mes con conversiones IA imagen→3D), y existen Spacecheck (49 $/mes, modelo en 180 s) y "AI 3D Model Generator" (2–3 fotos, 3–10 min). La generación en sí es un API de terceros (Meshy desde 20 $/mes con API, Tripo, Hunyuan3D, Trellis), así que el "pipeline" no es defendible; la diferenciación real estaría en calidad verificada a escala, integración y distribución, no en la generación.

### Cited Findings
- **Insiti 3D & AR** (Shopify, lanzada 20-may-2026, Insiti.io, Sant Martí, Barcelona): Free (3 referencias AR, branding Insiti), Creator 22 $/mes (10 referencias AR, analítica), **Starter 57 $/mes (25 referencias AR, 10 modelos 3D IA/mes, funnel completo)**; "convierte fotos planas de producto en modelos 3D/AR a escala real"; 3 reseñas / 5,0 — [Insiti en Shopify](https://apps.shopify.com/insiti-ar-viewer)
- **Visuality** (Shopify, lanzada 21-may-2026, Inside Learning, Landes, Francia): Bronze 32,99 $/mes (trial 7 días), Silver 42,99 $, Gold 64,99 $; "creación de modelos 3D desde fotos con IA o importación GLB", AR por QR; 0 reseñas a nov-2026; Capterra indica Bronze = 10 objetos 3D y 5 conversiones IA/mes — [Visuality en Shopify](https://apps.shopify.com/visuality); [Capterra Visuality](https://www.capterra.com/p/10040659/Visuality/)
- **Spacecheck – 3D AI Generator: Photo to 3D**: 49 $/mes, "modelo desde una sola foto en 180 segundos" — [Spacecheck en Shopify](https://apps.shopify.com/spacecheck)
- **AI 3D Model Generator**: genera un modelo en 3–10 min desde 2–3 imágenes — [AI 3D Model Generator en Shopify](https://apps.shopify.com/ai-3d-models-generator)
- **Zakeke**: listing destaca "AI-powered visualization", "AI realistic previews", "AI product images"; **no anuncia generación IA de modelos 3D** (a nov-2026); 100 reseñas, activa desde nov-2017, Starter 69,90 $ + 1,9 % — [Zakeke en Shopify](https://apps.shopify.com/zakeke-interactive-product-designer)
- **Angle 3D**: desde 39 $/mes, ~100 reseñas / 5,0, requiere modelo existente; ofrece modelado por su equipo — [Angle 3D en Shopify](https://apps.shopify.com/angle-3d-configurator)
- Generadores IA disponibles por API: Meshy (pago desde 20 $/mes con API; exporta GLB/OBJ/FBX/STL/USDZ), Tripo, Hunyuan3D, Trellis — [eCommerce Fastlane](https://ecommercefastlane.com/ai-3d-model-generators-shopify-product-pages/); [AI Magicx guide](https://www.aimagicx.com/blog/ai-image-to-3d-model-guide-2026)
- Shopify ofrece gratis escaneo 3D desde la app móvil (iPhone 12 Pro+, 10–15 min/pieza, requiere el objeto físico) — [eCommerce Fastlane](https://ecommercefastlane.com/ai-3d-model-generators-shopify-product-pages/)

### Inferences
- **Coste de copia [EST]**: integrar una API imagen→3D (Meshy/Tripo) en una app que ya tiene visor 3D/AR, gestión de assets y billing es un sprint de 2–6 semanas para un equipo pequeño; Insiti y Visuality lo hicieron en 2026 como productos de lanzamiento. Para Zakeke (equipo consolidado, 100 productos en plan Scale) es una feature de roadmap, no un reto técnico.
- La "diferenciación por pipeline" (mejor prompt/pipeline de limpieza de malla) no es defendible: los proveedores de modelos (Meshy-6, Hunyuan3D, Trellis) mejoran trimestralmente y todos los competidores acceden a las mismas mejoras al mismo precio. Lo defendible sería (a) datos de calidad validada por categoría de mueble, (b) distribución (agencias, reseñas, BFS), (c) integración con catálogo/variantes (acabados, telas) — y (c) ya lo hace Insiti ("material sigue la variante elegida").
- Hay un competidor directo **español, en Barcelona, ya en el App Store con pricing por debajo (22–57 $) y el mismo pitch** (fotos → 3D/AR a escala real). Site Hassle entraría segundo en su propio país, en WooCommerce/PrestaShop (sin marketplace eficiente), con un precio similar.

### Gaps
- No encontré tráfico, instalaciones o MRR de Insiti/Visuality/Spacecheck (Shopify lo prohíbe); solo reseñas (3, 0 y sin dato).
- No verifiqué si Zakeke/Angle 3D tienen roadmap público de generación IA.

---

## 8. Modelo GTM bottom-up para un founder en solitario a tiempo parcial (49 €/mes, churn 5 %/mes)

### Takeaway
Con 5 % de churn mensual, la base de clientes se estanca en **20 × (altas netas/mes)**: para 50 tiendas hacen falta ≥2,5 altas/mes sostenidas, para 200 ≥10/mes y para 500 ≥25/mes. La suma realista de canales para un founder a tiempo parcial (~40–60 h/mes totales, de las que 15–30 h se van en mantenimiento multiplataforma, §4) da 4–8 altas/mes en el primer año → **techo de 80–160 tiendas (3,9k–7,8k € MRR); 200 tiendas no se alcanza nunca y 500 queda fuera de rango** salvo con inversión en ads y producción de modelos que el propio modelo de 49 €/mes no financia.

### Cited Findings (parámetros usados y su origen)
- Churn 5 %/mes: dentro del rango "normal" 3–5 % para apps SMB (Taylor Sicard, jul-2026) y por debajo del 11 % de un listing real (Flippa) — [Taylor Sicard](https://taylorsicard.com/blog/shopify-ecosystem-benchmark-report-2026); [Flippa](https://flippa.com/11991879)
- Install→paid 15–20 % (mediana apps Shopify) — [Taylor Sicard](https://taylorsicard.com/blog/shopify-app-free-to-paid-conversion); freemium 2–5 % — [Freemius](https://freemius.com/blog/increase-freemium-upgrades-wordpress-plugin-theme/)
- Ingreso del quintil joven de apps Shopify ≈130–280 $/mes (≈3–6 tiendas a 49 €) — [Barn2](https://barn2.com/blog/shopify-app-store-saturation/)
- Cold email: ~1 reunión / 100 emails — [Instantly](https://instantly.ai/blog/meeting-email-metrics-to-track-response-booking-rates/); comisiones de partner 15–30 % — [eesel](https://www.eesel.ai/es/blog/best-saas-partner-programs)
- Coste de producción/retoque de modelo: 15–30 min/producto (IA) — [eCommerce Fastlane](https://ecommercefastlane.com/ai-3d-model-generators-shopify-product-pages/); 179–500 $ si es manual — [Sayduck](https://www.sayduck.com/pricing)
- Founder full-time crece 2,2× más que part-time — [MicroConf](https://microconf.com/founders/0-10k-arr)

### Supuestos propios **[EST]**
- Founder a tiempo parcial: 10–15 h/semana ≈ 40–60 h/mes totales; coste de oportunidad 50 €/h (para convertir horas en CAC).
- Mantenimiento triplataforma 15–30 h/mes (§4) → quedan 15–40 h/mes para ventas, soporte y producción de modelos.
- CPC App Store Ads 1–3 $ (no hay dato oficial; rango asumido para categoría de nicho), clic→instalación 10–15 %, instalación→pago 15–20 %.
- Cierre reunión→pago en outbound a pymes: 25–35 % (requiere demo con modelos del catálogo del prospecto: 1–2 h de preventa por reunión).

### Tabla A — CAC y volumen alcanzable por canal (año 1, founder a tiempo parcial)

| Canal | Supuestos clave | CAC estimado por tienda de pago | Altas/mes alcanzables (part-time) | Horas founder/mes | Comentario |
|---|---|---|---|---|---|
| App Store orgánico (Shopify, app nueva, 0–10 reseñas) | 10–30 instalaciones/mes; 15–20 % → pago | 0 € cash; 60–160 € en horas (ASO, pedir reseñas, soporte) | **1–4** | 5–10 h | Coherente con quintil joven Barn2 (3–6 tiendas/mes de ingreso). Sin BFS no hay spotlight; BFS exige ~6 meses y ~1.000 usuarios gratis. |
| App Store Ads | CPC 1–3 $ × (10–15 % inst.) × (15–20 % pago) → CPA 35–200 $ | **40–180 €** cash | 2–8 con 300–500 €/mes | 2–4 h | Payback 1–4 meses sobre 49 € bruto; pero el presupuesto sale del bolsillo del founder y la base española en Shopify es pequeña. CPC real desconocido. |
| SEO / contenido (ES, "visor 3D muebles", "AR tienda online") | Nicho de bajo volumen; 6–9 meses de latencia | 0 € cash; 100–300 € en horas durante el año 1 | **0–2** (meses 1–9), 2–5 después | 8–12 h | Competencia con Zakeke/Insiti/agencias por keywords genéricas; keywords en español con volumen muy bajo. |
| Cold outreach a pymes mueble/decoración ES (email + LinkedIn) | 300–500 emails/mes; 1 % reunión; 25–35 % cierre; 1–2 h preventa/reunión | **250–600 €** en horas (incl. demo con modelos del prospecto) | **1–2** | 12–20 h | Base direccionable se agota en 6–12 meses; cada demo exige producir modelos gratis. |
| Agencias / freelancers PrestaShop-Woo-Shopify como reseller | 20–30 % recurrente = 10–15 €/mes por tienda para la agencia | 50–150 € (onboarding de la agencia + comisión año 1) | **0–2** tras 3–6 meses de ramp | 4–8 h | Incentivo económico casi nulo para la agencia a 49 €/mes; piden facturar la implantación como servicio. |
| Contenido / LinkedIn personal | Posts, casos, vídeos AR | 0 € cash; 100–200 € en horas | **0–2** | 4–8 h | Compite con el tiempo de las otras 4 empresas del founder. |
| **Total realista** | | **CAC blended ≈ 120–250 €** (cash + horas) | **4–8 altas/mes año 1** (hasta 10–15 en año 2 si todo funciona) | **35–60 h/mes solo en GTM** | Supera las horas disponibles netas de mantenimiento (15–40 h). |

### Tabla B — Dinámica con churn 5 %/mes

Fórmula: con n altas/mes constantes y churn c, N(t) = (n/c)·(1−(1−c)^t); techo N* = n/c = 20·n; meses hasta un objetivo N: t = ln(1 − N·c/n) / ln(1−c).

| Escenario | Altas/mes (n) | Techo de tiendas (20·n) | Meses a 50 | Meses a 200 | Meses a 500 | MRR en el techo (49 €) |
|---|---|---|---|---|---|---|
| Pesimista part-time (orgánico + algo de outreach) | 4 | 80 | ~19 | nunca | nunca | 3.920 € |
| **Base part-time** (todos los canales, sin ads significativos) | 8 | 160 | **~7** | **nunca** | nunca | 7.840 € |
| Optimista part-time (ads 500 €/mes + agencias funcionando, año 2) | 15 | 300 | ~4 | **~21** | nunca | 14.700 € |
| Full-time con ads y equipo de producción de modelos | 30 | 600 | ~2 | ~8 | ~35 | 29.400 € |
| Necesario para que 500 sea alcanzable en <24 meses | ≥40 | 800 | ~1,5 | ~5 | ~19 | — |

Lecturas:
- **200 tiendas exige ≥10 altas netas/mes de forma indefinida** solo para no retroceder; 500 exige ≥25/mes. Ninguna de las dos cifras es compatible con 15–40 h/mes de GTM.
- En el escenario base, el MRR se estanca en ~7,8k € brutos. Restando churn de ingresos, Shopify 0 % (primer 1 M$) pero Woo Marketplace 30 % si se usa, créditos de IA, hosting y **producción/retoque de modelos** (10–25 € por producto; una tienda de 60 productos = 600–1.500 € de onboarding vs. 980 € de LTV bruto a 20 meses de vida media), el margen de contribución por tienda puede ser negativo en el primer año de cada cliente [EST].
- La ramp-up real es peor que la tabla: las altas no son constantes desde el mes 1 (App Store sin reseñas, SEO con 6–9 meses de latencia), así que los "meses a 50" del escenario base son más bien 9–12 que 7 [EST].
- El competidor directo (Insiti, Barcelona, Shopify, 22–57 $/mes con 10 modelos IA/mes incluidos) ya está en el canal con más tráfico; Site Hassle empezaría en los dos canales con peor distribución (Woo sin marketplace eficiente, PrestaShop en contracción −17 %/año).

### Inferences
- El GTM no falla por un canal concreto sino por aritmética: **churn 5 % × ticket 49 € × horas part-time → techo estructural de 80–160 tiendas**, muy por debajo de las 204 necesarias para 10k € MRR, y sin margen para financiar ads ni producción de modelos.
- Las dos palancas que cambiarían el resultado son incompatibles con el posicionamiento: (a) subir el ticket a 150–300 €/mes con modelado incluido y venta consultiva (modelo Angle 3D/Sayduck, requiere equipo de ventas y producción = full-time), o (b) bajar a 19–29 €/mes 100 % self-service en Shopify compitiendo frontalmente con Insiti/Visuality/Spacecheck en reseñas y BFS (requiere 12–24 meses de dedicación al App Store, también full-time).
- Multiplataforma desde el inicio multiplica el mantenimiento (15–30 h/mes) sin multiplicar las altas: los tres mercados comparten el mismo founder y las mismas horas de venta.

### Gaps
- Todos los parámetros de la Tabla A son estimaciones propias construidas con benchmarks de terceros no españoles; no existe ningún dato de CAC o conversión de un plugin 3D/AR vendido a pymes españolas.
- El CPC real de App Store Ads en la categoría 3D/AR solo se conoce dentro del Partner Dashboard.
