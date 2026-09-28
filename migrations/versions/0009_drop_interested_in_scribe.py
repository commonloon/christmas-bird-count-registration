"""participants: drop interested_in_scribe

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-07

The "Scribe" role (eBird data-entry helper) was an experimental checkbox
piloted for one season. The organizer decided it didn't work out and asked
for it to be removed entirely - including historical answers, which nobody
needs preserved (confirmed explicitly, unlike every other field on this
table). Every application-layer reference (registration form, admin/leader
displays, CSV export, digest/confirmation emails) was removed in the same
change as this migration.
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('participants', 'interested_in_scribe')


def downgrade():
    op.add_column('participants', sa.Column('interested_in_scribe', sa.Boolean, server_default=sa.false()))
