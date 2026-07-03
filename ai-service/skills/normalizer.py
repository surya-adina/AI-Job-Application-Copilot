from skills.taxonomy import KNOWN_SKILLS


def normalize_skill(raw_skill: str) -> str | None:
    lookup_key = raw_skill.strip().lower()

    return KNOWN_SKILLS.get(lookup_key)