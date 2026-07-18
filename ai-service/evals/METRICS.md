# Skill Matching Evaluation Metrics

This evaluation measures deterministic resume-job skill matching across development and holdout benchmark cases.

## Dataset

- Development cases: 3
- Holdout cases: 8
- Total benchmark cases: 11

The holdout set includes harder cases such as:
- Negated skill mentions
- Learning-only skill mentions
- Resume/job skill mismatch cases
- Alias-heavy skill mentions

## Improvement: Weak-Context Filtering

Weak-context filtering prevents the matcher from counting skills as experience when they appear in phrases such as:

- "no experience with"
- "no professional experience with"
- "currently learning"
- "tutorials"

## Holdout Results

| Metric | Before | After |
|---|---:|---:|
| Required skill false positives | 1 | 0 |
| Preferred skill false positives | 3 | 0 |
| Total false positive skill matches | 4 | 0 |
| Required missing-skill recall | 50.0% | 100.0% |
| Preferred missing-skill recall | 82.4% | 100.0% |

## Resume-Safe Summary

Implemented a labeled skill-matching evaluation suite across 11 resume-job benchmark cases and added weak-context filtering, reducing false positive skill matches on holdout cases from 4 to 0 while improving missing-skill recall from 50.0% / 82.4% to 100.0%.