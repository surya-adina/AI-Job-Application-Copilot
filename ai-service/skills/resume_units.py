"""Split resume text into editable units (bullets and paragraphs) and splice
rewritten units back in.

Text extracted from a PDF breaks a long bullet across several lines:

    • Engineered a graph-based pattern mining pipeline on 9,787 real Amazon weblog
    sessions; extracted 129,830 access patterns.

A line without a bullet marker continues the unit above it when that unit's
last line ran close to the full text width (the text wrapped) or when the line
starts mid-sentence (lowercase, digit or punctuation). Short lines such as
"Tech: Python, Docker" followed by a project title stay separate.

Offsets always point into the original text, so a rewrite replaces exactly the
unit's span and the bullet marker and surrounding layout are kept.
"""

import re
from dataclasses import dataclass

BULLET_MARKER = re.compile(r"^\s*(?:[•▪●◦·*–—]|-(?=\s))\s*")
MIN_WORDS = 5
WRAP_RATIO = 0.75


@dataclass
class ResumeUnit:
    id: int
    text: str
    start: int
    end: int
    bullet: bool
    last_line_length: int = 0


def _wrap_width(lines: list[str]) -> int:
    lengths = sorted(len(line.strip()) for line in lines if len(line.strip()) >= 20)
    if not lengths:
        return 0
    return lengths[int(0.9 * (len(lengths) - 1))]


def _looks_like_heading(line: str, width: int) -> bool:
    """Project titles, section names and job titles: "Stock Analyzer | GitHub"."""
    if " | " in line:
        return True
    words = [word for word in line.split() if word[0].isalpha()]
    if not words or (width and len(line) >= 0.7 * width):
        return False
    return sum(word[0].isupper() for word in words) / len(words) >= 0.7


def _continues(unit: ResumeUnit, line: str, width: int) -> bool:
    first = line[0]
    if first.islower() or first.isdigit() or first in "(,;&+/%":
        return True
    if _looks_like_heading(line, width) or unit.text.endswith((".", "!", "?")):
        return False
    return width > 0 and unit.last_line_length >= WRAP_RATIO * width


def resume_units(text: str) -> list[ResumeUnit]:
    raw_lines = text.splitlines(keepends=True)
    width = _wrap_width(raw_lines)

    units: list[ResumeUnit] = []
    current: ResumeUnit | None = None
    offset = 0

    for raw_line in raw_lines:
        line_start = offset
        offset += len(raw_line)
        line = raw_line.rstrip("\r\n")

        marker = BULLET_MARKER.match(line)
        content = line[marker.end() :].strip() if marker else line.strip()
        if not content:
            current = None
            continue

        content_start = line_start + line.find(content, marker.end() if marker else 0)
        content_end = content_start + len(content)

        if current is not None and not marker and _continues(current, content, width):
            current.text = f"{current.text} {content}"
            current.end = content_end
            current.last_line_length = len(line.strip())
            continue

        current = ResumeUnit(
            id=len(units),
            text=content,
            start=content_start,
            end=content_end,
            bullet=bool(marker),
            last_line_length=len(line.strip()),
        )
        units.append(current)

    kept = [unit for unit in units if len(unit.text.split()) >= MIN_WORDS]
    for index, unit in enumerate(kept):
        unit.id = index
    return kept


def apply_rewrites(text: str, units: list[ResumeUnit], rewrites: dict[int, str]) -> str:
    """Replace each rewritten unit's span; units without a rewrite stay as they are."""
    by_id = {unit.id: unit for unit in units}
    result = text
    for unit_id in sorted(rewrites, key=lambda i: by_id[i].start, reverse=True):
        unit = by_id[unit_id]
        result = result[: unit.start] + rewrites[unit_id].strip() + result[unit.end :]
    return result
