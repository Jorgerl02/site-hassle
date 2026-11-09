# VEED.io organic search machine (plus Kapwing, Canva, remove.bg, Photoroom for contrast)

**About the data.** All Ahrefs figures come from the Ahrefs API (Site Explorer), queried on 2026-11-09 with the report date set to 2026-11-08 and "all countries" unless a country is named. Ahrefs traffic is a **modelled estimate** (rankings × volume × CTR curve), not real analytics. It is useful for orders of magnitude and for comparing sections, not for exact visit counts. The "Source" links below point to the Ahrefs Site Explorer report for each target, which needs a paid Ahrefs login. The numbers were pulled through the API in this session.

---

## 1. Organic traffic and keywords over time; split by subfolder and locale

### Takeaway
VEED gets an estimated **~2.06M organic visits/month from ~76.7k keywords**. About two thirds comes from English product-led pages, and **/tools/ alone brings ~48%**. About 31% comes from **~26 locale folders** such as /es-ES/ and /pt-BR/. The blog (/learn/) is marginal at ~1.7%. Traffic peaked at **6.7M in Aug 2023**, recovered to **5.4M in Jun 2025**, and has since fallen about 64% to ~1.9–2.1M.

### Cited findings
- **Whole domain (veed.io, subdomains):** 2,056,216 est. organic visits/month; 76,749 keywords, of which 36,333 rank in the top 3; DR 86; 28,835 referring domains. Top countries: India 651k (~32%), US 188k (~9%), Indonesia 129k — [Ahrefs SE veed.io](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=veed.io)
- **Split by English subfolder (est. visits/month · keywords · RDs):**

  | Path | Traffic | Share of site | Keywords | Ref. domains | Top countries |
  |---|---|---|---|---|---|
  | /tools/ | 990,734 | ~48% | 25,027 | 10,515 | IN 516k, US 112k, PK 67k |
  | / (homepage, exact) | 158,425 | ~7.7% | 2,485 | 14,348 | IN 44k, US 21k |
  | /convert/ | 96,842 | ~4.7% | 2,563 | 537 | IN 38k, US 13k, PH 9k |
  | /create/ | 76,469 | ~3.7% | 6,144 | 1,842 | **US 34k**, IN 22k, GB 4k |
  | /learn/ (blog) | 34,223 | ~1.7% | 2,439 | 1,371 | IN 17k, SA 8k, US 2k |
  | /blog/ (legacy) | 119 | ~0 | 35 | 254 | – |
  | /use-cases/ | 20 | ~0 | 9 | 472 | – |
  | /templates/, /features/ | 0 | 0 | 0 | 20 / 9 | – |
  | /view/ (user-shared videos) | 0 | 0 | 0 | **3,227** | – |

  — [Ahrefs batch analysis, veed.io prefixes](https://app.ahrefs.com/site-explorer/overview/v2/prefix/live?target=www.veed.io/tools/)
- **Sub-clusters inside /tools/:** /tools/script-generator/ (AI text generators for hashtags, titles and descriptions) 195,976; /tools/ai-video* 173,195; /tools/video-compressor* 93,256; /tools/webcam-test* 38,393 — [Ahrefs SE](https://app.ahrefs.com/site-explorer/overview/v2/prefix/live?target=www.veed.io/tools/script-generator/)
- **History of monthly organic traffic (veed.io):** 2,519 (Jan 2019) → 81k (Dec 2020) → 858k (Dec 2021) → 2.54M (Dec 2022) → **6.72M peak (Aug 2023)** → 4.14M (Nov 2023, −38% in 3 months) → 4.0M (Nov 2024) → 5.39M (Jun 2025) → 4.0M (Dec 2025) → 2.51M (Jun 2026) → **1.92M (Nov 2026)** — [Ahrefs metrics history](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=veed.io)
- **Third-party write-ups** describe VEED's growth as "free standalone tools + programmatic landing pages matched to search intent". A former VEED growth PM's portfolio credits these with a 2.3M increase in users acquired through SEO. Traffic figures quoted in agency write-ups (3–3.5M/month) differ from Ahrefs today, and the ARR claims conflict ($7M vs $40M), so treat them as unverified — [Contra (ex-VEED PM)](https://contra.com/p/EoNlYOLc-23-m-visitors-and-19-m-mau-with-data-driven-seo-and-cro-veed); [upgrowth.in](https://upgrowth.in/how-veeds-programmatic-seo-drives-over-3m-monthly-organic-traffic/); [stormy.ai](https://stormy.ai/blog/veed-io-brute-force-seo-playbook); [Indie Hackers](https://www.indiehackers.com/post/from-ycombinator-rejection-to-7m-arr-in-less-than-5-years-how-veed-leveraged-seo-to-bootstrap-a-startup-to-success-ddcae57bfe) (403 on fetch; title only)

### Inferences
- The English sections (/tools/, /convert/, /create/, homepage, /learn/) add up to ~1.36M (66%), the locales ~0.64M (31%), and the rest is miscellaneous. VEED's SEO is **product-page SEO, not content SEO**: the blog drives under 2%.
- The steep 2021–2023 ramp coincides with RDs growing from ~2k to ~10k and with mass page creation. The drops in late 2023 and 2025–26 are consistent with Google core/helpful-content updates and AI Overviews absorbing "how to compress a video"-type queries. **This is an inference; Ahrefs does not give causes.** A copycat strategy started today should expect lower CTR on generic utility queries than VEED enjoyed in 2021–23.
- The traffic skews heavily to India, Pakistan and Indonesia. Much of the volume is low-monetisation "free utility" demand. /create/ is the only section where the US leads, because "X video maker" queries carry higher purchase intent.

### Gaps
- No real (GA/GSC) traffic numbers from VEED. Ahrefs is an estimate and tends to under-count long tail and brand.
- I did not test the history per subfolder, so it is unknown whether the 2025–26 decline hit /tools/ or the locales hardest.
- VEED's templates live outside /templates/ (0 traffic there). Their real path was not identified.

---

## 2. Top pages, their keywords, and how programmatic they are

### Takeaway
The top pages are almost all **one template × one task keyword**: "[tool]" or "[format] to [format]". **Ahrefs sees ~807 ranking URLs under /tools/, ~148 under /convert/ and ~347 under /create/**, before locale copies. Traffic follows a power law: **21 /tools/ pages bring ~80% of /tools/ traffic**. Free, browser-only micro-utilities (hashtag generator, webcam test, online mirror, teleprompter) are among the biggest winners.

### Cited findings
- **Top pages (all countries, est. visits/month · top keyword · volume · position):**
  1. / — 148k — "veed io"
  2. /tools/script-generator/hashtag-generator — **140.7k** — "hashtag generator" (21k vol, #1) — only 145 RDs
  3. /tools/video-editor — 96k — "video editing software" (#2) — 3,188 RDs
  4. /tools/ai-video — 81.7k — "ai video" (74k, #1)
  5. /convert/video-converter — 70.5k — "video converter" (47k, #2)
  6. /tools/video-compressor — 59.8k — "video compressor" (111k, #3)
  7. /create/gif-maker — 50.6k — "gif maker" (993k, #9)
  8. /es-ES/herramientas/descargar-de-instagram — 47.1k — "descargar videos de instagram" (143k, #3)
  9. /tools/ai-video/text-to-video — 47.1k — "text to video" (#1)
  10. /tools/text-to-speech-video/ai-voice-generator — 41.4k
  11. /tools/screen-recorder — 40.8k ("screen recorder", 772k, #6)
  12. /tools/webcam-test — 35.7k ("webcam test", 81k, #4)
  13. /id-ID/alat/pengompres-video — 35.7k ("kompres video", 170k)

  Others: /tools/audio-editor 34k; /tools/image-to-video-ai 31k; /tools/script-generator/youtube-description-generator 31k; /convert/video-to-audio 17.9k; /tools/video-cutter 17.6k; /tools/audio-cutter 16.7k; /tools/auto-subtitle-generator-online 16.7k; /tools/video-compressor/gif-compressor 13.7k; /tools/video-compressor/discord-video-compressor 7.5k; /tools/video-compressor/mp4-compressor 8.8k; /create/birthday-video-maker 5.1k; /create/photo-video-maker 3.6k; /convert/mpeg-to-mp3 2.8k — [Ahrefs top pages veed.io](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=veed.io)
- **How traffic is spread across pages (Ahrefs "pages by traffic"):**
  - /tools/: 21 pages above 10k visits/month = 796k (~80% of /tools/); 8 pages at 5–10k; 37 at 1–5k; 156 at 100–1k; 515 at 1–100; 70 at 0.
  - /convert/: 2 pages above 10k = 80.9k (~84%); 9 at 1–5k; 25 at 100–1k; 101 below 100; 11 at 0.
  - /create/: 1 page above 10k (50.6k); 1 at 5–10k; 5 at 1–5k; 40 at 100–1k; 245 below 100; 55 at 0.

  — [Ahrefs pages-by-traffic](https://app.ahrefs.com/site-explorer/overview/v2/prefix/live?target=www.veed.io/tools/)
- **Programmatic patterns visible in the URLs:**
  - **Hub → modifier children:** /tools/video-compressor → /compress-avi, /compress-mkv, /compress-mov, /mp4-compressor, /discord-video-compressor, /youtube-video-compressor, /gif-compressor.
  - **Format-pair matrix:** /convert/{a}-to-{b}. The MP4-to-GIF page links to roughly 130 pair converters and about 22 "/convert/{format}-converter" pages.
  - **"[Occasion] video maker":** /create/birthday-video-maker, /lyric-video-maker, /cute-video-maker, /photo-video-maker.
  - **Generator family:** /tools/script-generator/{hashtag, youtube-title, youtube-description, instagram-caption…}.

  — [VEED video compressor](https://www.veed.io/tools/video-compressor); [VEED MP4 to GIF](https://www.veed.io/convert/mp4-to-gif); [Ahrefs top pages](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=veed.io)
- **/learn/ (blog) winners** are adjacent, top-of-funnel and partly off-product: /learn/hashtags-for-youtube-shorts 8.5k, /learn/unscreen-alternatives-video-background-removal 7.6k (a competitor-alternative page), /learn/free-tiktok-likes 6.0k, /learn/youtube-channel-names 3.0k — [Ahrefs top pages](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=veed.io)
- **One case study** counted ~128.8k keywords across VEED tool pages against ~44.1k monthly US brand searches. It frames brand demand as the result of the tool-page strategy. This is a third-party, older figure — [upgrowth.in](https://upgrowth.in/how-veeds-programmatic-seo-drives-over-3m-monthly-organic-traffic/)

### Inferences
- Pages need few links to rank. The #2 traffic page (hashtag generator) has only 145 referring domains, and youtube-description-generator has 36. Domain-level authority (DR 86) plus exact-match intent does the work. A new site has no DR 86, so **head terms like "video compressor" are out of reach. Long-tail children with a clear modifier (format, platform, use case) are the copyable part.**
- Only a few dozen pages matter. The 500+ pages under 100 visits/month are low-cost bets that rarely pay out alone, but together they add keyword coverage and internal-link mass.
- A tiny team can copy the pattern of **"cheap browser-only utility that solves an adjacent job"**. Webcam test and online mirror bring ~36k + ~0.7k (US) with no paid compute.
- **For a 3D-from-photo product:** the equivalents would be a hub page per job, each with modifier children:
  - Hub examples: "photo to 3D model", "furniture 3D model", "image to GLB", "3D model for AR / IKEA-style room planner".
  - Modifier children by output format: /photo-to-glb, /photo-to-usdz, /photo-to-obj, /photo-to-fbx.
  - By platform: "3D model for Shopify", "for Amazon View in 3D", "for SketchUp".
  - By object: "sofa 3D model from photo", "chair…", "table…".
  - Free micro-utilities could include "measure furniture from a photo", a "GLB viewer", a "USDZ to GLB converter" and a "3D model file size compressor". **These are inferences, not validated keyword data.**

### Gaps
- The exact number of programmatic pages per family, including non-ranking ones, was not counted from the sitemap. Ahrefs counts only URLs with rankings.
- I did not pull the keyword list per page beyond the top keyword.

---

## 3. Page template anatomy and "free" modifiers

### Takeaway
Every tool or convert page uses the same ~1,000–1,300-word template:
- H1 = the tool name.
- One CTA that deep-links into the editor with a preset, plus "No credit card required". There is **no embedded upload widget**.
- A 3-step how-to, a demo video, 3 benefit H3s, an FAQ, a logo wall and testimonials, a "More from VEED" blog block, and two internal-link blocks ("Discover more" children and "Explore related tools").
- Schema: SoftwareApplication (price 0, aggregateRating), HowTo, VideoObject, FAQPage and BreadcrumbList.

The **"Free" modifier sits in the title and meta**. "No sign-up" appears on converter pages. "No watermark" is **not** claimed, because free exports carry a watermark.

### Cited findings
- **/tools/video-compressor:**
  - Title: "Video Compressor - Free Video File Compressor, No Quality Loss - VEED". The meta starts with "Free video file compressor…".
  - H1: "Video Compressor". Subhead: "Video compression in minutes…".
  - CTA "Compress a video" → `veed.io/new?tool=compress`, with "No credit card required". No upload widget on the page.
  - Rating 4.6 / 2,100+ reviews shown above the fold.
  - H2s: "Compress video online: …", "How to compress a video online:" (H3s Upload / Reduce / Export), demo video, 3 benefit H3s (Discord/TikTok; sharing; MP4/MOV/MKV), FAQ (6 Qs, e.g. "Is this a free video compressor?", "Can I use this video compressor for Discord?"), "Loved by creators.", "More from VEED" (3 blog cards), repeat CTA, "More than an online video compressor".
  - Link blocks: "Discover more" (6 child pages) and "Explore related tools" (3).
  - Schema: SoftwareApplication (price 0 USD, aggregateRating 4.6 / 2,139), BreadcrumbList, HowTo with VideoObject, FAQPage.
  - About 1,100–1,300 words.
  - Paid plans are sold as watermark-free.

  — [veed.io/tools/video-compressor](https://www.veed.io/tools/video-compressor)
- **/convert/mp4-to-gif:**
  - Title: "Convert MP4 to GIF - Video to GIF Converter - VEED.IO". The meta says free, online, no sign-up needed.
  - H1: "MP4 to GIF". H3: "Free to convert, no account needed".
  - CTA "Convert your video to GIF" → new-project URL with the output preset to GIF, plus "No credit card required".
  - 3-step how-to and 4 FAQs.
  - "Supported file formats" block with ~22 converter links. "Explore related tools" block with **~130 pair-converter links** (avi-to-gif, mov-to-gif, gif-to-mp4, twitter-video-to-gif…).
  - Same schema set as the compressor page. About 1,000 words of prose.

  — [veed.io/convert/mp4-to-gif](https://www.veed.io/convert/mp4-to-gif)
- **/tools/script-generator/hashtag-generator:**
  - Title: "Hashtag Generator - Start Trending Online - VEED". H1: "Hashtag Generator".
  - An on-page "Keywords" input with a "Generate Hashtags" button. The secondary CTAs deep-link into the app (`/new?flow=…&source=landingPage`).
  - H3: "A free hashtag generator to get your content ranking on Google". Price 0 in JSON-LD.
  - "Discover more" links to 7 sibling generators; "Explore related tools" has 4 links.
  - About 1,000 words.

  — [veed.io hashtag generator](https://www.veed.io/tools/script-generator/hashtag-generator)
- **US keywords with "free" or "online" modifiers that VEED ranks for (examples, est. US visits):**
  - "online video editor" 19k vol #3 (1.6k visits)
  - "online mirror" 14k #8
  - "compress video online" 2.7k #6
  - "online teleprompter" #4
  - "free convert video to mp4" 5.4k #5
  - "ai video editor online free" #1
  - "remove noise from video online free" #1
  - "extract audio from video online free" #2
  - "free video cutter" #3
  - "video splitter online" #1

  Each modifier variant is captured by the **same hub page**, not by a separate "-free" URL.

  — [Ahrefs organic keywords US, veed.io](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=veed.io)

### Inferences
- VEED does **not** create separate pages for "free" or "online" variants. It puts "Free" in the title or meta and "online" in the H2s, and lets one URL absorb the modifiers. Child URLs are reserved for genuinely different intents (format, platform).
- Above the fold, the conversion design is: tool-name H1 → one benefit line → one verb CTA ("Compress a video") that lands **inside the product with the job preselected** → a risk reducer ("No credit card required") → social proof (rating and logos). This can be copied as a single Next.js template with per-page JSON: H1, verb, preset, children, FAQs.
- VEED avoids claiming "no watermark" because its free tier watermarks exports. For a paid 3D product, keep claims honest. For example, "free preview" or "try free" with a watermark or low-res preview mirrors VEED's funnel.

### Gaps
- No field data on conversion rate per template (CTA click-through, signup).
- I did not verify whether the hashtag generator returns output without login.
- I did not verify the schema with Google's Rich Results test, only by reading the page.

---

## 4. Backlink profile: DR, what earns links, growth

### Takeaway
DR 86 with ~28.5–28.8k referring domains. RDs grew steadily, roughly doubling each year from 2019 to 2023:
- 330 at end of 2019
- 2,251 at end of 2021
- 10,627 at end of 2023
- 22,551 at end of 2025
- ~28.5k in Nov 2026

The homepage holds most of the link equity (~26.8k RDs). The tool pages that earn real links are **utility pages people reference** (video editor, audio cutter, MP3 editor, video player, audio player) and **user-shared video links (/view/, 3.2k RDs)**. Thousands of RDs on vi-VN and th-TH pages come from DR≈0 spam domains and should be ignored as a tactic.

### Cited findings
- **RD history (veed.io):** 93 (Jan 2019) → 330 (Dec 2019) → 721 (Dec 2020) → 2,251 (Dec 2021) → 5,516 (Dec 2022) → 10,627 (Dec 2023) → 16,249 (Dec 2024) → 22,551 (Dec 2025) → 28,518 (Nov 2026) — [Ahrefs refdomains history](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=veed.io)
- **Pages by RDs:**
  - www.veed.io/ 26,818; veed.io/ 7,031
  - /tools/video-editor 6,562
  - /tools/audio-cutter 3,305
  - /tools/audio-editor/mp3-editor 2,746
  - /tools/audio-cutter/crop-music 2,734
  - /tools/video-player 2,520
  - /create/cute-video-maker 2,352
  - /tools/video-downloader 2,313
  - /tools/audio-joiner 2,218
  - /tools/ai-video 2,181
  - /tools/audio-player 2,147

  — [Ahrefs pages by backlinks](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=veed.io)
- **Spam on Vietnamese and Thai pages:** many /vi-VN/ and /th-TH/ tool pages show ~2.1k–3.7k RDs each with ~10–20k links. The top referrers to /vi-VN/cac-cong-cu/nen-video are DR 0–1 domains with zero traffic (e.g. chichino1.com, videofilters.info, random *.asia and *.info domains first seen in 2024–2026). This looks like spam or link-network noise, not earned links — [Ahrefs RDs for vi-VN page](https://app.ahrefs.com/site-explorer/overview/v2/exact/live?target=https://www.veed.io/vi-VN/cac-cong-cu/nen-video)
- **/view/ (hosted or shared user videos):** 3,227 RDs and 0 organic traffic. **Canva's /design/ (share links): 241,353 RDs**, more than half of Canva's 452,614 total, with only 23k traffic — [Ahrefs batch analysis](https://app.ahrefs.com/site-explorer/overview/v2/prefix/live?target=www.veed.io/view/)
- **Highest-traffic referring domains** include youtube.com (160 links), wikipedia.org (12), google.com, reddit.com (64), apple.com (206), adobe.com (648), github.com (180), blogspot.com (1,392), capcut.com (99), openai.com (38) and chatgpt.com — [Ahrefs referring domains](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=veed.io)

### Inferences
- **Copyable link engines for a tiny team, in order of evidence strength:**
  1. **Shareable output URLs** such as a public viewer link for each generated 3D model, ideally with an embed snippet and a small "Made with X" attribution. Canva's 241k RDs and VEED's 3.2k on share or view paths show this scales with users, not with outreach.
  2. **Free utilities people link from tutorials and forums** (players, cutters, testers). The 3D analogue: a free GLB/USDZ viewer, a format converter, a file-size optimizer.
  3. A homepage that collects brand and press links.
- Tool pages rank with very few direct links (point 2 above). Link equity flows from the homepage through dense internal linking ("Discover more" and "Explore related tools" on every page).
- VEED's DR 86 took ~5 years and ~28k RDs to build. A new domain should target long-tail modifiers until share/embed links accumulate.

### Gaps
- I could not confirm whether VEED's free-tier watermark is a hyperlink. A watermark burned into video pixels gives no link, so "made with VEED" link credit is unproven.
- No anchor-text analysis was run to separate brand from tool anchors.
- No dofollow ratio was measured.

---

## 5. Localization: number of languages and traffic share

### Takeaway
VEED localizes through **locale-coded subfolders with translated slugs**, e.g. /es-ES/herramientas/comprimir-video, /pt-BR/ferramentas/…, /id-ID/alat/…. **~26 locale folders across ~18 languages** together bring **~642k est. visits (~31% of the site)**. Spanish is the largest language (~186k across es-ES, es-MX, es-AR and es-CO), then Indonesian (~100k), Portuguese (~78k), Russian (~60k) and Vietnamese (~44k). Several locales split a language by country (es-ES, es-MX, es-AR, es-CO; it-IT, it-CH; fr-FR, fr-CA).

### Cited findings
- **Locale folders (est. visits/month · keywords):**
  - Spanish: es-ES 117,879 · 5,184 (top countries VE, PE, i.e. it serves all of LatAm); es-CO 25,466; es-AR 21,371; es-MX 21,301
  - Indonesian: id-ID 99,619
  - Portuguese: pt-BR 73,956; pt-PT 3,940
  - Russian: ru-RU 60,024 (RU 24k, UA 21k)
  - Vietnamese: vi-VN 43,580
  - Turkish: tr-TR 30,305
  - Italian: it-IT 24,310; it-CH 6,400
  - Thai: th-TH 17,623
  - French: fr-FR 16,470; fr-CA 1,293
  - Chinese: zh-TW 13,936; zh-CN 543
  - Arabic: ar-EG 13,070
  - Polish: pl-PL 13,069
  - German: de-DE 10,279
  - Korean: ko-KR 9,726
  - Hindi: hi-IN 5,927
  - Dutch: nl-NL 5,801
  - Japanese: ja-JP 4,882
  - Swedish: sv-SE 1,757
  - Zero traffic: es-CL, es-PE, es-US, de-CH, ar-SA, uk-UA, en-GB, en-IN

  — [Ahrefs batch analysis, veed.io locale prefixes](https://app.ahrefs.com/site-explorer/overview/v2/prefix/live?target=www.veed.io/es-ES/)
- **Top localized pages:**
  - /es-ES/herramientas/descargar-de-instagram 47.1k
  - /id-ID/alat/pengompres-video 35.7k
  - /pt-BR/ferramentas/teste-sua-webcam 16.8k
  - /es-ES/convertir/audio-a-mp3 13.9k
  - /pt-BR/ferramentas/comprimir-video 11.4k
  - Translated slugs throughout; some locales such as th-TH and ar-EG keep English slugs

  — [Ahrefs top pages veed.io](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=veed.io)
- **For contrast:**
  - Photoroom localizes as /{lang}/tools/… (/es/tools/background-remover 590k, /pt-br/… 403k, /id/… 129k, /ru/… 127k, /th/… 113k) — [Ahrefs top pages photoroom.com](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=photoroom.com)
  - remove.bg localizes the homepage itself (/es 1.77M, /pt-br 1.49M, /id 527k, /th 322k, /it 239k) — [Ahrefs top pages remove.bg](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=remove.bg)
  - Kapwing /es/ has 39.7k — [Ahrefs batch](https://app.ahrefs.com/site-explorer/overview/v2/prefix/live?target=www.kapwing.com/es/)

### Inferences
- Localization is worth ~30–50% extra traffic for utility tools, but the gain is concentrated in big emerging markets (LatAm Spanish, Brazil, Indonesia, Vietnam, Turkey) where monetisation is weak. For an English-first startup selling paid 3D models to furniture brands and e-commerce, localization is a **later** lever. Spanish (es) and Portuguese (pt-BR) for the highest-volume hub pages would be the first step, and only once English pages rank.
- Country-split Spanish (es-MX, es-AR, es-CO) adds modest traffic. A single /es/ is the MVP.

### Gaps
- The locale list is not exhaustive. I tested the common codes; others may exist, e.g. /hu-HU/ or /cs-CZ/.
- No hreflang audit was done.

---

## 6. Competitors with try-free funnels (brief contrast)

### Takeaway
All four rely on **task-named tool landing pages**, but concentration varies:
- **remove.bg:** one tool, and the homepage *is* the tool page (74% of traffic).
- **Photoroom:** one hero tool page (background remover, 55% of the site).
- **VEED:** a broad long tail of ~800+ tool pages.
- **Kapwing:** a smaller /tools/ footprint (15%), plus a templates and meme long tail.
- **Canva:** scales the same idea to /features/ (11.9M), /create/ (4.3M) and /templates/ (2.7M).

Blogs are marginal for all of them except Canva /learn/.

### Cited findings
- **Kapwing:**
  - Overall: 946,722 est. visits; 76,677 keywords; DR 80; 19,203 RDs; US 217k, IN 137k, ID 87k
  - /tools/ 144,932 (15%) · /resources/ (blog) 29,371 · /templates/ 22,351 · /es/ 39,682
  - Top pages: home 157k; /video-editor 35.9k; /subtitles 24.4k; /ai 21.4k; /meme-maker 14.5k; /tools/make/deepfake 12k; meme templates under /explore/ (5k each)

  — [Ahrefs kapwing.com](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=kapwing.com)
- **remove.bg:**
  - Overall: 37.2M est. visits; only 35,954 keywords; DR 83; 26,084 RDs
  - Homepage 27.45M (74%)
  - Localized homepages: /es 1.77M, /pt-br 1.49M, /id 527k
  - Task pages under short paths: /t/change-background 884k, /f/white-background 248k
  - /blog/ 165 visits

  — [Ahrefs remove.bg](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=remove.bg)
- **Photoroom:**
  - Overall: 9.49M est. visits; 52,015 keywords; DR 79; 14,805 RDs
  - English /tools/ 6.32M (67%); /tools/background-remover alone 5.22M (55%)
  - Other tool pages: /tools/white-background 209k, /tools/change-background-color 165k, /tools/remove-object-from-photo 135k
  - /blog/ 8.7k; /templates/ 86

  — [Ahrefs photoroom.com](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=photoroom.com)
- **Canva:**
  - Overall: 308.9M est. visits; 1.92M keywords; DR 93; 452,614 RDs
  - /features/ 11.87M · /create/ 4.28M · /templates/ 2.70M · /learn/ 650k · /design/ (share links) 23k traffic but 241k RDs

  — [Ahrefs canva.com](https://app.ahrefs.com/site-explorer/overview/v2/subdomains/live?target=canva.com)

### Inferences
- **What a tiny team can copy:**
  1. One "hero" page for the core job (the remove.bg/Photoroom model), e.g. "photo to 3D model" or "furniture photo to 3D". It should show a try-free CTA that lands in the product with the photo upload preselected.
  2. A modest family of modifier children: format, platform, furniture type. Use VEED's /tools/{hub}/{child} pattern with "Discover more" and "Related tools" blocks on every page.
  3. 2–4 free browser-only utilities that earn links: a GLB/USDZ viewer, a converter, a model size checker.
  4. Public share/embed URLs for every generated model to accumulate RDs (the Canva /design/ and VEED /view/ evidence).
  5. A blog only for alternative and comparison pages and adjacent how-tos. The evidence says a blog will not be the traffic engine.
- **Risk:** VEED's 64% traffic decline since mid-2025 suggests generic "free online [utility]" pages are losing clicks, plausibly to AI Overviews and Google updates (unverified). Pages targeting specific, high-intent jobs (e.g. "3D model of my sofa for AR / Shopify") are likely more durable than broad utility terms.

### Gaps
- Competitor histories (whether Kapwing or Photoroom also fell in 2025–26) were not pulled to save API units.
- Canva's /features/ page template was not inspected.
- No keyword-volume validation was done for 3D/furniture modifier terms. That belongs to a separate keyword research pass with Keywords Explorer.
