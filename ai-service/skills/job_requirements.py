import re
from skills.extractor import extract_known_skills


REQUIRED_HEADINGS = {
    "requirements",
    "required",
    "required qualifications",
    "minimum qualifications",
    "basic qualifications",
    "qualifications",
    "programming skills",
    "web development knowledge",
    "required experience and competencies",
    "required experience",
    "competencies",
    "must-have qualifications",
    "must have qualifications",
    "what we're looking for",
    "what we are looking for",
}

PREFERRED_HEADINGS = {
    "preferred",
    "will be a plus",
    "will be a plus.",
    "is a plus",
    "will be a strong plus",
    "preferred qualifications",
    "nice to have",
    "good to have",
    "bonus qualifications",
    "nice-to-have qualifications",
    "nice to have qualifications",
}

GENERAL_HEADINGS = {
    "responsibilities",
    "what you will do",
    "what you'll do",
    "the opportunity",
    "about the role",
}

PREFERRED_HINTS = [
    "preferred",
    "plus",
    "strong plus",
    "nice to have",
    "good to have",
    "bonus",
    "exposure to",
    "familiarity with",
    "interest in",
]

REQUIRED_HINTS = [
    "required",
    "must have",
    "strong experience",
    "experience with",
    "knowledge of",
]


def split_chunks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n")

    # Put common inline headings on their own lines.
    headings = (
        list(REQUIRED_HEADINGS)
        + list(PREFERRED_HEADINGS)
        + list(GENERAL_HEADINGS)
    )

    for heading in sorted(headings, key=len, reverse=True):
        pattern = re.compile(rf"(^|\n|\.)\s*({re.escape(heading)})\s*:", re.IGNORECASE)
        normalized = pattern.sub(rf"\1\n{heading}\n", normalized)

    chunks = []

    for line in normalized.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue

        # Split very long pasted JD paragraphs into smaller sentence-like chunks.
        parts = re.split(r"(?<=[.!?])\s+", cleaned)

        for part in parts:
            part = part.strip()
            if part:
                chunks.append(part)

    return chunks


def detect_heading(chunk: str) -> str | None:
    normalized = chunk.lower().strip().rstrip(":")

    if normalized in PREFERRED_HEADINGS:
        return "preferred"

    if normalized in REQUIRED_HEADINGS:
        return "required"

    if normalized in GENERAL_HEADINGS:
        return "general"

    return None


def has_any_hint(text: str, hints: list[str]) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in hints)


def extract_job_requirements(job_description: str) -> dict[str, list[str]]:
    current_section = "general"

    required_set = set()
    preferred_set = set()
    general_set = set()

    for chunk in split_chunks(job_description):
        heading = detect_heading(chunk)

        if heading:
            current_section = heading
            continue

        skills = extract_known_skills(chunk)

        if not skills:
            continue

        # Sentence-level preferred detection is important for phrases like:
        # "Familiarity with Go is a plus."
        if current_section == "preferred" or has_any_hint(chunk, PREFERRED_HINTS):
            preferred_set.update(skills)
            continue

        if current_section == "required" or has_any_hint(chunk, REQUIRED_HINTS):
            required_set.update(skills)
            continue

        general_set.update(skills)

    # Responsibilities/general skills are usually relevant, but do not override
    # explicit preferred-only classifications.
    required_set.update(skill for skill in general_set if skill not in preferred_set)

    return {
        "required_skills": sorted(required_set),
        "preferred_skills": sorted(preferred_set - required_set),
    }
