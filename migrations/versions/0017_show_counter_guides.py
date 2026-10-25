"""circles.show_counter_guides: show the Birds Canada counter guide buttons on registration

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-25

When true (the default, so no existing circle changes behaviour) the registration
page shows the Birds Canada "Guide for Field/Feeder Counters" buttons. When false it
shows a sentence linking to the circle's own count information page instead.
"""
from alembic import op
import sqlalchemy as sa

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('circles', sa.Column(
        'show_counter_guides', sa.Boolean, nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column('circles', 'show_counter_guides')
