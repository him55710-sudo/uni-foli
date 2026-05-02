from __future__ import annotations

import json
from pathlib import Path

import pytest

from unifoli_api.services.prompt_registry import (
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
    assert "학업역량" in composed
    assert "community_contribution" in composed


def test_prompt_registry_loads_workshop_copilot_v2() -> None:
    registry = PromptRegistry()

    asset = registry.get_asset("chat.workshop-copilot-v2")
    composed = registry.compose_prompt("chat.workshop-copilot-v2")

    assert asset.meta.category == "chat"
    assert asset.meta.version == "2.0.0"
    assert "student-record-grounded report copilot" in composed
    assert "report_drafting" in composed
    assert "[DRAFT_PATCH]" in composed


def test_prompt_registry_falls_back_to_backend_registry_assets() -> None:
    registry = PromptRegistry()

    asset = registry.get_asset("diagnosis.semantic-scoring")

    assert asset.meta.category == "diagnosis"
    assert asset.full_path.name == "prompt.md"
    assert "{{criteria_context}}" in asset.markdown
    assert "공식 기준은 학생 행동의 증거가 아니라 평가 맥락" in asset.markdown


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

