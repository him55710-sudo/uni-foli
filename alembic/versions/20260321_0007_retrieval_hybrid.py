from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from db.models.eval import RetrievalEvalCase


# revision identifiers, used by Alembic.
revision = "20260321_0007"
down_revision = "20260321_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    RetrievalEvalCase.__table__.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        inspector = inspect(bind)
        existing_indexes = {index["name"] for index in inspector.get_indexes("retrieval_index_records")}
        if "ix_retrieval_index_records_search_tsv" not in existing_indexes:
            op.execute(
                "CREATE INDEX ix_retrieval_index_records_search_tsv "
                "ON retrieval_index_records USING GIN (to_tsvector('simple', searchable_text))"
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_retrieval_index_records_search_tsv")
    RetrievalEvalCase.__table__.drop(bind=bind, checkfirst=True)
