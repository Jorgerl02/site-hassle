# Lado comprador: tiendas online de mueble/decoración/piedra en España y Europa como clientes de un plugin AR/3D

Fecha de investigación: 8 de noviembre de 2026. Cada cifra lleva su fecha de publicación o de última actualización de la fuente. Leyenda: **[VERIFICADO]** = dato tomado de la fuente citada; **[ESTIMACIÓN]** = cálculo propio a partir de datos citados, con supuestos explícitos; **[VENDOR]** = cifra publicada por un proveedor de AR/3D o por Shopify con interés comercial, no contrastada.

Nota metodológica general: no he encontrado NINGUNA fuente oficial española (CNMC, INE, ANIEME/AMIC, Aidimme, Cetelem) que publique el número de tiendas online de mueble ni la facturación e-commerce del mueble en España. El bottom-up se apoya en censos de tiendas (Store Leads, StoreCensus) y en analogías con datos de EE. UU., y por tanto tiene bandas anchas.

---

## 1. TAM/SAM bottom-up: cuántas tiendas online de mueble/decoración/iluminación/colchón/piedra/cocina-baño hay en España (y DE/FR/IT/UK)

### Takeaway
En España hay del orden de 3.500–7.700 tiendas Shopify y ~5.200 tiendas WooCommerce en la categoría "Hogar y jardín" (nov. 2026), pero la subcategoría mueble/producto voluminoso es ~20 % de eso, y el segmento que puede pagar 50–100 €/mes (>25 SKUs y >300 k€ online) se queda, por estimación, en unas 200–500 tiendas en toda España. El techo de ingresos realista para un plugin AR a 19–99 €/mes en España es de decenas de miles de euros anuales, no de cientos de miles, salvo adopción muy superior a la observada en el mercado más maduro (EE. UU., donde <1 % de las tiendas de mueble <1 M$ usan AR/3D).

### Cited Findings

**Censos de tiendas (plataforma, país, categoría)**

