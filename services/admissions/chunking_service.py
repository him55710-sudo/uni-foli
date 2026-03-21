from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from db.models.content import DocumentChunk, ParsedBlock


@dataclass(slots=True)
class ChunkingConfig:
    target_chars: int = 1200
    overlap_chars: int = 160


class ChunkingService:
    def __init__(self) -> None:
        self.config = ChunkingConfig()

    def build_chunks(
        self,
        *,
        document_id,
        document_version_id,
        parsed_blocks: list[ParsedBlock],
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        current_blocks: list[ParsedBlock] = []
        current_length = 0

        def flush_chunk() -> None:
            nonlocal current_blocks, current_length
            if not current_blocks:
                return
            text = "\n\n".join(block.cleaned_text for block in current_blocks)
            first = current_blocks[0]
            last = current_blocks[-1]
            chunk = DocumentChunk(
                document_id=document_id,
                document_version_id=document_version_id,
                primary_block_id=first.id,
                chunk_index=len(chunks),
                chunk_hash=sha256(
                    f"{document_version_id}:{len(chunks)}:{text}".encode("utf-8")
                ).hexdigest(),
                heading_path=first.heading_path,
                page_start=first.page_start,
                page_end=last.page_end,
                char_start=first.char_start,
                char_end=last.char_end,
                token_estimate=max(1, len(text) // 4),
                content_text=text,
                metadata_json={
                    "block_ids": [str(block.id) for block in current_blocks],
                    "block_indexes": [block.block_index for block in current_blocks],
                },
            )
            chunks.append(chunk)
            if len(text) > self.config.overlap_chars:
                current_blocks = current_blocks[-1:]
                current_length = len(current_blocks[0].cleaned_text)
            else:
                current_blocks = []
                current_length = 0

        for block in parsed_blocks:
            block_length = len(block.cleaned_text)
            if current_blocks and current_length + block_length > self.config.target_chars:
                flush_chunk()
            current_blocks.append(block)
            current_length += block_length

        flush_chunk()
        return chunks


chunking_service = ChunkingService()
