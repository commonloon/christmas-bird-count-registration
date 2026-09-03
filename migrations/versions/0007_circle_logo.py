"""circles.logo_data / logo_content_type - DB-backed per-circle logo upload

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-03

Replaces logo_path (a free-text server file path - removed from the circle-admin
form in an earlier session as unsound UX/security) with the logo bytes themselves,
stored in Postgres rather than the app node's filesystem - same reasoning as
0006's move of area boundaries into the DB (admin-uploaded content shouldn't
depend on filesystem persistence on this hosting platform; the app node's disk
has already been wiped once this migration by a full environment recreation,
while Postgres lives on a separate node and wasn't affected).

Backfills only Vancouver's logo (static/icons/NV_logo.png, the one circle whose
logo is already live in production today) so the switchover doesn't blank it.
Nanaimo/Ladner/Comox-spring's real logos exist as static files elsewhere
(the `nanaimo` branch, and the separate ../ladner-cbc / ../comox-spring repos)
but are deliberately NOT backfilled here - each will be uploaded through the new
admin UI instead.
"""
import os

from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def _vancouver_logo_path():
    # migrations/versions/0007_*.py -> repo root -> static/icons/...
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(repo_root, 'static', 'icons', 'NV_logo.png')


def upgrade():
    op.add_column('circles', sa.Column('logo_data', sa.LargeBinary))
    op.add_column('circles', sa.Column('logo_content_type', sa.String(100)))

    path = _vancouver_logo_path()
    if os.path.exists(path):
        with open(path, 'rb') as f:
            logo_bytes = f.read()

        connection = op.get_bind()
        circles = sa.table(
            'circles',
            sa.column('slug', sa.String),
            sa.column('logo_data', sa.LargeBinary),
            sa.column('logo_content_type', sa.String),
        )
        connection.execute(
            circles.update()
            .where(circles.c.slug == 'vancouver')
            .values(logo_data=logo_bytes, logo_content_type='image/png')
        )
    # else: nothing to backfill (e.g. a fresh dev DB without this static asset) -
    # Vancouver's row simply starts with no logo until one is uploaded.

    op.drop_column('circles', 'logo_path')


def downgrade():
    op.add_column('circles', sa.Column('logo_path', sa.String(500)))
    op.drop_column('circles', 'logo_content_type')
    op.drop_column('circles', 'logo_data')