| Dato | Valor | Fecha | Fuente | Estado |
|---|---|---|---|---|
| Tiendas Shopify activas en España (todas las categorías) | 46.597 – 49.733 (dos snapshots distintos) | ago. 2026 | [StoreCensus](https://api.storecensus.com/stores/country/spain?page=236) | VERIFICADO (snapshots inconsistentes) |
| Tiendas Shopify "Home & Garden" en España | 3.492 (título de página: 3.473) | 8 nov. 2026 | [StoreCensus ES Home & Garden](https://www.storecensus.com/stores/country/spain/category/home-and-garden) | VERIFICADO |
| Tiendas Shopify "Home & Garden" en España según Store Leads | 7.743 (1,9 % del total mundial) | 30 oct. 2026 | [Store Leads Home & Garden](https://storeleads.app/reports/shopify/category/Home%20&%20Garden) | VERIFICADO (la diferencia ~2x con StoreCensus se debe a taxonomías y criterios de "activa" distintos) |
| Tiendas WooCommerce "Home & Garden" en España | 5.242 | 8 nov. 2026 | [StoreCensus ES WooCommerce](https://www.storecensus.com/woocommerce-stores/country/spain/category/home-and-garden) | VERIFICADO |
| Tiendas PrestaShop hogar en España | No hay censo público en las fuentes consultadas | — | — | GAP |
| Tiendas Shopify "Home & Garden" mundiales | 409.956 | 30 oct. 2026 | [Store Leads](https://storeleads.app/reports/shopify/category/Home%20&%20Garden) | VERIFICADO |
| Tiendas Shopify "Home Furnishings" (mobiliario) mundiales | 84.626 (= 20,6 % de Home & Garden) | 30 oct. 2026 | [Store Leads Home Furnishings](https://storeleads.app/reports/shopify/category/Home%20&%20Garden/Home%20Furnishings) | VERIFICADO |
| Tiendas Shopify "Living Room Furniture" mundiales | 6.192; UK 13,6 %; dominios .de 100, .fr 97; España no aparece en el top | 13 mar. 2026 | [Store Leads](https://storeleads.app/reports/shopify/category/Home%20&%20Garden/Home%20Furnishings/Living%20Room%20Furniture) | VERIFICADO |

**Distribución por número de productos (Store Leads, 30 oct. 2026, Shopify mundial)** — [Home Furnishings](https://storeleads.app/reports/shopify/category/Home%20&%20Garden/Home%20Furnishings): 1–9 productos: 13.449; 10–24: 11.757; 25–49: 10.995; 50–99: 13.072; 100–249: 11.519; 250–999: 12.129; 1.000–4.999: 6.508; ≥5.000: 2.750. Es decir, el 70 % de las tiendas de mobiliario tiene ≥25 productos y el 30 % tiene <25. VERIFICADO.

**Europa (Shopify, categoría Home & Garden)**

| País | StoreCensus (8 nov. 2026) | Store Leads (30 oct. 2026) | Fuente |
|---|---|---|---|
| Reino Unido | 20.186 | 33.796 | [StoreCensus UK](https://www.storecensus.com/stores/country/united-kingdom/category/home-and-garden); Store Leads |
| Alemania | 8.729 | 12.841 | [StoreCensus DE](https://www.storecensus.com/stores/country/germany/category/home-and-garden); Store Leads |
| Francia | 7.058 | 14.511 | [StoreCensus FR](https://www.storecensus.com/stores/country/france/category/home-and-garden); Store Leads |
| Italia | 3.628 | no listado en top | [StoreCensus IT](https://www.storecensus.com/stores/country/italy/category/home-and-garden) |
| España | 3.492 | 7.743 | ver arriba |
| EE. UU. | — | 159.779 | Store Leads |

En "Home Furnishings" (mobiliario) Store Leads lista EE. UU. 31.118, UK 7.432, Francia 4.077, Alemania 2.414; España e Italia no aparecen en el top 10 (30 oct. 2026) — [Store Leads](https://storeleads.app/reports/shopify/category/Home%20&%20Garden/Home%20Furnishings). VERIFICADO.

**Tamaño del mercado del mueble en España (contexto)**
- El comercio minorista de muebles en España facturó 4.160 M€ en 2025 (+3,1 %), "impulsado por la vivienda, las reformas y el canal online", sin desglose del peso online — [Informa vía Demócrata](https://www.democrata.es/economia/el-comercio-minorista-de-muebles-eleva-su-facturacion-a-4-160-millones-en-2025-un-3-mas-segun-informa/) (2026). VERIFICADO.
- La fabricación de muebles en España cerró 2025 en 4.779 M€ (+3,4 %), exportaciones récord de 2.887 M€ — [Aidimme vía Interempresas](https://www.interempresas.net/Envase/629583-sector-mueble-cierra-2025-incremento-ventas-3-4-por-ciento-encima-PIB-total-pais.html). VERIFICADO.
- El e-commerce total español facturó 114.812 M€ en 2025 (+20,6 %), pero sólo el 31,3 % corresponde a compras de residentes en comercios españoles — [CNMC vía Marketing4ecommerce](https://marketing4ecommerce.net/ecommerce-espanol-facturacion-2025/) (2026). En el III-25, 29.296 M€ (+19,3 %); el 46,5 % de los ingresos tuvo destino España; los sectores líderes fueron agencias de viajes (10,8 %) y aéreo (6,6 %). El mueble NO aparece entre las diez ramas con mayor volumen — [Nota de prensa CNMC III-25, 24 abr. 2026](https://www.cnmc.es/sites/default/files/editor_contenidos/Notas%20de%20prensa/2026/20260424_NP%20CE_III_25.pdf). VERIFICADO.
- Observatorio Cetelem 2025 (mueble): el canal de compra líder vuelve a ser "las grandes cadenas"; en la edición 2024 el 52 % de los encuestados había comprado muebles el año anterior (-4 pts) y el 24 % productos de mueble de cocina — [Cetelem 2025 muebles PDF](https://elobservatoriocetelem.es/app/uploads/sites/3/2025/11/consumo-espana_2025_muebles.pdf) y [Cetelem 2024 muebles](https://elobservatoriocetelem.es/app/uploads/sites/3/2024/11/ob_consumo-espana_2024_muebles.pdf). VERIFICADO (el PDF 2025 devolvió 404 en la descarga directa; cifra del canal tomada del extracto de buscador).

**Analogía EE. UU. para la cola de tiendas grandes**
- De 42.817 tiendas Shopify activas de mueble y decoración en EE. UU., 3.446 (8,0 %) facturan más de 1 M$/año — [Soda Web Media, jul. 2026, datos Store Leads](https://www.sodawebmedia.com/insights/furniture-ar-3d-configurators/). VERIFICADO.
- Sólo el 1,82 % de los ~3,6 M de tiendas Shopify (65.441) gasta más de 100 $/mes en apps — [Eightx con datos Store Leads, 2026](https://eightx.co/blog/average-ecommerce-shopify-app-spend-by-revenue-band-2026). VERIFICADO (fuente vendor, dato derivado de Store Leads).

### Tabla bottom-up SAM España (ESTIMACIÓN con supuestos explícitos)

| Paso | Supuesto | Pesimista | Base | Optimista | Base del supuesto |
|---|---|---|---|---|---|
| A. Tiendas "Hogar y jardín" en ES (Shopify + Woo + PrestaShop) | Shopify 3.500–7.700 + Woo 5.200 + PrestaShop estimado 2.000–4.000 (sin censo) | 10.700 | 13.500 | 17.000 | StoreCensus / Store Leads (nov. 2026); PrestaShop sin fuente |
| B. % que vende producto voluminoso (mueble, colchón, iluminación grande, piedra, cocina-baño) | 20 % mobiliario (ratio mundial Home Furnishings/Home & Garden) + 5–10 pts por iluminación/colchón/piedra | 22 % | 26 % | 30 % | Store Leads (20,6 %) |
| C. Tiendas de producto voluminoso | A × B | 2.350 | 3.500 | 5.100 | — |
| D. % con ≥25 SKUs | Distribución Store Leads Home Furnishings | 65 % | 70 % | 70 % | Store Leads (70 %) |
| E. Tiendas con ≥25 SKUs voluminosos (universo que puede necesitar un plugin "por nº de productos") | C × D | 1.530 | 2.450 | 3.570 | — |
| F. % con >300 k€/año online (capaces de pagar 50–100 €/mes) | EE. UU.: 8 % supera 1 M$; España tiene tickets y madurez menores | 8 % | 12 % | 15 % | Soda Web Media (8 % >1 M$) |
| G. **SAM núcleo** (tiendas que pueden pagar el tier alto) | E × F | **120** | **290** | **535** | — |
| H. Resto de E (tier 19–39 €/mes) | E − G | 1.410 | 2.160 | 3.035 | — |

**Techo de ingresos en España (ESTIMACIÓN)** — adopción tomada del único dato de penetración real de apps AR/3D por tramo de facturación (EE. UU., Shopify, jul. 2026: <1 % en tiendas <1 M$, 5 % en >1 M$, 13 % en top 500, 26 % en top 100 — [Soda Web Media](https://www.sodawebmedia.com/insights/furniture-ar-3d-configurators/)):

| Escenario | Tier alto: tiendas × adopción × ARPU | Tier bajo: tiendas × adopción × ARPU | MRR | ARR |
|---|---|---|---|---|
| Pesimista | 120 × 5 % × 79 € = 474 € | 1.410 × 0,5 % × 25 € = 176 € | ~650 € | **~8 k€** |
| Base | 290 × 10 % × 79 € = 2.291 € | 2.160 × 2 % × 29 € = 1.253 € | ~3.500 € | **~43 k€** |
| Optimista | 535 × 20 % × 89 € = 9.523 € | 3.035 × 5 % × 35 € = 5.311 € | ~14.800 € | **~178 k€** |

El escenario optimista supone que Site Hassle captura en España una penetración 4× superior a la que todo el ecosistema de apps AR/3D juntas tiene hoy en el segmento >1 M$ de EE. UU. Para llegar a 1 M€ ARR haría falta Europa entera (ver abajo) y una cuota de mercado dominante.

**Multiplicador Europa (ESTIMACIÓN)**: en Home & Garden Shopify, UK + FR + DE suman 61.148 tiendas frente a 7.743 de España (Store Leads, 30 oct. 2026), es decir ~7,9× España; añadiendo Italia (StoreCensus: 3.628 vs 3.492 de España, ~1×) el multiplicador queda en ~9×. Aplicado al escenario base: ~390 k€ ARR teóricos para ES+DE+FR+IT+UK, antes de descontar competencia (Shopify tiene visor 3D/AR nativo gratuito; apps existentes desde 9–25 $/mes, ver pregunta 2) y costes de localización/venta.

### Inferences
- El cuello de botella del SAM no es el número de tiendas de hogar (~10–17 k en España) sino el filtro combinado "producto voluminoso + catálogo ≥25 SKUs + facturación suficiente": deja unas pocas centenas de tiendas en toda España.
- La discrepancia 2× entre StoreCensus y Store Leads para la misma categoría/país indica que cualquier TAM "de catálogo" debe presentarse como banda, no como cifra.
- La ausencia del mueble entre las diez ramas con más facturación e-commerce de la CNMC (III-25), junto con la preferencia por "grandes cadenas" (Cetelem 2025), sugiere que el canal online del mueble en España sigue siendo minoritario y concentrado en grandes operadores que no comprarían un plugin SMB.
- Un modelo de cobro "por número de productos" penaliza justo al segmento con más SKUs voluminosos (el que más se beneficiaría del AR), empujando a las tiendas grandes hacia soluciones a medida y dejando al plugin con las tiendas pequeñas, de menor disposición a pagar.

### Gaps
- No existe (o no es público) un recuento de tiendas PrestaShop de hogar/mueble en España; PrestaShop tiene peso histórico relevante en el e-commerce español y la banda A podría moverse ±3.000 tiendas.
- CNMCData sí desglosa por ramas de actividad (incluida "Muebles, iluminación y hogar" en informes antiguos — [CNMC 2012](https://www.cnmc.es/sites/default/files/1528847_8.pdf)), pero no he podido extraer la cifra actual del portal; recomiendo descargar la serie directamente en data.cnmc.es.
- INE/DIRCE: no he obtenido el número de empresas CNAE 4759 (comercio al por menor de muebles, iluminación y otros artículos de uso doméstico) ni el % que vende online; el INE sólo publica el agregado (31,6 % de empresas ≥10 empleados vendía online en 2021 — [Cronista](https://www.cronista.com/espana/economia-finanzas/un-tercio-de-las-empresas-vende-en-linea-y-ya-facturan-miles-de-millones-cual-es-el-secreto)).
- ANIEME/AMIC/Confortec no publican cuota de e-commerce del mueble en las fuentes localizadas; sólo exportaciones ([Feria Hábitat Valencia](https://www.feriahabitatvalencia.com/spanish-furniture-closes-2025-with-a-5-growth-in-exports/)).
- Store Leads sólo muestra el top 10 de países por categoría sin suscripción; el dato exacto de España en "Home Furnishings" requiere cuenta de pago.

---

## 2. En qué gastan realmente las pymes e-commerce en apps/plugins y dónde queda el 3D/AR

### Takeaway
La tienda Shopify mediana gasta ~50 $/mes en apps repartidos en ~11 apps (unos 4 $/app), y sólo el 1,8 % de las tiendas supera los 100 $/mes en apps; un plugin de 50–99 €/mes competiría por una cuota desproporcionada del presupuesto total de apps de una pyme. Las apps AR/3D del App Store de Shopify tienen muy pocas reseñas (0–3 en la mayoría; 93 la más reseñada) frente a miles en reviews/email/upsell, y Shopify ofrece el visor 3D/AR nativo gratis, lo que erosiona la disposición a pagar.

### Cited Findings
- Muestra de 300 tiendas Shopify con tráfico: mediana de 11 apps instaladas (cuartiles 6 y 16, p90 = 21) y gasto mediano en apps de 51,99 $/mes (~4,20 $ por app) — [Koala Apps, 2026](https://koala-apps.io/blog/shopify-app-stack-report/). VERIFICADO (fuente vendor).
- Otras estimaciones del gasto medio: 42 $/mes ([Digital Applied, 2026](https://digitalapplied.com/blog/shopify-statistics-2026-platform-growth-data)), 120 $/mes ([Shop Theme Detector](https://shopthemedetector.com/blog/shopify-app-store-statistics/)), 50–300 $/mes según tamaño ([Shopify Pricing](https://shopifypricing.pages.dev/app-costs)). Fuentes secundarias sin metodología; inconsistentes.
- Sólo 65.441 tiendas Shopify (1,82 %) gastan más de 100 $/mes en apps — [Eightx con Store Leads, 2026](https://eightx.co/blog/average-ecommerce-shopify-app-spend-by-revenue-band-2026). VERIFICADO (derivado).
- Shopify no publica una cifra oficial de gasto en apps por tienda en las fuentes consultadas. GAP parcial.
- Penetración de apps AR/3D/visualización en tiendas Shopify de mueble y decoración de EE. UU. (42.817 tiendas, detección de app instalada, jul. 2026): top 100 por facturación 26 %; top 500 13 %; >1 M$/año 5 % (163 de 3.446); <1 M$/año "under 1 percent". El autor advierte que la detección infravalora visores a medida y que "no rigorous, public, furniture-specific A/B evidence exists" — [Soda Web Media](https://www.sodawebmedia.com/insights/furniture-ar-3d-configurators/). VERIFICADO.
- Encuestas (autodeclaradas, sesgadas hacia interesados): Forrester Consulting para Cylindo (jun. 2023, 190 decisores de mueble): 17 % había adoptado AR y 52 % lo planeaba/consideraba; London Research/Fixtuur (inicios 2025, 100 retailers, 64 % europeos): 58 % declaraba usar AR — citadas en [Soda Web Media](https://www.sodawebmedia.com/insights/furniture-ar-3d-configurators/). VERIFICADO como cita; VENDOR en origen.
- Reseñas de apps AR/3D en Shopify App Store (nov. 2026): SwiftXR 3 reseñas (5,0) — [AppNavigator](https://appnavigator.io/app/swiftxr-viewer/reviews/); The Immersive 3D/AR ShowRoom (SunMall) 0 reseñas; Viewly 3D 0 reseñas — [open.store](https://open.store/shopify-apps/3d-viewer-sunmall), [apps.shopify.com/viewly3d](https://apps.shopify.com/viewly3d); Angle 3D Configurator 93 reseñas (92 de 5★, 1 de 4★, ninguna crítica) — [Shopify App Store](https://apps.shopify.com/angle-3d-configurator/reviews?page=15). VERIFICADO.
- Precios de apps AR/3D existentes: ARDisplay Viewer desde 10 $/mes (49 $ en otra locale) — [apps.shopify.com/ardisplay-viewer](https://apps.shopify.com/ardisplay-viewer); Viewly 9–19 $/mes; ARitize3D 9,99 $ por SKU — [Digismoothie](https://www.digismoothie.com/es/app/aritize3d); SwiftXR y "Try at Home" desde ~19–25 $/mes y tiers gratuitos; Poplar ofrece AR gratis para cuadros, alfombras y espejos (no necesitan modelo 3D) — [open.store Poplar](https://open.store/shopify-apps/poplar-ar-product-visualisation). VERIFICADO.
- Shopify soporta modelos 3D (GLB) nativamente en la media del producto con visor y AR Quick Look sin app — [Shopify 3D ecommerce guide](https://www.shopify.com/blog/3d-ecommerce); una guía de vendor reconoce que "si ya tienes modelos 3D precisos y vendes pocos muebles, el soporte nativo puede bastar" — [Picture It](https://www.pictureit.co/blog/best-shopify-ar-apps-in-2026). VERIFICADO.
- Un reseñador de una app 3D de pago cuenta que "the developer advised us to use the free, native 3D viewer in Shopify" — snippet de reseñas en [Shopify App Store (Angle 3D)](https://apps.shopify.com/angle-3d-configurator/reviews?page=15) recuperado vía buscador; no he podido localizar la reseña exacta en la página paginada. VERIFICADO PARCIAL.
- Coste de crear modelos: 200–1.000 $ por producto y plataformas AR para mueble con cuotas de 1.000–5.000 $/mes que exigen CAD — [Vizologi](https://vizologi.com/augmented-reality-for-shopify-how-to-add-ar-to-your-online-store/). VENDOR/secundario.
- PrestaShop: único módulo AR con precio público localizado, Webkul WebAR, 149 $ (licencia) — [Webkul](https://store.webkul.com/prestashop-webar-product-image.html). No se han encontrado hilos de foro ni reseñas de usuarios. VERIFICADO (precio).

### Inferences
- Con un gasto mediano total de ~50 $/mes en 11 apps, un plugin a 49–99 €/mes equivaldría a duplicar o triplicar la factura de apps de la tienda mediana; sólo el ~2 % de tiendas que ya gastan >100 $/mes es un comprador "natural".
- El volumen de reseñas (0–93 para apps AR/3D frente a decenas de miles en reviews, email o upsell) es un proxy de instalaciones: la categoría AR/3D es marginal en el App Store aun con 6+ años de existencia.
- La competencia relevante no son otras apps AR sino el visor nativo gratuito de Shopify y los generadores 3D con IA de bajo coste; el valor defendible sería únicamente la creación automática de modelos a escala, no el botón AR.
- La penetración real (<1 % en tiendas <1 M$ en EE. UU.) frente a la intención declarada (52–58 % en encuestas de vendors) es la mejor evidencia de que las pymes dicen querer AR pero no lo compran.

### Gaps
- No existe ranking público de categorías del Shopify App Store por instalaciones con el puesto exacto de "3D/AR"; la inferencia se basa en recuentos de reseñas.
- No he hallado datos de gasto en plugins de tiendas WooCommerce/PrestaShop españolas.

---

## 3. Devoluciones en e-commerce de mueble y efecto demostrado (independiente) del AR sobre conversión y devoluciones

### Takeaway
Las tasas de devolución del mueble online oscilan entre ~8 % y ~23 % según la fuente (todas de vendors de logística, 2024–2025), y el problema de talla/escala explica entre el 29 % y el 58 % de esas devoluciones; la única evidencia independiente sobre AR y devoluciones (Hayati, Chen y Van Everdingen, EMAC 2025) concluye que el AR reduce devoluciones SÓLO si la escala es exacta y que, si no, infla expectativas y produce "mixed outcomes". Las cifras de conversión más repetidas (+94 %, +250 %, 44 %/27 %/65 %) son de Shopify/vendors sin metodología o de un único caso (Rebecca Minkoff, bolsos), y Baymard (mayo 2024) midió que sólo el 6 % de los usuarios usa el botón "Ver en mi habitación" de forma proactiva y recomienda despriorizarlo.

### Cited Findings

**Tasas de devolución del mueble (todas fuentes vendor/secundarias)**
- Mueble y hogar: 19–23 % online; una devolución de mueble voluminoso cuesta 55–108 $ de procesar; el desajuste de tamaño/espacio explica ~58 % de las devoluciones (cita RocketReturns 2025) — [Eightx, 2025](https://eightx.co/blog/average-furniture-and-home-return-rate-benchmarks). VENDOR.
- Hogar y mueble: 15–20 % (media e-commerce EE. UU. 2024: 20,4 %) — [Corso](https://www.corso.com/post-purchase-resource-center/ecommerce-return-rate-benchmarks-by-industry). VENDOR.
- Mueble ~8 % frente a 25 % ropa y 17 % calzado — [Red Stag Fulfillment](https://redstagfulfillment.com/average-return-rates-for-ecommerce/). VENDOR.
- Motivos de devolución de mueble (encuesta Fixtuur): "no se parecía a lo esperado" 43 %, "las fotos no transmitían el producto real" 37 %, "confusión sobre dimensiones/escala" 29 % — [Fixtuur](https://www.fixtuur.com/resources/insights/returniture-is-rising-and-your-product-imagery-might-be-part-of-the-problem). VENDOR de 3D.
- Alemania (Forschungsgruppe Retourenmanagement, Univ. Bamberg): tasa global de devolución 24,2 % de paquetes en 2021 (~530 M de envíos), >90 % de los artículos devueltos son moda; "Dekoartikel und Möbel" figuran entre los grupos que rara vez se devuelven, sin porcentaje — [t3n](https://t3n.de/news/jede-6-bestellung-im-onlinhandel-geht-zurueck-1159446/), [gruender.de](https://www.gruender.de/vertrieb/produkte-mit-wenig-retouren/), [Uni Bamberg](https://www.uni-bamberg.de/presse/pressemitteilungen/artikel/erste-europaeische-haendlerbefragung-retourenmanagement/). VERIFICADO (académico, sin cifra de mueble).
- No he encontrado tasas de devolución de mueble online específicas de España. GAP.

**Evidencia independiente (académica) sobre AR**
- Hayati, Chen y Van Everdingen (Erasmus/RSM), "The Influence of Augmented Reality on Consumers' Product Returns in Online Retailing", EMAC 2025 (54th, #125566): "Using a combination of secondary data and two lab experiments, we demonstrate AR's potential in reducing product returns when it accurately shows the size of a product. However, AR results in inflated consumer expectations when sizing accuracy is lacking, leading to mixed outcomes." — [PDF EMAC](https://proceedings.emac-online.org/pdfs/A2025-125566.pdf). VERIFICADO (extended abstract de 2 páginas; sin tamaños de efecto publicados).
- Pfaff y Spann, "Augmented Reality and Spatial Fit Uncertainty in Online Retailing", Journal of Retailing and Consumer Services, vol. 87, 104442 (2025): datos de compras de productos con y sin AR de un "multi-channel home interior retailer", usando el cierre de tiendas físicas en pandemia como identificación; el AR es "particularly effective for evaluating and selling larger products" (mayor incertidumbre de encaje espacial). El resumen no reporta efecto sobre devoluciones ni magnitudes — [LMU ePub](https://epub.ub.uni-muenchen.de/128040). VERIFICADO (abstract).
- Tan, Chandukala y Reddy, "Augmented Reality in Retail and Its Impact on Sales", Journal of Marketing 86(1), 2022: datos de app móvil de un retailer internacional de COSMÉTICA (no mueble); el uso de AR "is associated with higher sales" sobre todo en marcas menos populares, productos de nicho y más caros, y en clientes nuevos en el canal; lenguaje correlacional, no experimento de campo — [Kellogg](https://www.kellogg.northwestern.edu/academics-research/research/detail/2022/augmented-reality-in-retail-and-its-impact-on-sales/). VERIFICADO.
- Heller, Chylinski, de Ruyter et al. (Journal of Retailing 2019, "Let Me Imagine That for You" y "Touching the Untouchable") tratan imaginería mental y AR multisensorial; no he encontrado en ellos ninguna medición de devoluciones — [RePEc](https://econpapers.repec.org/RePEc:eee:jouret:v:95:y:2019:i:2:p:94-114). VERIFICADO (ausencia).
- Tesis doctoral Univ. Zaragoza (Barta Arroyos, 2023), "Augmented reality as a tool to improve decision-making in online shopping: mitigating the problem of product return" — [Zaguan](https://zaguan.unizar.es/record/162164?ln=en). Existe; no he leído resultados. GAP.
- Frontiers in Communication (2026): encuesta a 209 compradores con PLS-SEM; el AR "plays a strong mediating role" en la eficacia de la política de devoluciones — es percepción autodeclarada, no comportamiento — [Frontiers](https://www.frontiersin.org/journals/communication/articles/10.3389/fcomm.2026.1769831/full). VERIFICADO (débil).
- Leal-Enríquez y Gutiérrez-Antúnez (IAENG IJCS 51(8), 2024): prueba de concepto AR en el departamento de mueble de la tienda Coppel; el texto recuperado no incluye resultados — [IAENG](https://iaeng.org/IJCS/issues_v51/issue_8/IJCS_51_8_23.pdf). GAP en resultados.

**Uso real del botón AR (Baymard, independiente)**
- Baymard Institute, "Furniture and Home Decor UX: Deprioritize 'View in Room' Augmented Reality (AR) Features", 15 mayo 2024 (tests a gran escala en Room & Board, CB2, Article, Joybird, Bob's): "only 6% of participants sought out and used it proactively"; 87 % de quienes lo encontraron eligieron no usarlo; "66% of users opted out of using AR and another 21% said they would but then didn't"; 79 % va primero a las imágenes; 41 % ve vídeo frente a 6 % que busca AR; "Worse, it frequently opens up doubt about the product and delays the purchasing decision to a later point in time"; recomendación: "invest in high-performing images on the product page" (zoom, imagen de escala, vignettes, dimensiones visibles, vídeo) y, si se mantiene AR, meterlo en la galería con etiqueta de texto — [Baymard](https://baymard.com/research-articles/deprioritize-view-in-room-augmented-reality). VERIFICADO.
- Houzz: "more than 2 million shoppers" usaron "View in My Room" en el proceso de compra desde mayo 2017; sin denominador ni tasa — [Retail Dive](https://www.retaildive.com/news/at-houzz-mobile-augmented-reality-is-fueling-sales/525276). VERIFICADO (sin tasa).
- Wayfair: "View in Room 3D" disponible para ~6 M de productos; ninguna tasa de uso publicada — [Business of Home](https://businessofhome.com/articles/wayfair-wants-to-transform-your-home-into-a-furniture-showroom). VERIFICADO (sin tasa).
- No he encontrado ningún comerciante que publique el % de visitantes que pulsa el botón AR. GAP.

**Cifras de marketing (VENDOR) y su trazabilidad**
- "+94 % de conversión": la única fuente de Shopify es una línea del changelog ("Merchants who add 3D content to their stores see a 94% conversion lift, on average") sin metodología — [Shopify changelog](https://changelog.shopify.com/posts/shop-adds-3d-and-augmented-reality-ar-previews); Inc. y Adobe la atribuyen a "Charged Retail Tech News" — [Inc.](https://www.inc.com/kevin-j-ryan/shopify-3d-augmented-reality-online-retail.html), [Adobe](https://www.adobe.com/products/substance3d/sunrisefor3d.html). VENDOR.
- "44 % más add-to-cart, 27 % más pedidos, 65 % más compra con AR": caso único Rebecca Minkoff (bolsos, Shopify Plus) — [Shopify case study](https://www.shopify.com/case-studies/rebecca-minkoff). VENDOR, n=1, sector no mueble.
- "+250 %": repetido por vendors (martech.zone, BrainStation) sin fuente primaria — [martech.zone](https://martech.zone/shopify-ar-augmented-reality-for-ecommerce/). VENDOR.
- "Wayfair: +92 % conversión, -43 % devoluciones, +28 % AOV": sólo en blog de vendor, sin disclosure de Wayfair — [FrameSixty](https://www.framesixty.com/augmented-reality-in-ecommerce/). VENDOR, no trazable.
- "58 % de consumidores usa AR antes de comprar" (Clutch 2026 vía Shopify) y "reducción de devoluciones de hasta 40 %" (post de un desarrollador en Shopify Community, 30 oct. 2025) — sin datos — [Shopify blog](https://www.shopify.com/blog/augmented-reality-furniture), [Shopify Community](https://community.shopify.com/t/has-anyone-tried-using-ar-in-their-shopify-store/573155). VENDOR.
- Único dato de devoluciones de un comerciante citado por Shopify: Gunner Kennels (transportines para perros) "reduced return rates by 5 percent" tras añadir 3D — [Shopify 3D ecommerce](https://www.shopify.com/blog/3d-ecommerce). VENDOR, n=1, no mueble.
- Casos de vendors en mueble sin cifras: Brico Io (Zakeke) "decrease in product returns"; Richmond Interiors (iONE360) "reduced returns" — [casestudies.com Zakeke](https://www.casestudies.com/company/zakeke/case-study/brico-io-reducing-furniture-returns-with-3d-ar-experiences), [casestudies.com iONE360](https://www.casestudies.com/company/ione360/case-study/visualizing-furniture-with-augmented-reality). VENDOR.
- Correlacional, no causal: 31 % de compradores que usaron un configurador 3D compró más de lo previsto frente a 17 % de los no usuarios (3D Cloud/Provoke Insights, 400 compradores EE. UU., finales 2025) — citado en [Soda Web Media](https://www.sodawebmedia.com/insights/furniture-ar-3d-configurators/). VENDOR.

### Inferences
- El argumento "el AR reduce devoluciones por tamaño" tiene una condición necesaria que la propuesta de Site Hassle ataca de frente: la exactitud dimensional del modelo. Un modelo generado por IA a partir de fotos de catálogo que no sea exacto a escala puede, según Hayati et al., EMPEORAR la brecha expectativa-realidad. El riesgo de producto es, por tanto, de doble filo.
- La mejor evidencia independiente de uso (Baymard: 6 % proactivo, 87 % rechazo) implica que incluso si el AR elevara la conversión de quien lo usa en un +50 %, el efecto sobre la conversión total de la tienda sería de ~+3 % relativo, difícil de detectar para una pyme sin test A/B.
- Lo que la literatura sí sostiene (Pfaff y Spann; Tan et al.) es que el AR ayuda más en productos grandes, caros y de nicho: exactamente el perfil de Pietra by Bianca o un fabricante de sofás, pero son productos de ticket alto con pocos SKUs y pocos pedidos, es decir, el peor encaje con un modelo de cobro por número de productos.
- Las tasas de devolución del mueble (8–23 %) son estructuralmente más bajas que en moda; el ahorro potencial por devolución evitada es alto (55–108 $ cada una) pero el volumen de devoluciones evitables por escala en una tienda de 300 k€ es de pocas decenas al año, lo que acota la disposición a pagar a unos cientos de euros anuales.

### Gaps
- No existe un experimento de campo publicado con datos de Wayfair, Houzz, IKEA o Shopify que mida devoluciones antes/después del AR; el propio sector reconoce la ausencia de evidencia A/B pública en mueble (Soda Web Media, jul. 2026).
- No he podido leer el texto completo de Pfaff y Spann (2025) ni la tesis de Zaragoza (2023) para extraer tamaños de efecto.
- No hay tasa de devolución de mueble online específica de España ni de la UE en fuentes independientes.

---

## 4. Comportamiento de los grandes retailers de mueble en España/UE respecto al AR

### Takeaway
Los únicos grandes operadores con AR verificado en ficha de producto son los gigantes tecnológicos del sector (IKEA, Wayfair, Houzz, Amazon), y aun así IKEA ha reorientado su inversión desde el AR puro (IKEA Place, 2017) hacia el diseño de habitación con IA (IKEA Kreativ, 2022–2024), señal de que el "ver el mueble flotando en AR" no convenció ni al líder. Para Kave Home, Maisons du Monde, Westwing, Leroy Merlin ES, Conforama y El Corte Inglés no he encontrado evidencia de AR en ficha de producto; Maisons du Monde y Leroy Merlin optaron por configuradores 3D/VR de habitación, no por AR por producto.

### Cited Findings
- IKEA lanzó IKEA Place (AR) en septiembre de 2017 y en 2019 permitió colocar varios productos a la vez — [Gear Patrol](https://www.gearpatrol.com/2019/09/23/ikea-place-augmented-reality-app-update/). En junio de 2022 presentó IKEA Kreativ (escaneo LiDAR de la habitación, borrado de muebles existentes, diseño sobre foto) — [9to5Mac](https://9to5mac.com/2022/06/22/ikea-augmented-reality-app/), [Mixed News](https://mixed-news.com/en/ikea-app-now-deletes-your-furniture-and-replaces-it-with-your-own/); en 2024 Kreativ se integró gratis en la app de IKEA — [Pickr](https://www.pickr.com.au/news/2024/ikea-takes-augmented-reality-to-2-0-with-kreativ-ai/). Una reseña de 2026 señala que IKEA en EE. UU. ya no promociona una app Place independiente y presenta Kreativ como la experiencia activa — [MacMyths](https://macmyths.com/ikea-place-review-what-ikea-kreativ-does-in-2026/) (fuente de baja autoridad). VERIFICADO (no hay anuncio oficial de discontinuación). En la ficha web de IKEA España sigue existiendo "Ver en 3D" y "Vista previa en realidad aumentada" (modo Quick Look) — [Xataka Móvil](https://www.xatakamovil.com/movil-y-sociedad/comprando-nuevos-muebles-para-mi-casa-he-encontrado-aliada-inesperada-realidad-aumentada). VERIFICADO.
- Wayfair: "View in Room 3D" en app para ~6 M de productos; extendido a Android con ARCore; añadió "Interactive Photo" — [Business of Home](https://businessofhome.com/articles/wayfair-wants-to-transform-your-home-into-a-furniture-showroom), [TechCrunch](https://techcrunch.com/?p=1609428). VERIFICADO.
- Houzz: "View in My Room" desde mayo 2017; >2 M de usuarios acumulados — [Retail Dive](https://www.retaildive.com/news/at-houzz-mobile-augmented-reality-is-fueling-sales/525276). VERIFICADO.
- Maisons du Monde: app "3D at Home" de realidad VIRTUAL para definir el estilo de interior — [Real Homes](https://www.realhomes.com/us/news/maisons-du-mondes-3d-at-home-app-helps-you-define-your-interior-style); servicio de asesoría decorativa con "visualisation 3D photo réaliste" — [Corporate MdM](https://corporate.maisonsdumonde.com/en/node/1810). No se ha encontrado AR por producto. VERIFICADO (ausencia en fuentes).
- Leroy Merlin España: realidad virtual/aumentada con Oculus en tiendas de Sant Cugat y Armilla (2016) — [Alimarket](https://www.alimarket.es/construccion/noticia_amp/208509/leroy-merlin-invertira-este-ano-172-m-en-aperturas-y-renovaciones); implantación de 3DVIA Home (Dassault, configurador 3D de cocinas) en España y Portugal (2018) — [Alimarket](https://www.alimarket.es/construccion/noticia_amp/271319/leroy-merlin-incorpora-la-experiencia-inmersiva-3dvia-home-de-dassault-systemes-06-06-2018-05-00); su app representó el 24 % de la venta digital al año de lanzarse, sin mención de AR — [Interempresas](https://www.interempresas.net/Ferreteria/582514-App-de-Leroy-Merlin-representa-24-por-ciento-de-su-venta-digital-ano-despues-de-su.html); piloto AR con la startup R2U sólo en Brasil (2021) — [Mercado & Consumo](https://mercadoeconsumo.com.br/2021/07/28/leroy-merlin-sai-na-frente-e-investe-em-realidade-aumentada-no-varejo-de-construcao/). VERIFICADO.
- Kave Home, Westwing, Conforama, El Corte Inglés, Habitat, La Redoute: ninguna fuente localizada menciona AR en ficha de producto (búsquedas en español y francés, nov. 2026). Kave Home ofrece servicio de interiorismo humano — [Kave Home](https://kavehome.com/ch/en/e/interior-design). VERIFICADO (ausencia en fuentes; no inspección directa de fichas).
- Made.com: quebró en 2022 (contexto conocido; no investigado aquí).
- En EE. UU., el 74 % de las 100 mayores tiendas Shopify de mueble NO tiene app AR/3D detectable, y el 95 % de las que facturan >1 M$ tampoco (jul. 2026) — [Soda Web Media](https://www.sodawebmedia.com/insights/furniture-ar-3d-configurators/). VERIFICADO.
- Baymard testó AR web (USDZ) en Room & Board, CB2, Article, Joybird y Bob's Discount Furniture, es decir, grandes retailers de EE. UU. que SÍ lo tienen, y concluyó que debe despriorizarse — [Baymard, mayo 2024](https://baymard.com/research-articles/deprioritize-view-in-room-augmented-reality). VERIFICADO.

### Inferences
- La trayectoria de IKEA (de AR por producto a diseño de habitación con IA/LiDAR) sugiere que el valor percibido por el líder está en "ver la habitación entera amueblada", no en el botón AR por SKU que propone Site Hassle.
- Que operadores con presupuesto como Maisons du Monde, Leroy Merlin o Kave Home no hayan desplegado AR en ficha (según las fuentes) mientras sí invierten en interiorismo humano y configuradores 3D es un indicio de que el ROI del AR por producto no les ha resultado evidente, lo que debilita el argumento "las pymes lo necesitan para competir con los grandes".
- Si el 95 % de las tiendas Shopify de mueble >1 M$ en EE. UU. no usa AR/3D pese a que es gratis en la plataforma, la ausencia de AR no es un problema de acceso/precio que un plugin resuelva, sino de prioridad.

### Gaps
- No he inspeccionado directamente fichas de producto de Kave Home, Westwing, Maisons du Monde, Conforama o El Corte Inglés en noviembre de 2026 (páginas con JavaScript pesado); la ausencia es "en fuentes", no comprobación de primera mano. Recomendable comprobar manualmente en móvil iOS (botón AR Quick Look) antes de usarlo como argumento definitivo.
- No he encontrado ningún caso documentado de un gran retailer que anuncie la RETIRADA de AR; el cambio de IKEA Place a Kreativ es el más cercano y no está formalizado como discontinuación.

---

## 5. Señales de disposición a pagar de las pymes (foros, Reddit, comunidades Shopify/PrestaShop/WooCommerce ES)

### Takeaway
El silencio es la señal: no he encontrado un solo hilo en Reddit, foros de PrestaShop en español o comunidades WooCommerce ES donde comerciantes de mueble discutan resultados de apps AR/3D; el único hilo de Shopify Community (oct.–nov. 2025) está íntegramente escrito por vendedores de apps, y en él la única "pega" reconocida es el coste de crear los modelos 3D. Las apps AR/3D del App Store acumulan 0–3 reseñas en su mayoría, frente a cientos o miles en categorías que las pymes sí pagan.

### Cited Findings
- Shopify Community, "Has anyone tried using AR in their Shopify store?" (29 oct. 2025, abierto por Vizbl, un vendor): el OP reconoce que "many shops think they are hard to implement or too costly"; websensepro (30 oct. 2025) afirma sin fuente "Stores have seen conversion rates jump by as much as 94% on products with AR/3D models" y "lower return rates by up to 40%"; HoppyApps (1 nov. 2025) identifica como obstáculo principal "creating the initial 3D models, but the ROI in customer confidence and reduced returns makes it worthwhile" y recomienda "starting with a few flagship products". Ningún comerciante real aporta datos propios — [Shopify Community](https://community.shopify.com/t/has-anyone-tried-using-ar-in-their-shopify-store/573155). VERIFICADO.
- Reseñas en App Store: SwiftXR (3 reseñas, 5,0): un usuario dice "The pricing structure is fair" pero "My only reasoning for now not using SwiftXR is that my product supplier changed their supply terms" (20 dic. 2024) y que el dashboard "can look confusing when you first open it up" — [AppNavigator](https://appnavigator.io/app/swiftxr-viewer/reviews/). SunMall Immersive ShowRoom: 0 reseñas; Viewly: 0 reseñas — [open.store](https://open.store/shopify-apps/3d-viewer-sunmall), [Shopify App Store](https://apps.shopify.com/viewly3d). Angle 3D Configurator: 93 reseñas, todas 4–5★ — [Shopify App Store](https://apps.shopify.com/angle-3d-configurator/reviews?page=15). VERIFICADO.
- Un reseñador de app 3D de pago indica que "the developer advised us to use the free, native 3D viewer in Shopify" — snippet de buscador de [reseñas Angle 3D](https://apps.shopify.com/angle-3d-configurator/reviews?page=15); no localizado literalmente en la página. VERIFICADO PARCIAL.
- PrestaShop en español: ninguna discusión de foro localizada sobre módulos AR/3D; único módulo con precio público Webkul WebAR 149 $ — [Webkul](https://store.webkul.com/prestashop-webar-product-image.html); Viewit3D con integración PrestaShop tiene 1 valoración (4,0) en Capterra — [Capterra ES](https://www.capterra.es/software/1015221/viewit3d). VERIFICADO.
- Reddit: tres búsquedas distintas (r/shopify, r/ecommerce, "uninstalled", "not worth") no devolvieron ningún hilo de comerciantes de mueble sobre apps AR/3D; el índice de búsqueda sólo devolvió blogs de vendors. GAP.
- Guía de vendor que admite el problema de medición: "you won't be able to tell where AR helps if you convert the whole catalog at once" — [Vizologi](https://vizologi.com/augmented-reality-for-shopify-how-to-add-ar-to-your-online-store/). VENDOR.
- Recuerdo de la evidencia de uso: 6 % de uso proactivo y 87 % de rechazo en tests de Baymard (mayo 2024) — [Baymard](https://baymard.com/research-articles/deprioritize-view-in-room-augmented-reality). VERIFICADO.

### Inferences
- La ausencia de conversación orgánica entre comerciantes (ni quejas ni elogios) es consistente con una categoría de app que casi nadie instala; las categorías con dolor real (envíos, reseñas, email) generan miles de hilos.
- El único "pain" que el propio ecosistema de vendors reconoce es la creación de modelos 3D; Site Hassle ataca ese pain con IA, pero la evidencia de Baymard y Hayati et al. indica que modelos de baja fidelidad o escala imprecisa empeoran la experiencia, así que resolver el coste del modelo no resuelve el problema de valor.
- Que haya apps AR gratuitas o de 9–19 $/mes con 0 reseñas sugiere que el precio no es la barrera de adopción; a 19–99 €/mes el plugin se posicionaría por encima de alternativas que ya no se usan.

### Gaps
- Ninguna cita directa de un comerciante español o europeo de mueble (positiva o negativa) sobre apps AR/3D; recomiendo entrevistas directas (10–15 tiendas del SAM núcleo) antes de cualquier decisión, porque la evidencia secundaria es inexistente.
- No se han revisado grupos de Facebook/Telegram/Discord de e-commerce en español ni el foro oficial de PrestaShop con búsqueda interna (no indexados).

---

## 6. Ciclo de venta de SaaS a pymes españolas de mueble: quién decide, sensibilidad al precio, estacionalidad, agencias como canal, churn

### Takeaway
Los datos disponibles son antiguos o genéricos: las pymes españolas representan el 97 % de las empresas de >10 empleados pero sólo 1 de cada 5 euros facturados online (ICEX/Adigital), más del 50 % declara no tener tiempo ni conocimientos para su tienda online (Cajamar/acens), y el churn mensual de SaaS para pymes se sitúa en 3–7 % (30–58 % anual). No he encontrado datos específicos de churn SaaS en pymes españolas ni del % de tiendas de mueble gestionadas por agencias.

### Cited Findings
- Las pymes son el 97 % de las empresas de más de 10 trabajadores en España y el 45 % de la cifra de negocios total, pero "apenas son responsables de uno de cada cinco euros facturados online" — [ICEX/Adigital vía PuroMarketing](https://www.puromarketing.com/76/23808/commerce-afianza-como-medio-internacionalizacion-empresas-espanolas) (fecha no reciente). VERIFICADO (antiguo).
- "El 90 % de las pymes considera estratégico abrir una tienda online pero más del 50 % no dispone de tiempo ni conocimientos" — [Cajamar y acens, 2016](https://www.acens.com/comunicacion/wp-content/images/2016/07/ndp-acens-cajamar.pdf). VERIFICADO (2016).
- Una de cada cuatro pymes españolas vendía online (estudio eBay 2017) — [PuroMarketing](https://www.puromarketing.com/76/28908/cada-cuatro-pymes-espanolas-vende-online). VERIFICADO (2017).
- El 75 % de las pymes españolas planeaba invertir en soluciones de e-commerce para 2025 (Forrester, citado en 2025) — [Emprendedores](https://emprendedores.es/gestion/internacionalizacion-ecommerce/). Secundario.
- Churn SaaS pyme (benchmarks internacionales, 2025–2026): 3–7 % mensual y 30–58 % anual para SMB SaaS — [Vena Solutions](https://www.venasolutions.com/blog/saas-churn-rate); 4,7 % mensual mediano de logo churn SMB — [Kalungi](https://www.kalungi.com/blog/-average-churn-rate-for-b2b-saas); clientes de 10–99 empleados 6,4 % mensual (57,8 % anual) — [Focus Digital](https://focus-digital.co/?p=6073); Recurly 2,34 % churn voluntario medio multisector (no sólo SaaS) — [UserJot](https://userjot.com/blog/saas-churn-rate-benchmarks). VERIFICADO (secundarios, definiciones no homogéneas).
- Shopify: el 1,82 % de tiendas gasta >100 $/mes en apps — [Eightx](https://eightx.co/blog/average-ecommerce-shopify-app-spend-by-revenue-band-2026). VERIFICADO (derivado).
- Estacionalidad del mueble en España: Cetelem 2025 sitúa el canal principal en grandes cadenas; compra de muebles declarada por el 52 % de los encuestados en 2024 (-4 pts) — [Cetelem 2024](https://elobservatoriocetelem.es/app/uploads/sites/3/2024/11/ob_consumo-espana_2024_muebles.pdf). No hay dato de estacionalidad mensual en las fuentes. GAP parcial.

### Inferences
- Si el 50 %+ de las pymes carece de tiempo y conocimientos para su tienda, el interlocutor real de un plugin "instálalo y sube fotos" será una agencia o freelance que cobra por horas y tiene incentivos para proponer proyectos (fotografía, renders, rediseño) antes que un SaaS de 49 €/mes cuyo margen de reventa es mínimo.
- Con churn SMB de 4–6 % mensual, un cliente a 49 €/mes tiene un valor de vida esperado de ~800–1.200 € antes de costes; un ciclo de venta que requiera demo + modelado de muestra + onboarding (típico en AR) difícilmente se amortiza con CAC de venta directa.
- El cobro por número de productos añade fricción adicional en catálogos que cambian por temporada (colecciones primavera/otoño en decoración), lo que puede elevar el churn estacional.

### Gaps
- No hay datos de churn SaaS específicos de pymes españolas ni del sector mueble.
- No hay estadística del % de tiendas online españolas de mueble gestionadas por agencia/freelance frente a in-house; sólo el indicio indirecto de Cajamar/acens (2016).
- No se ha localizado información sobre el programa de partners/agencias de Shopify en España ni sobre comisiones de reventa de apps, que sería clave para evaluar las agencias como canal.

---

## 7. Subnicho piedra/encimeras/mármol/travertino: evidencia de que el AR ayuda y tamaño del nicho online en España

### Takeaway
No he encontrado ninguna evidencia (académica ni de vendor) de que el AR mejore la venta online de productos de piedra o mármol; el canal online de la piedra en España es abrumadoramente B2B (Cosentino declara el 85 % de sus ventas online, pero a profesionales vía marmolistas) y la venta DTC de muebles de travertino se concentra en marketplaces de diseño (1stdibs) y marcas que sólo entregan en tienda. El nicho DTC de mueble de piedra en España es, por lo visto, de unas pocas tiendas, insuficiente para sostener un plugin.

### Cited Findings
- Cosentino: "el 85 % de sus ventas se realizan online", pero su e-commerce es B2B; los prescriptores (tiendas de cocina, constructores) compran a través de intermediarios como talleres de mármol — [Marketing4ecommerce](https://marketing4ecommerce.net/historia-cosentino/). VERIFICADO.
- Levantina ofrece la app "Dressed Stone" para visualizar piedra natural Naturamia o porcelánico Techlam en encimeras, paredes y suelos (visualizador, orientado a prescripción) — [Levantina](https://www.levantina.com/en/). VERIFICADO.
- Cupa Stone lanzó Ceratop (porcelánico) para encimeras; distribución vía talleres y distribuidores — [Alimarket](https://www.alimarket.es/construccion/noticia/373181/cupa-stone-se-consolida-en-encimeras-con-el-lanzamiento-de-ceratop--su-nueva-marca-de-porcelanico). VERIFICADO.
- Mueble de travertino DTC: en 1stdibs aparecen piezas de diseñadores españoles (Joaquín Moll para Meddel, mesa de centro a 3.858 € con 20 % de descuento, envío desde Madrid) — [1stdibs](https://www.1stdibs.com/es/muebles/mesas/mesas-de-centro/travertine-marble-coffee-table-spain-c-1980/id-f_46062452); Eichholtz vende una mesa auxiliar Sartoria a 1.495 € sólo con recogida en tienda — [Eichholtz ID House](https://eichholtzidhouse.com/es/products/side-table-sartoria-expo). No se ha localizado ninguna tienda online española especializada en mueble de travertino en los resultados de búsqueda (nov. 2026). VERIFICADO (ausencia).
- Evidencia AR en piedra/mármol: ninguna encontrada en búsquedas académicas ni de vendors. GAP.
- Lo más cercano en la literatura: el AR es más eficaz en productos grandes, caros y con alta incertidumbre (Pfaff y Spann 2025; Tan et al. 2022), condición que el mueble de piedra cumple, pero el beneficio depende de la exactitud de escala y textura (Hayati et al. 2025; Baymard 2024 cita "low-quality 3D models that differ in color or texture from product photos" como causa de abandono) — [Baymard](https://baymard.com/research-articles/deprioritize-view-in-room-augmented-reality). VERIFICADO.

### Inferences
- La piedra natural es el peor caso para un generador 3D por IA desde fotos: el valor del producto está en el veteado único y el acabado, exactamente lo que un modelo genérico con textura aproximada no reproduce, y Baymard documenta que la discrepancia de color/textura es motivo de rechazo del AR.
- Las encimeras se venden a medida por m² con plantillado en obra; el "ver en tu casa" a escala de catálogo no aplica a un producto que se corta a medida, por lo que la subcategoría cocina-baño/encimera queda fuera del caso de uso.
- El nicho DTC de mueble de piedra en España parece contarse en unidades o decenas de tiendas (ESTIMACIÓN basada en la ausencia de resultados), con tickets altos y pocos SKUs: cliente de proyecto a medida, no de SaaS por número de productos.

### Gaps
- No existe censo del número de tiendas online españolas de mueble de piedra/mármol/travertino; habría que construirlo manualmente (Store Leads con filtro de palabra clave, búsquedas en Google Shopping).
- No se ha encontrado ningún estudio, ni siquiera de vendor, sobre AR aplicado a piedra, mármol o encimeras.
- No se ha analizado la web de Pietra by Bianca ni su catálogo/SKUs para situarla en el bottom-up.
