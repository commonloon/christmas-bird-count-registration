"""circle_areas.boundary_geojson - KML-imported area polygons

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-31

Backfills Vancouver's existing boundaries from the static
static/data/area_boundaries_vancouver.json file that the app used to read
at request time (see app.py/routes/api.py, updated in this same change to
read from this column instead) - without this backfill, deploying this
migration would blank out the live Vancouver map until someone re-ran the
KML import by hand.
"""
import json
import os

from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def _vancouver_boundaries_path():
    # migrations/versions/0006_*.py -> repo root -> static/data/...
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(repo_root, 'static', 'data', 'area_boundaries_vancouver.json')


def upgrade():
    op.add_column('circle_areas', sa.Column('boundary_geojson', sa.JSON))

    path = _vancouver_boundaries_path()
    if not os.path.exists(path):
        # Nothing to backfill (e.g. a fresh dev DB with no seed file present) -
        # areas simply start with no boundary until someone imports a KML file.
        return

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    connection = op.get_bind()
    circle_areas = sa.table(
        'circle_areas',
        sa.column('circle_slug', sa.String),
        sa.column('code', sa.String),
        sa.column('boundary_geojson', sa.JSON),
    )
    for area in data.get('areas', []):
        connection.execute(
            circle_areas.update()
            .where(circle_areas.c.circle_slug == 'vancouver')
            .where(circle_areas.c.code == area['letter_code'])
            .values(boundary_geojson=area['geometry'])
        )


def downgrade():
    op.drop_column('circle_areas', 'boundary_geojson')
