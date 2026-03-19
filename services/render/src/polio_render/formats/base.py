from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from polio_render.models import RenderArtifact, RenderBuildContext
from polio_shared.paths import get_export_root, slugify


class BaseRenderer(ABC):
    extension = ".bin"
    implementation_level = "stub"

    @abstractmethod
    def render(self, context: RenderBuildContext) -> RenderArtifact:
        raise NotImplementedError

    def prepare_output_path(self, context: RenderBuildContext) -> Path:
        target_dir = get_export_root() / context.project_id / context.job_id
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{slugify(context.draft_title)}{self.extension}"
        return target_dir / filename
