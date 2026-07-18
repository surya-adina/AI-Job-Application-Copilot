# AI Endpoint Metrics

This benchmark measures latency and estimated token cost for the FastAPI AI service endpoints using a fixed resume and job description payload.

## Endpoints Tested

- `/analyze`
- `/resume-review`
- `/cover-letter`
- `/interview-prep`

## Results

| Endpoint | Latency | Tokens | Estimated Cost |
|---|---:|---:|---:|
| Analysis | 4780 ms | 779 | $0.000205 |
| Resume Review | 2698 ms | 1014 | $0.000236 |
| Cover Letter | 2792 ms | 546 | $0.000171 |
| Interview Prep | 5538 ms | 839 | $0.000372 |

## Summary

| Metric | Value |
|---|---:|
| Endpoints tested | 4 |
| Successful endpoints | 4 |
| Average measured latency | 3952 ms |
| Average measured latency | 3.95 seconds |

## Notes

The benchmark was run locally against the FastAPI service on `localhost:8000`.

Generated JSON reports are saved under:

```text
ai-service/evals/results/