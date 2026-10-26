"""Model-based judge for the agent evals.

Uses a stronger model than the agents (EVAL_JUDGE_MODEL, default gpt-4.1) so
the judge is not grading its own model's work. Its agreement with human labels
is measured on evals/data/rewrite_faithfulness_cases.json before its numbers
are used for anything else.
"""

import json
import os
from pathlib import Path

from pydantic import BaseModel

from llm import RunMetadata, call_structured

PROMPTS = Path(__file__).resolve().parent / "prompts"
JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "gpt-4.1")


class RewriteJudgement(BaseModel):
    adds_content: bool
    added: list[str]
    reason: str


class ParagraphJudgement(BaseModel):
    unsupported_claims: list[str]


def judge_rewrite(original: str, rewrite: str) -> tuple[RewriteJudgement, RunMetadata]:
    result = call_structured(
        endpoint="eval:judge_rewrite",
        prompt_version="judge_rewrite_v1",
        system=(PROMPTS / "judge_rewrite_v1.txt").read_text(),
        user=json.dumps({"original": original, "rewrite": rewrite}),
        schema=RewriteJudgement,
        temperature=0,
        max_output_tokens=300,
        model=JUDGE_MODEL,
    )
    return result.parsed, result.metadata


def judge_paragraph(resume: str, paragraph: str) -> tuple[ParagraphJudgement, RunMetadata]:
    result = call_structured(
        endpoint="eval:judge_paragraph",
        prompt_version="judge_paragraph_v1",
        system=(PROMPTS / "judge_paragraph_v1.txt").read_text(),
        user=json.dumps({"resume": resume, "paragraph": paragraph}),
        schema=ParagraphJudgement,
        temperature=0,
        max_output_tokens=400,
        model=JUDGE_MODEL,
    )
    return result.parsed, result.metadata
