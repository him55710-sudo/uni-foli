from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "20260322_0002"
down_revision = "20260320_0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("firebase_uid", sa.String(length=128), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("name", sa.String(length=200), nullable=True),
            sa.Column("target_university", sa.String(length=200), nullable=True),
            sa.Column("target_major", sa.String(length=200), nullable=True),
            sa.Column("grade", sa.String(length=50), nullable=True),
            sa.Column("track", sa.String(length=100), nullable=True),
            sa.Column("career", sa.String(length=200), nullable=True),
            sa.Column("admission_type", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"], unique=True)
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    else:
        # Add new onboarding columns if table exists (e.g., created by auto_create_tables)
        columns = [col["name"] for col in inspector.get_columns("users")]
        if "grade" not in columns:
            op.add_column("users", sa.Column("grade", sa.String(length=50), nullable=True))
            op.add_column("users", sa.Column("track", sa.String(length=100), nullable=True))
            op.add_column("users", sa.Column("career", sa.String(length=200), nullable=True))
            op.add_column("users", sa.Column("admission_type", sa.String(length=100), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "users" in tables:
        columns = [col["name"] for col in inspector.get_columns("users")]
        if "grade" in columns:
            op.drop_column("users", "admission_type")
            op.drop_column("users", "career")
            op.drop_column("users", "track")
            op.drop_column("users", "grade")
