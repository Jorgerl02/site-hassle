# VEED.io: from landing page to paid export (funnel and UX teardown, state as of 9 Nov 2026)

Method note: "LIVE" means observed directly on veed.io in a logged-out browser session on 2026-11-09 from a Spanish IP, so prices showed in EUR. The flow tested was /tools/video-compressor, then the editor, then a stock clip, then "Compress Video", then "Done" (export), then the signup and upgrade modals. Nothing was purchased, no account was created and no file was downloaded. "3P" means a third-party claim. Anecdotes and estimates are marked as such.

## 1. Can a visitor start editing without an account? Where is signup required, and which methods are offered?

### Takeaway
VEED has no signup wall before value. A tool-page CTA drops an anonymous visitor straight into the full editor with an auto-created project, and the visitor can upload, edit and even start the render. Signup is demanded only at download/share/save, and the modal appears *while the export renders*, so render time doubles as signup time. Methods offered: Google, Apple, Microsoft and "Work Email", which is passwordless via a one-time code.

### Cited Findings
- LIVE: The video compressor page CTA "Compress a video" links to `veed.io/new?tool=compress&locale=en&source=%2Ftools%2Fvideo-compressor`. That redirects with no login to `veed.io/edit/{uuid}/compress?...`: an anonymous project is created instantly and opens with a tool-specific modal, "Compress a Video". The modal reads "Upload files / Drag & drop a file or import from a link" and the footer says "By continuing, you agree to VEED's Terms of Use." — [veed.io/tools/video-compressor](https://www.veed.io/tools/video-compressor)
- LIVE: Behind the modal is the full editor (left rail: AI Tools, Video, Audio, Image, Subtitles, Text, Elements, Brand Kit, Settings), with stock videos and "Talking Characters" (avatars) available logged out. So the tool landing page is only a preset entry into the same editor (the `?tool=` parameter). — [veed.io/new](https://www.veed.io/new?tool=compress)
- LIVE: The compressor sub-flow ran fully logged out. "Compress Video" produced "Your video is now 1.5MB." with a "Download file" button and "Adjust compression settings" / "Compress another file" (I did not click download). The page's FAQ schema says: "You can compress a video for free (up to 1GB) and download it immediately from the compression results popup window. A paid plan lets you upload larger file sizes, access more editing tools, and unlock watermark-free exports." Simple utility tools therefore appear to allow logged-out download, which serves SEO trust. — [veed.io/tools/video-compressor](https://www.veed.io/tools/video-compressor)
- LIVE: The editor's top bar always shows a yellow "⚡ Upgrade" button next to a green "✓ Done" button, plus a gift icon. Clicking "Done" while anonymous redirected to `veed.io/view/{project}/{render}` with a progress card ("26% Rendering your video / Hang in there, this may take a few minutes.") and, beside it, a card titled "While you wait..." reading "Create a free account to download, share and save this video to your workspace." The buttons are Google (primary, black), Apple, Microsoft and Work Email, with "By proceeding, you agree to our Terms and Privacy Policy." — [veed.io](https://www.veed.io/new)
- LIVE: When the render finished (about 20 s for an 18 s clip), the card changed to a green check and "Sign up to download", with the same copy and buttons. The rendered video shows the creator as "Anonymous" with the date. The top bar shows "+ New", "⚡ Upgrade" and "Keep editing". The side rail has share, translate, download and comment icons. — [veed.io](https://www.veed.io/new)
- LIVE: "Work Email" opens a single field, "Enter your work email...", with "Continue" and "Back" buttons. There is no password field. — [veed.io](https://www.veed.io/new)
- VEED's help center: email signup uses a one-time code sent to the email address, followed by a "Stay signed in?" prompt. Signing in with Google can create a separate account even if the email matches an existing work-email account. — [VEED support: sign up and log in](https://support.veed.io/en/articles/10491439-sign-up-and-log-in-to-our-web-app); [VEED support: how to sign up](https://support.veed.io/en/articles/10491439-how-to-sign-up-and-login-to-veed)
- The subtitle tool page's copy also says "Sign up now to start creating" and "No credit card required", although the CTA itself doesn't force signup. — [Auto Subtitle Generator page](https://www.veed.io/tools/auto-subtitle-generator-online)

### Inferences
- The pattern is: enter the editor immediately with an anonymous project → do the work → put the gate at download, *while the render is still processing*. The wait is used to collect the account. The visitor has already invested effort and can see the result, so abandoning feels expensive. Adapted to our 3D case: free preview → "Download (1 credit)" → signup modal while the GLB/USDZ is being prepared.
- Social sign-in (Google first) plus a passwordless email OTP minimises friction. Our equivalent would be Google + magic link.
- The anonymous project is persisted under a URL (`/edit/{uuid}`) and is "saved to your workspace" on signup. This preserves the work across the auth boundary, which is critical so that signing up doesn't lose the result.

### Gaps
- I didn't complete signup, so I can't confirm whether the anonymous project is attached automatically after the OTP (VEED's copy implies it is: "save this video to your workspace").
- I didn't test upload of a user file (only stock media), or behaviour on mobile.

## 2. Free tier vs. gated features (watermark, resolution, minutes, file size, AI, brand kit) and how the watermark is shown

### Takeaway
On free (and logged out) you get 720p, exports up to 10 minutes, 1 GB uploads, 2 GB storage, 10 min/month of auto-subtitles and "Try once" on most AI tools, plus a VEED watermark on the export. The key UX trick is that **the watermark is not shown in the editor preview. It appears only in the rendered output** (top right, "VEED" logo, and it moves around the frame).

### Cited Findings
- LIVE (pricing comparison table, "See all features", 2026-11-09):

  | | Free | Creator | Pro | Enterprise |
  |---|---|---|---|---|
  | Watermark-free exports | No | Yes | Yes | Yes |
  | Export length | 10 min | Unlimited | Unlimited | Unlimited |
  | Export quality | 720p | 1080p | 4K | 4K |
  | Storage | 2 GB | 5 GB | 50 GB | Unlimited |
  | Upload size | 1 GB | Unlimited | Unlimited | Unlimited |
  | Stock audio/video | Limited | Unlimited | Unlimited | Unlimited |
  | Auto subtitles | 10 min/mo | Unlimited* | Unlimited* | Unlimited* |
  | Subtitle styles | Limited | Limited | Unlimited | Unlimited |
  | Text to speech | up to 10 min/mo w/ credits | 2 h/mo | 12 h/mo | Custom |
  | AI images | up to 50/mo w/ credits | 500/mo | Unlimited | credits |
  | AI dubbing | Try once | Try once | 30 min/mo | Custom |
  | Voice clone | Try once | – | – | – |
  | AI editing (Text Behind Person, AI B-Roll, Clean Audio, Remove Filler Words, Remove Silences, Eye Contact, Background Removal, Beautifier, Auto-Edits, Clips) | "Try once" each | (not shown) | (not shown) | (not shown) |
  | Brand kit | – | Limited | Multiple brands | Multiple brands |
  | Editors / reviewers | up to 3 / 0 | up to 3 / 0 | up to 3 / 0 | 3+ / Unlimited |
  | Support | AI chatbot | Chat | Chat | Chat 24/5 |

  — [veed.io/pricing](https://www.veed.io/pricing). Column alignment was reconstructed from the page text, so some cells for rows with few values are approximate.
- The pricing FAQ says: "All paid plans include unlimited subtitle generation, subject to a fair use limit of 50 hours per month." Translations are minute-based and "unused minutes do not roll over." — [veed.io/pricing](https://www.veed.io/pricing)
- VEED support (dated 19 Aug 2026): exports made while logged out or on a free account carry a VEED.IO watermark. The paid Lite, Pro and Enterprise plans export without it. The watermark can't be edited or moved, and it changes position over the course of the video. — [VEED support: watermark](https://support.veed.io/en/articles/7056370-will-the-videos-i-created-have-a-veed-watermark-on-them)
- VEED support (dated 21 Aug 2026): "Free Plan: Export in 720p only." Creator goes up to 1080p, Pro/Studio/Enterprise up to 4K. Upgrading doesn't fix past files: "The watermark is put on all exported videos while the account had a free subscription"; you must re-export the original project. — [VEED support: export](https://support.veed.io/en/articles/10531327-how-to-export-your-project)
- Naming inconsistency: VEED's own support articles still name "Lite" (watermark article) and "Studio" (export article), while the live pricing page shows only Creator / Pro / Enterprise. — [watermark article](https://support.veed.io/en/articles/7056370-will-the-videos-i-created-have-a-veed-watermark-on-them); [export article](https://support.veed.io/en/articles/10531327-how-to-export-your-project); [veed.io/pricing](https://www.veed.io/pricing)
- LIVE: The editor canvas showed the stock clip with **no watermark** during editing and in the compressor's result preview frame. The rendered export on the `/view/` page shows a semi-transparent "VEED" wordmark in the top-right corner of the player. — [veed.io](https://www.veed.io/new)

### Inferences
- Showing a clean preview and watermarking only the output keeps the experience premium and the "aha" intact, while making the watermark a loss-aversion trigger at the moment of highest intent. For us, the free 3D/AR preview should look perfect (no overlays). The gate should be the downloadable file, not a degraded preview.
- "Try once" per AI feature is a generous single-use sampler that teaches the value of each paid feature. For us, an analogue would be one free download on signup.
- The moving watermark exists to prevent cropping. In 3D the equivalent protection is not shipping the high-quality asset before payment (only a viewer stream or low-poly preview), not watermarking geometry.

### Gaps
- I couldn't confirm whether the free compressor download is watermarked (I did not download). The FAQ implies that watermark-free output requires a paid plan.
- Studio-tier details aren't visible on the live page (see section 3 for the conflict).

## 3. Upgrade moments, copy, pricing (dated), credits, trials, cancellation and refunds

### Takeaway
Upgrade pressure is constant but soft: a permanent yellow "Upgrade" button in the editor and view page, a "Sign up to download" gate, and an in-app "Upgrade Your Plan" modal that defaults to yearly billing ("Save up to 51%") with the Pro plan highlighted. Plan value is expressed in AI credits, translated into "~N AI Videos". There's no self-serve trial (only an Enterprise trial with 3+ seats). Cancellation is anytime, but refunds are essentially limited to the legal 14-day cooling-off period for unused service, which drives frequent Trustpilot complaints.

### Cited Findings
- LIVE prices (EUR, 2026-11-09, pricing page and in-app modal identical):
  - Yearly (default toggle "Pay yearly", badge "Save up to 51%"): **Creator €11** per user/month billed yearly, "6,000 Credits · ~1,500 AI Videos". **Pro €23** ("Recommended"), "18,000 Credits · ~4,500 AI Videos". Enterprise "Custom pricing" with a "Contact Sales" button.
  - Monthly: **Creator €22**/user/month, "500 Credits · ~125 AI Videos". **Pro €47**/user/month, "1,500 Credits · ~375 AI Videos". The comparison table header shows "€0 / €22/mo, per user / €47/mo, per user / Custom pricing".
  - Creator bullets: "No watermark · Unlimited Auto Subtitles · Full audio & video catalog · 15+ AI tools to make studio-quality videos · Create videos with Gen-AI Studio". Pro bullets: "Everything in Creator + · Multiple Brand Kits · Translate to 50+ Languages · Up to 144 hr/yr of AI voice (12 hr/mo on monthly)". CTAs are "Go Creator" and "Go Pro". The headline is "Great videos start with a plan" with the subline "Start for free, upgrade to get powerful features."
  - [veed.io/pricing](https://www.veed.io/pricing)
- LIVE in-app modal ("Upgrade Your Plan", opened from the yellow Upgrade button on the anonymous `/view/` page): same toggle, with the Pro "Upgrade" button in lime (primary) and the Creator "Upgrade" button in grey. Each card has a credits dropdown: Creator offers "6,000 credits" and "12,000 credits" per year, so credit tiers are a second price lever. Modal copy differs slightly from the page: "Unlimited clips / day in Gen-AI Studio" (Creator), "Unlimited videos in Gen-AI Studio" (Pro). The footer reads "Enterprise · Playground Credits, Central team management, Review mode, Privacy controls, Account manager…" with "Contact Sales". — [veed.io](https://www.veed.io/new)
- Pricing FAQ (verbatim fragments): trial — "We offer a free trial for enterprise customers. You will need a minimum of 3 users." Cancel — "Yes, absolutely", by turning off auto-renewal in the dashboard, with access "to all the premium features until the end of your billing cycle". Credits — "Your plan includes a set amount of AI credits each month or year to spend on AI generations." "Credits do not carry over, and you can move to a higher plan whenever you need more." Currency — local currency if available, otherwise USD. Seats are charged per user when you invite them. — [veed.io/pricing](https://www.veed.io/pricing)
- Terms of Sale: refunds aren't offered for changing your mind. Clause 7.3 lets consumers cancel for a full refund within the first 14 days only if they never used the Services (uploading, editing or adding subtitles all count as use). Subscriptions auto-renew (5.7). Cancel at least two business days before renewal (7.1/7.4). Support contact is hello@veed.io. No last-updated date appeared in the fetched content. — [veed.io/terms-of-sale](https://www.veed.io/terms-of-sale)
- 3P pricing history and conflict: a pricing tracker reports that on 26 Oct 2026 Studio was discontinued and Pro credits were cut from 30,000 to 18,000/yr, then on 2 Nov 2026 Pro was raised back to 30,000 and a new Studio plan with 180,000 credits was added, priced around $38.75–39. Other aggregators list USD prices of about $12/$24 yearly or $19/$49 monthly (labelled "Lite/Pro"). **This conflicts with my live observation on 9 Nov 2026 (EUR): no Studio and Pro at 18,000 credits/yr.** This may be geo-specific pricing or an A/B test. — [search summary of pricingsaas.com diffs](https://pricingsaas.com/companies/veed/diffs/2026W45); [magichour.ai](https://magichour.ai/blog/veed-pricing); [fluxnote.io](https://fluxnote.io/guides/veed-io-pricing-2026). I didn't open these pages; the figures come from the search tool's summary.
- 3P historical: pricingsaas logged in 2024 Q1 that VEED moved "Translate to 50+ Languages" from Pro to the then "Business" plan, so the plan lineup has been reshuffled repeatedly (Basic/Pro/Business → Lite/Pro → Creator/Pro/(Studio)). — [pricingsaas 2024Q1](https://pricingsaas.com/companies/veed/diffs/2024Q1). Title only, not opened.
- 3P (Trustpilot, read 2026-11-09): TrustScore 4.2 "Great", 3,932 reviews (846 in the last 12 months). Distribution: 70% 5-star, 15% 1-star. Recent negative themes are billing and refunds. A paused subscription restarted at US$30/mo without a reminder (4 Nov 2026); VEED agreed a partial refund and said it was "adding pre-billing notifications". An annual-plan refund was refused after under 30 minutes of use (6 Nov 2026). There are also complaints about slow support (11 days). These are anecdotes and self-selected. — [Trustpilot veed.io](https://www.trustpilot.com/review/veed.io)

### Inferences
- Upgrade moments observed, in order: (1) the persistent "Upgrade" button in the editor, (2) the signup gate at export/download, (3) the plan modal, which defaults to yearly with the "Recommended" tier visually primary, (4) per-feature "Try once" limits and the 720p/watermark limits, which surface when used (not observed directly).
- Expressing credits as "~N AI Videos" translates an abstract currency into outcomes. For a "1 credit = 1 model download" business, the mapping is already 1:1, which is clearer than VEED's.
- VEED's refund strictness plus auto-renewal create a visible reputation cost (a 15% 1-star share). For a pay-per-download credit pack (non-subscription), this risk is much lower. A clear "credits never expire / refund unused credits" promise could be a differentiator (my inference, not tested).

### Gaps
- Couldn't see the checkout page (Stripe or other) or whether a discount or downsell modal appears on cancel.
- Couldn't verify USD prices directly (the site geo-served EUR).
- Couldn't verify the exact modal triggered when a free user hits 720p, 10 minutes or a "Try once" limit.

## 4. Landing-page anatomy of tool pages (hero, upload box, social proof, how-to, FAQ, internal links, CTA repetition, speed)

### Takeaway
Tool pages are templated SEO pages that serve one job: send the visitor into the editor preconfigured for that tool (`/new?tool=X&source=/tools/...`). There's **no inline upload box on the landing page**; the hero is H1 + one-line benefit + a single CTA + "No credit card required" + "4.6 · 2,100+ reviews". The rest is a fixed template: benefit copy → 3-step how-to (with HowTo schema) → demo video → feature blocks → FAQ (FAQPage schema) → testimonials → closing CTA → large internal-link mesh. The pages are light and fast.

### Cited Findings
- LIVE, /tools/video-compressor (2026-11-09):
  - Title: "Video Compressor - Free Video File Compressor, No Quality Loss - VEED". Meta description: "Free video file compressor. Decrease video size by up to 90% with no visible quality loss and real-time size estimates. Free up to 1GB."
  - Hero: breadcrumb "Home › VEED Tools › Video Compressor", badge "Trusted by 1M+ creators", H1 "Video Compressor", sub "Video compression in minutes. Shrink file sizes without visible quality loss", CTA "Compress a video", microcopy "No credit card required", rating "4.6 · 2,100+ reviews".
  - H2 sequence: "Compress video online: Save storage, upload faster, and stream smoothly" → "How to compress a video online:" (Step 01 "Upload your file", Step 02 "Reduce file size", Step 03 "Export or edit") → "Watch this video compressor demo:" (YouTube embed) → "FAQ" → "Loved by creators." → "More from VEED" → "When it comes to amazing videos, all you need is VEED" → "More than an online video compressor".
  - **No `<input type=file>` on the page** (0 found). The CTA "Compress a video" appears three times. All three link to `/new?tool=compress`, and one carries `&locale=en&source=%2Ftools%2Fvideo-compressor` for attribution.
  - Internal links: contextual in-copy links (video editor, filler-word remover, hosting, background expand, converter), long-tail child pages (Compress AVI/MKV/MOV/WebM/WMV, Discord Video Compressor, GIF Compressor, MP4 Compressor, Android, YouTube) and related tools (Extract Audio, Repurpose, Resize, Share, Downloader, Feedback Tool, YouTube to GIF).
  - Structured data: SoftwareApplication (aggregateRating 4.6 / 2,139, offer price 0 USD), BreadcrumbList, HowTo, VideoObject, FAQPage.
  - Page speed: a single desktop measurement in my browser gave DOMContentLoaded 188 ms, load 436 ms, HTML transfer about 30 KB, 58 resources. This is anecdotal, one run, not a CrUX or Lighthouse figure.
  - [veed.io/tools/video-compressor](https://www.veed.io/tools/video-compressor)
- /tools/auto-subtitle-generator-online: badge "Trusted by 1M+ creators", H1 "Auto Subtitle Generator Online", sub "Automatically generate subtitles to make your video accessible to all audiences", CTA "Generate subtitles" (three times), "4.6 · 2,100+ reviews", a logo wall (Visa, Merck, Target, P&G, Meta, Amazon, Google, BBC, NBCUniversal, UBS, Netflix…), three steps ("Auto-generate subtitles" / "Change subtitle styles, personalize, animate, and more" / "Export your video or download the subtitle file"), demo video, three feature blocks with a stat ("Around 85% of videos on mobile are watched without sound"), 10 FAQs (including "Is VEED's auto subtitle generator free?" → "free to start"), testimonials ("Loved by the Fortune 500"), closing CTA plus "No credit card required", about 45 "Discover more" links to language and variant pages, and 10 "Explore related tools" links. — [veed.io/tools/auto-subtitle-generator-online](https://www.veed.io/tools/auto-subtitle-generator-online)
- Homepage (2026-11-09): repositioned toward AI generation. H1 "AI video creation, made for social", sub "Imagine it. Generate it. Brand it. AI videos worth posting, in minutes.", CTAs "Create AI video" and "AI Edit", a strap "1500+ 5 star reviews", an avatar/example carousel (Explainer, Product Demo, Ad, Testimonials, Thought Leadership), "Powering millions of teams globally" logos, three cards (Generate / Subtitles / Brand), testimonials, and a "G2 Best AI software company 2026" badge. The homepage shows no "free / no credit card / watermark" copy. — [veed.io](https://www.veed.io/)
- Pricing page footer and mega-menu: tool hubs grouped as Generation (AI Video Generator, Text to Video, AI Avatars, Dubbing…), Video Editing (Video Editor, Add Subtitles, Compressor, Converter, Background Remover…) and API (Subtitle API, Lip Sync API…), with resources such as "Alternatives" (comparison pages). — [veed.io/pricing](https://www.veed.io/pricing)

### Inferences
- Template to copy for a "3D model from photo" page: an H1 with the exact keyword; a one-line outcome; one CTA verb matching the job ("Get 3D model"); "No credit card required"; a rating line; 3 how-to steps with HowTo schema; a demo; 6–10 FAQs with FAQPage schema (including "Is it free?"); a long-tail child-page mesh (per format GLB/USDZ/OBJ, per furniture type, per retailer…); and the same CTA repeated about 3 times.
- VEED deliberately doesn't put the upload box on the landing page. The CTA opens the app, where upload is the first modal. This keeps landing pages static, fast and cacheable while the app does the heavy work. For an ads-driven funnel, though, an inline photo/URL input on the landing page could reduce one click. That would need A/B testing, not a copy of VEED.
- The `source=` parameter on the CTA lets VEED attribute signups and revenue to each SEO page. Copy this.

### Gaps
- I didn't fetch an AI-avatar tool page; its anatomy may differ (it's generation-first).
- No lab Core Web Vitals data was collected.

## 5. Onboarding after signup (questions, templates, empty states, email nurture)

### Takeaway
According to one third-party teardown, after auth VEED asks segmentation questions (use case, role, acquisition source, email preferences), shows pricing before first value, shows a $50 referral pop-up on dashboard entry, and then lands on a deliberately minimal dashboard with two actions (Generate / Upload). Email nurture content was not found.

### Cited Findings
- 3P (Supademo user-flow gallery, page generated 2026-11-03): pre-signup risk reducers are "Start for free", "No credit card required" and a G2 rating. Auth is a four-screen flow (Google, Apple, Microsoft SSO, passwordless email). Next come segmentation questions (use case, role, acquisition source, email preferences), then a pricing screen before any generation, then a $50 referral pop-up on dashboard entry (the reviewer criticises this: "Retention mechanics work after satisfaction"). The empty-state dashboard has two primary actions, "Generate" and "Upload", with no feature grid or onboarding modal. The generate path is format → generator → prompt → progress %, ending in the first AI video with download or regenerate. Estimated time to value is about 5–8 minutes. — [Supademo: VEED user flow](https://supademo.com/user-flow-examples/veed)
- The help center confirms the OTP email login and a "Stay signed in?" prompt. — [VEED support](https://support.veed.io/en/articles/10491439-sign-up-and-log-in-to-our-web-app)

### Inferences
- Note that the tool-page flow I observed (anonymous editor → signup at download) skips the generic dashboard onboarding entirely for the first artefact. Users arriving via SEO or ads get value first and the questionnaire after. The Supademo flow describes the homepage "Start for free" path, which is a different entry point.
- For a small startup: keep signup at the download moment and defer questions (or ask just one, such as "What will you use the model for?") until after the first download.

### Gaps
- No teardown of VEED's onboarding or lifecycle email sequence was found. Sequenzy has a VEED email-examples page, but its content wasn't retrieved. — [sequenzy.com/email-examples/brands/veed](https://www.sequenzy.com/email-examples/brands/veed)
- I didn't verify the segmentation questions myself (no account was created).

## 6. Public numbers: users, revenue/ARR, funding, team (dated)

### Takeaway
VEED was bootstrapped until 2022 and raised a single $35M Series A (Sequoia, Feb 2022). Its CEO publicly cited about $50M ARR "as of last year" (that is, 2025) and 10M+ users (June 2026). All revenue figures are self-reported or third-party estimates.

### Cited Findings
- $50M ARR and over 10M users, attributed to CEO Sabba Keynejad via a LinkedIn post, reported 17 Jun 2026 ("$50M ARR as of last year"). The same source cites +15% growth and a 40% churn reduction. A related Oct 2025 signal cites "10M+ monthly users". — [ARR Club](https://www.arr.club/veed/veed-surpasses-50m-arr-with-10m-users)
- Other estimates: Latka puts revenue at $50M (Dec 2025), Sacra at $45M (2024), and a founder-written post cites $40M ARR. — [Latka](https://getlatka.com/companies/veed); [Sacra](https://sacra.com/c/veed); [Founderoo](https://founderoo.beehiiv.com/p/the-40m-veed-story). These are from the search summary and estimates, not audited figures.
- Funding: a $35M Series A in Feb 2022 led by Sequoia, the only external round. Before that it was bootstrapped; Latka's 2020 interview lists $0 funding. The co-founders are Sabba Keynejad (CEO) and Timur Mamedov (CTO). — [Sequoia](https://sequoiacap.com/article/veed-the-future-of-video); [Latka 2020 interview](https://getlatka.com/companies/veed/interviews/veed-sabba-keynejad-2020)
- Early traction: a podcast titled "How VEED grew to $1.7m ARR in less than 2 years" (Indie Bites, around 2020). — [Indie Bites](https://indiebites.transistor.fm/6)
- On-site claims (2026-11-09): "Trusted by 1M+ creators" (tool pages), "Powering millions of teams globally" (home), "Trusted by millions of teams" (pricing), schema aggregateRating 4.6 from 2,139 ratings, "G2 Best AI software company 2026". — [veed.io](https://www.veed.io/); [video compressor page](https://www.veed.io/tools/video-compressor)

### Inferences
- The on-site user claims are inconsistent (1M+ creators vs millions of teams vs 10M+ users on LinkedIn), which suggests marketing rounding.

### Gaps
- No public free-to-paid conversion rate was found.
- No current team size was found (not in the sources fetched).
- The Sacra, Latka and Founderoo pages were not opened directly; their figures come from the search summary.
- The co-founder named in the brief (Tim Hunkin) did not appear in the sources found; the CTO co-founder is listed as Timur Mamedov.
