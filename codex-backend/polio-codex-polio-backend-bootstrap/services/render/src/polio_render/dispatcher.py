from polio_domain.enums import RenderFormat
from polio_render.formats.base import BaseRenderer
from polio_render.formats.hwpx_renderer import HwpxRenderer
from polio_render.formats.pdf_renderer import PdfRenderer
from polio_render.formats.pptx_renderer import PptxRenderer
from polio_render.models import RenderArtifact, RenderBuildContext


RENDERERS: dict[RenderFormat, type[BaseRenderer]] = {
    RenderFormat.PDF: PdfRenderer,
    RenderFormat.PPTX: PptxRenderer,
    RenderFormat.HWPX: HwpxRenderer,
}


def dispatch_render(context: RenderBuildContext) -> RenderArtifact:
    renderer_cls = RENDERERS[context.render_format]
    renderer = renderer_cls()
    return renderer.render(context)
