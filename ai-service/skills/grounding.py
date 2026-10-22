"""Cheap, deterministic grounding checks.

`find_unsupported_quotes` confirms that text the model says it copied from
the resume actually appears there. It catches invented evidence; it does not
judge whether a paragraph's claim follows from the quote. The full claim
verifier (embeddings + skill extraction) builds on this in the agent milestone.
"""

import re
import unicodedata

_CHAR_MAP = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "•": " ",
    }
)


def normalize_for_match(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_CHAR_MAP).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .,;:!?\"'()[]")


def find_unsupported_quotes(quotes: list[str], source_text: str) -> list[str]:
    source = normalize_for_match(source_text)
    return [quote for quote in quotes if normalize_for_match(quote) and normalize_for_match(quote) not in source]


PLACEHOLDER_PATTERN = re.compile(r"\[[^\]]{1,60}\]")


def find_placeholders(text: str) -> list[str]:
    return PLACEHOLDER_PATTERN.findall(text)
