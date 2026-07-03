import re

from skills.taxonomy import KNOWN_SKILLS


def extract_known_skills(text: str) -> list[str]:
    text_to_search = text.lower()
    found_skills = set()

    for skill_alias, canonical_name in KNOWN_SKILLS.items():
        pattern = r"\b" + re.escape(skill_alias) + r"\b"

        if re.search(pattern, text_to_search):
            found_skills.add(canonical_name)

    return sorted(found_skills)