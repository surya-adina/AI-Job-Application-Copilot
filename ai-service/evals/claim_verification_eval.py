"""Evaluate verify_claims on hand-labeled claims.

    python evals/claim_verification_eval.py

Each case is a claim about a candidate, the resume quotes it cites, and a label
for whether the claim is actually true of the resume. The positive class is
"unsupported" (what the verifier should reject):
  precision = rejected claims that really were unsupported
  recall    = unsupported claims that were rejected

Deterministic: no API calls. The labels were written together with the
verifier rules, so these numbers describe behaviour on known patterns, not
generalization; the agent evals measure unsupported-claim rates on real drafts.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skills.claim_verifier import Claim, verify_claim  # noqa: E402

DATA_PATH = ROOT / "evals" / "data" / "claim_verification_cases.json"
RESULTS_DIR = ROOT / "evals" / "results"


def main() -> None:
    data = json.loads(DATA_PATH.read_text())
    resumes = data["resumes"]

    tp = fp = fn = tn = 0
    by_kind = defaultdict(lambda: {"cases": 0, "correct": 0})
    errors = []

    for case in data["cases"]:
        verdict = verify_claim(Claim(**case["claim"]), resumes[case["resume"]])
        rejected = not verdict.supported
        unsupported = not case["supported"]

        tp += rejected and unsupported
        fp += rejected and not unsupported
        fn += not rejected and unsupported
        tn += not rejected and not unsupported

        correct = rejected == unsupported
        by_kind[case["kind"]]["cases"] += 1
        by_kind[case["kind"]]["correct"] += correct
        if not correct:
            errors.append(
                {
                    "id": case["id"],
                    "kind": case["kind"],
                    "error": "missed_unsupported_claim" if unsupported else "rejected_supported_claim",
                    "claim": case["claim"]["text"],
                    "reasons": verdict.reasons,
                }
            )

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cases": len(data["cases"]),
        "unsupported_cases": tp + fn,
        "rejection": {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)},
        "accuracy": round((tp + tn) / len(data["cases"]), 3),
        "confusion": {"rejected_unsupported": tp, "rejected_supported": fp, "passed_unsupported": fn, "passed_supported": tn},
        "by_kind": dict(by_kind),
        "errors": errors,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = RESULTS_DIR / f"claim_verification_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2))

    print(f"cases={report['cases']} unsupported={report['unsupported_cases']}")
    print(f"rejection precision={precision:.3f} recall={recall:.3f} f1={f1:.3f} accuracy={report['accuracy']}")
    print(f"confusion={report['confusion']}")
    for kind, counts in sorted(report["by_kind"].items()):
        print(f"  {kind:20} {counts['correct']}/{counts['cases']}")
    for error in errors:
        print(f"  ERROR {error['error']}: {error['id']} -> {error['reasons']}")
    print(f"Report: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
