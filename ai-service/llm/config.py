"""Model and pricing configuration for every LLM call in the AI service.

Prices are USD per 1M tokens. Keep this table in sync with OpenAI's pricing
page; a model missing from the table gets estimated_cost_usd=None instead of
a made-up number. You can override the price for the active model with
OPENAI_PRICE_INPUT_PER_MTOK / OPENAI_PRICE_OUTPUT_PER_MTOK.
"""

import os

DEFAULT_MODEL = "gpt-4o-mini"

PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4.1": (2.00, 8.00),
}


def get_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def get_max_retries() -> int:
    return int(os.getenv("LLM_MAX_RETRIES", "2"))


def get_timeout_seconds() -> float:
    return float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float | None:
    override_in = os.getenv("OPENAI_PRICE_INPUT_PER_MTOK")
    override_out = os.getenv("OPENAI_PRICE_OUTPUT_PER_MTOK")

    if override_in and override_out:
        price_in, price_out = float(override_in), float(override_out)
    else:
        # Match dated snapshots such as "gpt-4o-mini-2024-07-18" to their base model.
        base = next(
            (name for name in sorted(PRICING_PER_MTOK, key=len, reverse=True) if model.startswith(name)),
            None,
        )
        if base is None:
            return None
        price_in, price_out = PRICING_PER_MTOK[base]

    return round(tokens_in * price_in / 1_000_000 + tokens_out * price_out / 1_000_000, 8)
