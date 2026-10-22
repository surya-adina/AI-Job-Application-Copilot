import re
from skills.taxonomy import AMBIGUOUS_ALIASES, KNOWN_SKILLS


WEAK_CONTEXT_PHRASES = [
    "no professional experience with",
    "no experience with",
    "not experienced with",
    "currently learning",
    "learning to use",
    "plan to learn",
    "planning to learn",
    "tutorials",
]


def has_weak_context(text: str, start_index: int) -> bool:
    window_start = max(0, start_index - 80)
    context_window = text[window_start:start_index].lower()

    return any(phrase in context_window for phrase in WEAK_CONTEXT_PHRASES)


def alias_pattern(alias: str) -> re.Pattern:
    # Lookarounds instead of \b so aliases ending in symbols ("c#", "c++") match.
    # "go" followed by a hyphen is "go-to"/"go-live", not the language.
    suffix = r"(?![a-z0-9+#])(?!-)" if alias == "go" else r"(?![a-z0-9+#])"
    return re.compile(r"(?<![a-z0-9])" + re.escape(alias) + suffix)


_PATTERNS = {alias: alias_pattern(alias) for alias in KNOWN_SKILLS}


def extract_known_skills(
    text: str,
    ignore_weak_context: bool = True,
    include_ambiguous: bool = True,
) -> list[str]:
    text_to_search = text.lower()
    found_skills = set()

    for skill_alias, canonical_name in KNOWN_SKILLS.items():
        if not include_ambiguous and skill_alias in AMBIGUOUS_ALIASES:
            continue

        for match in _PATTERNS[skill_alias].finditer(text_to_search):
            if ignore_weak_context and has_weak_context(
                text_to_search,
                match.start(),
            ):
                continue

            found_skills.add(canonical_name)

    return sorted(found_skills)


def canonical_skill(name: str) -> str:
    """Map a free-form skill name ("LLM APIs", "Apache Kafka") to its taxonomy
    name when it clearly refers to one known skill; otherwise keep it as given."""
    cleaned = " ".join(name.split())
    key = cleaned.lower()

    if key in KNOWN_SKILLS:
        return KNOWN_SKILLS[key]

    found = extract_known_skills(cleaned, ignore_weak_context=False)
    return found[0] if len(found) == 1 else cleaned
