"""Unit prices in USD used to record ``cost_usd`` for every external call.

Sources are in ``docs/proveedores.md``. Dollar figures are not invoices: each constant says
where it comes from and what is still unverified.
"""

# Tripo API public price, 0,30–0,40 $/generation (consulted 2026-11-08; not measured in the
# pilot). The lower bound is used. https://platform.tripo3d.ai/pricing
TRIPO_USD_PER_MODEL = 0.30

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
