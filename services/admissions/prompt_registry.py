from __future__ import annotations

from dataclasses import dataclass
import json

from app.core.config import PROJECT_ROOT


@dataclass(slots=True)
class PromptTemplateBundle:
    key: str
    version: str
    kind: str
    description: str
    system_text: str
    user_text: str
    schema_text: str
    schema_json: dict[str, object]


class PromptRegistry:
    def __init__(self) -> None:
        self.registry_path = PROJECT_ROOT / "prompts" / "claim_extraction" / "registry.json"

    def get(self, key: str) -> PromptTemplateBundle:
        registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        if key not in registry:
            raise KeyError(f"Unknown prompt template key: {key}")
        item = registry[key]
        system_path = PROJECT_ROOT / item["system_path"]
        user_path = PROJECT_ROOT / item["user_path"]
        schema_path = PROJECT_ROOT / item["schema_path"]
        schema_text = schema_path.read_text(encoding="utf-8")
        return PromptTemplateBundle(
            key=key,
            version=item["version"],
            kind=item["kind"],
            description=item["description"],
            system_text=system_path.read_text(encoding="utf-8"),
            user_text=user_path.read_text(encoding="utf-8"),
            schema_text=schema_text,
            schema_json=json.loads(schema_text),
        )


prompt_registry = PromptRegistry()
