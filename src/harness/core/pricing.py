"""Unit prices in USD used to record ``cost_usd`` for every external call.

Sources are in ``docs/proveedores.md``. Dollar figures are not invoices: each constant says
where it comes from and what is still unverified.
"""

# Tripo API bills credits; "1 credit = $0.01 USD" (https://developers.tripo3d.ai/en/pricing
# and /en/docs/billing, read 2026-11-09). H Series, image- and multiview-to-model cost the
# same: 20 credits without texture, 30 with standard texture, plus stacked add-ons. PBR,
# face_limit, orientation, auto_size and image autofix carry no listed add-on.
# ``harness.clients.tripo.TripoSettings.estimated_credits`` reads this table.
TRIPO_USD_PER_CREDIT = 0.01
TRIPO_CREDITS_BASE_NO_TEXTURE = 20
TRIPO_CREDITS_BASE_TEXTURE = 30
TRIPO_CREDITS_TEXTURE_QUALITY_ADDON = {"fast": 0, "standard": 0, "detailed": 10, "extreme": 20}
TRIPO_CREDITS_GEOMETRY_DETAILED_ADDON = 20  # "HD Geometry Quality" (Ultra mesh)
# Per-piece estimate for the default ``TripoSettings`` (textured, texture_quality and
# geometry_quality "detailed"): 30 + 10 + 20 = 60 credits = 0,60 $. A test checks it equals
# ``TripoSettings().estimated_cost_usd()``.
TRIPO_DEFAULT_CREDITS = (
    TRIPO_CREDITS_BASE_TEXTURE
    + TRIPO_CREDITS_TEXTURE_QUALITY_ADDON["detailed"]
    + TRIPO_CREDITS_GEOMETRY_DETAILED_ADDON
)
TRIPO_USD_PER_MODEL = round(TRIPO_DEFAULT_CREDITS * TRIPO_USD_PER_CREDIT, 4)

# Meshy bills credits: 30 per textured generation (meshy-7.1, 2K) and 10 per retexture
# (2K/4K), from https://docs.meshy.ai/en/api/pricing. There is no public USD price per
# credit, so the USD figure per generation stays provisional.
MESHY_CREDITS_PER_MODEL = 30
MESHY_CREDITS_PER_RETEXTURE = 10
# TODO verificar el precio en USD por crédito de la API de Meshy (sin precio público).
MESHY_USD_PER_MODEL = 0.65
MESHY_USD_PER_CREDIT = MESHY_USD_PER_MODEL / MESHY_CREDITS_PER_MODEL
MESHY_USD_PER_RETEXTURE = round(MESHY_USD_PER_CREDIT * MESHY_CREDITS_PER_RETEXTURE, 4)

# TODO verificar 2026-11-08 https://ai.google.dev/gemini-api/docs/pricing
GEMINI_IMAGE_USD = 0.039

# claude-sonnet-5-5, from the claude-api skill pricing table (cached 2026-10-06).
# TODO verificar 2026-11-08 https://platform.claude.com/docs/en/about-claude/pricing
ANTHROPIC_INPUT_USD_PER_MTOK = 2.0
# TODO verificar 2026-11-08 https://platform.claude.com/docs/en/about-claude/pricing
ANTHROPIC_OUTPUT_USD_PER_MTOK = 10.0
