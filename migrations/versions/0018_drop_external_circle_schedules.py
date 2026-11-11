"""Delete email schedule rows belonging to external circles

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-11

An external circle (circles.is_external) has its registration managed
elsewhere and sends no email from this app, but circles created before this
change were given the default email schedule rows. The scheduler now ignores
external circles; this removes the dead rows. CircleModel.update() recreates
the defaults if a circle is later switched back to a normal one. The run log
(email_schedule_run_log) is left untouched.
"""
from alembic import op

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "DELETE FROM circle_email_schedules "
        "WHERE circle_slug IN (SELECT slug FROM circles WHERE is_external)")


def downgrade():
    # The deleted rows were unused defaults; nothing to restore.
    pass
