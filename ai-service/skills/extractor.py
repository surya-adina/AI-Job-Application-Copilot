import re
from skills.taxonomy import KNOWN_SKILLS


WEAK_CONTEXT_PHRASES = [
    "no professional experience with",
    "no experience with",
    "not experienced with",
    "currently learning",
    "learning",
    "tutorials",
]


def has_weak_context(text: str, start_index: int) -> bool:
    window_start = max(0, start_index - 80)
    context_window = text[window_start:start_index].lower()

    return any(phrase in context_window for phrase in WEAK_CONTEXT_PHRASES)


def extract_known_skills(
    text: str,
    ignore_weak_context: bool = True,
) -> list[str]:
    text_to_search = text.lower()
    found_skills = set()

    for skill_alias, canonical_name in KNOWN_SKILLS.items():
        pattern = r"\b" + re.escape(skill_alias) + r"\b"

        for match in re.finditer(pattern, text_to_search):
            if ignore_weak_context and has_weak_context(
                text_to_search,
                match.start(),
            ):
                continue

            found_skills.add(canonical_name)

    return sorted(found_skills)