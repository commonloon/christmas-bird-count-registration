"""circles.map_medium_from / map_high_from: per-circle map colour thresholds

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-20

The participant-count tiers that colour the area maps: counts below map_medium_from
are 'low', from map_medium_from up to map_high_from - 1 are 'medium', and
map_high_from and above are 'high'. Both NULL means the application defaults
(4 and 8) - see services/count_thresholds.py. Existing rows are left NULL, so no
circle changes behaviour until a circle admin sets values.
"""
from alembic import op
import sqlalchemy as sa

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('circles', sa.Column('map_medium_from', sa.Integer, nullable=True))
    op.add_column('circles', sa.Column('map_high_from', sa.Integer, nullable=True))


def downgrade():
    op.drop_column('circles', 'map_high_from')
    op.drop_column('circles', 'map_medium_from')
