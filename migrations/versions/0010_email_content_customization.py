"""add email_content_defaults and email_content_overrides tables

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-09

Storage for the per-circle customizable email content feature
(EMAIL_CUSTOMIZATION_PLAN.txt, config/email_content_blocks.py). Two tables,
not one nullable-circle_slug table, because Postgres unique constraints treat
NULL as distinct from every other NULL - a single table couldn't guarantee
"exactly one global-default row" per block. Both tables start empty; every
block resolves to its hardcoded fallback until an admin edits something, so
this migration changes no visible email content on its own.
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'email_content_defaults',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('email_type', sa.String(50), nullable=False),
        sa.Column('block_key', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.String(254)),
        sa.UniqueConstraint('email_type', 'block_key', name='uq_email_content_defaults_type_block'),
    )

    op.create_table(
        'email_content_overrides',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('circle_slug', sa.String(50), sa.ForeignKey('circles.slug'), nullable=False),
        sa.Column('email_type', sa.String(50), nullable=False),
        sa.Column('block_key', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.String(254)),
        sa.UniqueConstraint('circle_slug', 'email_type', 'block_key', name='uq_email_content_overrides_circle_type_block'),
    )
    op.create_index('ix_email_content_overrides_circle_slug', 'email_content_overrides', ['circle_slug'])


def downgrade():
    op.drop_index('ix_email_content_overrides_circle_slug', table_name='email_content_overrides')
    op.drop_table('email_content_overrides')
    op.drop_table('email_content_defaults')
