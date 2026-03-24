"""add diagnosis runs table

Revision ID: 20260322_0004
Revises: 20260322_0003
Create Date: 2026-03-22 04:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = '20260322_0004'
down_revision = '20260322_0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'diagnosis_runs' not in tables:
        op.create_table('diagnosis_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('result_payload', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_diagnosis_runs_project_id'), 'diagnosis_runs', ['project_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'diagnosis_runs' in tables:
        op.drop_index(op.f('ix_diagnosis_runs_project_id'), table_name='diagnosis_runs')
        op.drop_table('diagnosis_runs')
