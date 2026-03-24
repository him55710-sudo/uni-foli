"""add workshop models

Revision ID: 20260322_0006
Revises: 20260322_0005
Create Date: 2026-03-22 05:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '20260322_0006'
down_revision = '20260322_0005'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'workshop_sessions' not in tables:
        op.create_table('workshop_sessions',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('quest_id', sa.String(), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=False),
            sa.Column('context_score', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
            sa.ForeignKeyConstraint(['quest_id'], ['quests.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_workshop_sessions_project_id'), 'workshop_sessions', ['project_id'], unique=False)
        op.create_index(op.f('ix_workshop_sessions_quest_id'), 'workshop_sessions', ['quest_id'], unique=False)

    if 'workshop_turns' not in tables:
        op.create_table('workshop_turns',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('session_id', sa.String(length=36), nullable=False),
            sa.Column('turn_type', sa.String(length=32), nullable=False),
            sa.Column('query', sa.Text(), nullable=False),
            sa.Column('response', sa.Text(), nullable=True),
            sa.Column('action_payload', JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['session_id'], ['workshop_sessions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_workshop_turns_session_id'), 'workshop_turns', ['session_id'], unique=False)

    if 'pinned_references' not in tables:
        op.create_table('pinned_references',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('session_id', sa.String(length=36), nullable=False),
            sa.Column('text_content', sa.Text(), nullable=False),
            sa.Column('source_type', sa.String(length=32), nullable=True),
            sa.Column('source_id', sa.String(length=36), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['session_id'], ['workshop_sessions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_pinned_references_session_id'), 'pinned_references', ['session_id'], unique=False)

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'pinned_references' in tables:
        op.drop_index(op.f('ix_pinned_references_session_id'), table_name='pinned_references')
        op.drop_table('pinned_references')
        
    if 'workshop_turns' in tables:
        op.drop_index(op.f('ix_workshop_turns_session_id'), table_name='workshop_turns')
        op.drop_table('workshop_turns')
        
    if 'workshop_sessions' in tables:
        op.drop_index(op.f('ix_workshop_sessions_quest_id'), table_name='workshop_sessions')
        op.drop_index(op.f('ix_workshop_sessions_project_id'), table_name='workshop_sessions')
        op.drop_table('workshop_sessions')
