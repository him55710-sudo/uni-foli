from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.content import Document, DocumentChunk, DocumentVersion, ParsedBlock
from services.admissions.utils import ensure_uuid


class DocumentService:
    def list_documents(self, session: Session) -> list[Document]:
        stmt = select(Document).order_by(Document.created_at.desc())
        return list(session.scalars(stmt))

    def get_document(self, session: Session, document_id: str) -> Document | None:
        return session.get(Document, ensure_uuid(document_id))

    def list_document_chunks(self, session: Session, *, document_id: str) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == ensure_uuid(document_id))
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(session.scalars(stmt))

    def list_document_blocks(self, session: Session, *, document_id: str) -> list[ParsedBlock]:
        stmt = (
            select(ParsedBlock)
            .where(ParsedBlock.document_id == ensure_uuid(document_id))
            .order_by(ParsedBlock.block_index.asc())
        )
        return list(session.scalars(stmt))

    def get_current_version(self, session: Session, *, document_id: str) -> DocumentVersion | None:
        document = self.get_document(session, document_id)
        if document is None or document.current_version_id is None:
            return None
        return session.get(DocumentVersion, document.current_version_id)


document_service = DocumentService()
