from __future__ import annotations

import json
from pathlib import Path

import pytest

from polio_api.services.prompt_registry import (
    PromptAssetNotFoundError,
    PromptRegistry,
)


def test_prompt_registry_loads_known_asset() -> None:
    registry = PromptRegistry()

    asset = registry.get_asset("diagnosis.grounded-analysis")

    assert asset.meta.category == "diagnosis"
    assert asset.meta.version == "1.1.0"
    assert "## Prompt Body" in asset.markdown
    composed = registry.compose_prompt("diagnosis.grounded-analysis")
    assert "Never fabricate student activities" in composed
    assert "diagnosis engine and guided-choice planner" in composed


def test_prompt_registry_missing_prompt_has_clear_error() -> None:
    registry = PromptRegistry()

    with pytest.raises(PromptAssetNotFoundError, match="missing.prompt"):
        registry.get_asset("missing.prompt")


def test_prompt_registry_supports_override_paths(tmp_path: Path) -> None:
    prompt_root = tmp_path / "prompts"
    prompt_root.mkdir()
    asset_dir = prompt_root / "chat" / "override-v1"
    asset_dir.mkdir(parents=True)
    (asset_dir / "prompt.md").write_text(
        "# chat.override\n\n## Prompt Body\n\nOverride prompt body.\n",
        encoding="utf-8",
    )
    (prompt_root / "registry.v1.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "registry_name": "test",
                "prompts": {
                    "chat.override": {
                        "category": "chat",
                        "version": "1.0.0",
                        "relative_path": "chat/override-v1/prompt.md",
                        "description": "Override asset",
                        "output_mode": "markdown",
                        "wiring_status": "test-only",
                        "dependencies": [],
                        "runtime_targets": []
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    registry = PromptRegistry(
        prompt_root=prompt_root,
        registry_path=prompt_root / "registry.v1.json",
    )

    asset = registry.get_asset("chat.override")

    assert asset.body == "Override prompt body."
