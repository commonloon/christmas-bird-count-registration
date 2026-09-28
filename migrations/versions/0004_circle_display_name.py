"""add circle_name (display name of the count circle itself, distinct from the
managing organization's name), backfill Vancouver's

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-30

"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('circles', sa.Column('circle_name', sa.String(200)))

    op.execute(
        "UPDATE circles SET circle_name = 'Vancouver' WHERE slug = 'vancouver'"
    )

    op.alter_column('circles', 'circle_name', nullable=False)


def downgrade():
    op.drop_column('circles', 'circle_name')
