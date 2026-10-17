"""circles.is_external / external_url; circles.name nullable

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-16

An "external" circle is a count whose registration is managed outside this
app (e.g. Birds Canada's CBC registration system). It is listed on the
landing-page maps like any other circle, but its map/table links go to
external_url instead of the circle's own subdomain, and its subdomain
redirects to the matching landing page / external_url rather than serving a
registration site. external_url may be NULL (an external count with only a
name, location, and contact - listed without links), and may be an info page
rather than a registration page, hence the name.

circles.name is the managing ORGANIZATION (circle_name is the count itself and
stays NOT NULL). It becomes nullable because an externally-managed count may
be run by an individual rather than an organization; the app still requires
it for non-external circles.

Existing rows: is_external defaults false, external_url stays NULL, name is
untouched - no circle changes behaviour until a super-admin sets the flag.
"""
from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('circles', sa.Column(
        'is_external', sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column('circles', sa.Column('external_url', sa.String(500), nullable=True))
    op.alter_column('circles', 'name', existing_type=sa.String(200), nullable=True)


def downgrade():
    # Rows with no managing organization can't satisfy NOT NULL; use an empty
    # string rather than failing or inventing an organization name.
    op.execute("UPDATE circles SET name = '' WHERE name IS NULL")
    op.alter_column('circles', 'name', existing_type=sa.String(200), nullable=False)
    op.drop_column('circles', 'external_url')
    op.drop_column('circles', 'is_external')
