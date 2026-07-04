import re
from skills.extractor import extract_known_skills

REQUIRED_SECTION_MARKERS = [
    "required qualifications",
    "minimum qualifications",
    "basic qualifications",
    "must have",
    "what you need",
    "who you are and what you have",
    "who you are",
]

PREFERRED_SECTION_MARKERS = [
    "preferred qualifications",
    "nice to have",
    "good to have",
    "bonus qualifications",
]


def normalize_job_description(text: str) -> str:
    normalized = text

    all_markers = REQUIRED_SECTION_MARKERS + PREFERRED_SECTION_MARKERS

    for marker in sorted(all_markers, key=len, reverse=True):
        pattern = re.compile(re.escape(marker), re.IGNORECASE)
        normalized = pattern.sub(f"\n{marker.title()}\n", normalized)

    return normalized


def split_job_description_sections(job_description: str) -> dict[str, str]:
    normalized_description = normalize_job_description(job_description)
    lines = normalized_description.splitlines()

    current_section = "general"
    sections = {
        "general": [],
        "required": [],
        "preferred": [],
    }

    for line in lines:
        cleaned_line = line.strip()
        normalized_line = cleaned_line.lower().rstrip(":")

        if not cleaned_line:
            continue

        if any(marker == normalized_line for marker in PREFERRED_SECTION_MARKERS):
            current_section = "preferred"
            continue

        if any(marker == normalized_line for marker in REQUIRED_SECTION_MARKERS):
            current_section = "required"
            continue

        sections[current_section].append(cleaned_line)

    return {
        section: "\n".join(content)
        for section, content in sections.items()
    }


def extract_job_requirements(job_description: str) -> dict[str, list[str]]:
    sections = split_job_description_sections(job_description)

    required_skills = extract_known_skills(sections["required"])
    preferred_skills = extract_known_skills(sections["preferred"])
    general_skills = extract_known_skills(sections["general"])

    required_set = set(required_skills)
    preferred_set = set(preferred_skills)

    if not required_set:
        required_set.update(general_skills)
    else:
        required_set.update(
            skill for skill in general_skills
            if skill not in preferred_set
        )

    return {
        "required_skills": sorted(required_set),
        "preferred_skills": sorted(preferred_set - required_set),
    }