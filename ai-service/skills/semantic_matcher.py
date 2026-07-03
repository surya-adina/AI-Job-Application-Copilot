from difflib import SequenceMatcher


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


def find_semantic_matches(
    resume_skills: list[str],
    job_skills: list[str],
    threshold: float = 0.72,
) -> list[dict]:
    matches = []

    for job_skill in job_skills:
        best_match = None
        best_score = 0.0

        for resume_skill in resume_skills:
            score = similarity(resume_skill, job_skill)

            if score > best_score:
                best_score = score
                best_match = resume_skill

        if best_match and best_score >= threshold:
            matches.append(
                {
                    "job_skill": job_skill,
                    "resume_skill": best_match,
                    "similarity": round(best_score, 3),
                }
            )

    return matches