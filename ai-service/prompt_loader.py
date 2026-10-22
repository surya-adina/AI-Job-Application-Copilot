import json
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"
REGISTRY_PATH = PROMPTS_DIR / "prompt_registry.json"


class UnknownPromptError(ValueError):
    pass


def registered_prompts() -> set[str]:
    return set(json.loads(REGISTRY_PATH.read_text()))


def load_prompt(prompt_name: str) -> str:
    # prompt_version comes from request bodies, so only registered names are
    # accepted; this also keeps the name from being used as a file path.
    if prompt_name not in registered_prompts():
        raise UnknownPromptError(f"Unknown prompt version: {prompt_name}")

    return (PROMPTS_DIR / f"{prompt_name}.txt").read_text().strip()
