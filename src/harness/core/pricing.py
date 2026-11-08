"""Unit prices in USD used to record ``cost_usd`` for every external call.

All values are placeholders until verified against the provider's pricing page.
"""

# TODO verificar 2026-11-08 https://platform.tripo3d.ai/pricing
TRIPO_USD_PER_MODEL = 0.25

# TODO verificar 2026-11-08 https://docs.meshy.ai/en/api/pricing
MESHY_USD_PER_MODEL = 0.65

# TODO verificar 2026-11-08 https://ai.google.dev/gemini-api/docs/pricing
GEMINI_IMAGE_USD = 0.039

# TODO verificar 2026-11-08 https://platform.claude.com/docs/en/about-claude/pricing
# (placeholder; the cached Claude pricing table lists claude-sonnet-5-5 at 2.0 / 10.0 USD/MTok)
ANTHROPIC_INPUT_USD_PER_MTOK = 3.0
# TODO verificar 2026-11-08 https://platform.claude.com/docs/en/about-claude/pricing
ANTHROPIC_OUTPUT_USD_PER_MTOK = 15.0
