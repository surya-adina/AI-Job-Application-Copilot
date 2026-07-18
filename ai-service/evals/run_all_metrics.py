import subprocess
import sys


def run_command(label: str, command: list[str]):
    print(f"\n=== {label} ===")

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
    )

    print(result.stdout)

    if result.returncode != 0:
        print(result.stderr)
        sys.exit(result.returncode)


def main():
    run_command(
        "Skill Matching Metrics",
        ["python", "evals/compare_skill_matching.py"],
    )

    run_command(
        "AI Endpoint Metrics",
        ["python", "evals/measure_ai_endpoint_metrics.py"],
    )

    print("\nAll metrics completed successfully.")


if __name__ == "__main__":
    main()