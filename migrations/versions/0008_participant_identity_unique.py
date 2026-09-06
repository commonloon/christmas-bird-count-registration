"""participants: unique (circle_slug, year, first_name, last_name, email)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-05

CLAUDE.md has always documented (first_name, last_name, email) as the mandatory
identity-matching tuple, but nothing before this migration enforced it at the
database level - the Firestore-era app (and this app until now) only ever did
an application-level check-then-write (ParticipantModel.email_name_exists)
before inserting, which is exposed to a race between two near-simultaneous
submissions with the same identity. Scoped by circle_slug/year, since the same
person registers fresh each year and circles don't share participants.

Confirmed no existing violations before writing this migration (checked both
local dev and production): a duplicate would make this upgrade fail outright.
"""
from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        'uq_participants_identity', 'participants',
        ['circle_slug', 'year', 'first_name', 'last_name', 'email'],
    )


def downgrade():
    op.drop_constraint('uq_participants_identity', 'participants', type_='unique')
