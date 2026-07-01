# Evaluation Harness

This service includes a small evaluation harness for testing resume-to-job match analysis quality across prompt versions.

## What it evaluates

The harness sends fixed resume/job-description pairs to the `/analyze` endpoint and measures:

- pass rate
- matched skill recall
- missing skill recall
- score correctness
- latency
- estimated cost
- prompt version

## Why this exists

Prompt changes should not be judged by vibes.

The goal is to compare prompt versions against the same fixed cases so changes can be measured.

Example:

```text
analysis_v1 vs analysis_v2