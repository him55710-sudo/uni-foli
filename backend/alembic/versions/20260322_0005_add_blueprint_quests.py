"""add blueprints and quests

Revision ID: 20260322_0005
Revises: 20260322_0004
Create Date: 2026-03-22 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = '20260322_0005'
down_revision = '20260322_0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'blueprints' not in tables:
        op.create_table('blueprints',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('diagnosis_run_id', sa.String(), nullable=True),
        sa.Column('headline', sa.String(length=500), nullable=True),
        sa.Column('recommended_focus', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['diagnosis_run_id'], ['diagnosis_runs.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_blueprints_project_id'), 'blueprints', ['project_id'], unique=False)

    if 'quests' not in tables:
        op.create_table('quests',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('blueprint_id', sa.String(), nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('summary', sa.String(), nullable=False),
        sa.Column('difficulty', sa.String(), nullable=False),
        sa.Column('why_this_matters', sa.String(), nullable=False),
        sa.Column('expected_record_impact', sa.String(), nullable=False),
        sa.Column('recommended_output_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['blueprint_id'], ['blueprints.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_quests_blueprint_id'), 'quests', ['blueprint_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'quests' in tables:
        op.drop_index(op.f('ix_quests_blueprint_id'), table_name='quests')
        op.drop_table('quests')
        
    if 'blueprints' in tables:
        op.drop_index(op.f('ix_blueprints_project_id'), table_name='blueprints')
        op.drop_table('blueprints')
