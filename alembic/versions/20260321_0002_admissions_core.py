from __future__ import annotations

from alembic import op

from db.base import Base
from db.models.admissions import AdmissionCycle, AdmissionTrack, EvaluationDimension, Source, SourceCrawlJob, University
from db.models.audit import Citation, PolicyFlag, ResponseTrace, ReviewTask
from db.models.content import (
    Claim,
    ClaimEvidence,
    ConflictRecord,
    Document,
    DocumentChunk,
    DocumentVersion,
    ExtractionJob,
    FileObject,
    IngestionJob,
    ParsedBlock,
    RetrievalIndexRecord,
)
from db.models.security import Account, AuthSession, DeletionEvent, DeletionRequest, PrivacyScan, Role, Tenant
from db.models.student import StudentAnalysisRun, StudentArtifact, StudentFile

# revision identifiers, used by Alembic.
revision = "20260321_0002"
down_revision = "20260320_0001"
branch_labels = None
depends_on = None


TABLES_IN_ORDER = [
    Source.__table__,
    University.__table__,
    EvaluationDimension.__table__,
    Tenant.__table__,
    Role.__table__,
    Account.__table__,
    AuthSession.__table__,
    FileObject.__table__,
    AdmissionCycle.__table__,
    AdmissionTrack.__table__,
    SourceCrawlJob.__table__,
    Document.__table__,
    DocumentVersion.__table__,
    ParsedBlock.__table__,
    DocumentChunk.__table__,
    IngestionJob.__table__,
    ExtractionJob.__table__,
    Claim.__table__,
    ClaimEvidence.__table__,
    ConflictRecord.__table__,
    RetrievalIndexRecord.__table__,
    StudentFile.__table__,
    StudentArtifact.__table__,
    StudentAnalysisRun.__table__,
    ResponseTrace.__table__,
    Citation.__table__,
    PolicyFlag.__table__,
    ReviewTask.__table__,
    DeletionRequest.__table__,
    DeletionEvent.__table__,
    PrivacyScan.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind, tables=TABLES_IN_ORDER, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=list(reversed(TABLES_IN_ORDER)), checkfirst=True)
