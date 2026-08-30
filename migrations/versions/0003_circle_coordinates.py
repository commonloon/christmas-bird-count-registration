"""add latitude/longitude to circles, backfill Vancouver's coordinates

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-30

"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('circles', sa.Column('latitude', sa.Float))
    op.add_column('circles', sa.Column('longitude', sa.Float))

    op.execute(
        "UPDATE circles SET latitude = 49.2827, longitude = -123.1207 WHERE slug = 'vancouver'"
    )


def downgrade():
    op.drop_column('circles', 'longitude')
    op.drop_column('circles', 'latitude')
