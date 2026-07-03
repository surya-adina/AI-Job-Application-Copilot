import math
from skills.embedding_client import embed_texts


def cosine_similarity(left_vector: list[float], right_vector: list[float]) -> float:
    dot_product = sum(left * right for left, right in zip(left_vector, right_vector))

    left_norm = math.sqrt(sum(value * value for value in left_vector))
    right_norm = math.sqrt(sum(value * value for value in right_vector))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def find_semantic_matches(
    resume_skills: list[str],
    job_skills: list[str],
    threshold: float = 0.78,
) -> list[dict]:
    unique_skills = sorted(set(resume_skills + job_skills))
    vectors_by_skill = embed_texts(unique_skills)

    matches = []

    for job_skill in job_skills:
        best_resume_skill = None
        best_score = 0.0
        job_vector = vectors_by_skill[job_skill]

        for resume_skill in resume_skills:
            resume_vector = vectors_by_skill[resume_skill]
            score = cosine_similarity(resume_vector, job_vector)

            if score > best_score:
                best_score = score
                best_resume_skill = resume_skill

        if best_resume_skill and best_score >= threshold:
            matches.append(
                {
                    "job_skill": job_skill,
                    "resume_skill": best_resume_skill,
                    "similarity": round(best_score, 3),
                }
            )

    return matches