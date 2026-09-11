"""circles.major_area_boundaries - decorative KML-imported boundary lines

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-11

A circle can optionally store a set of decorative "major area group"
boundary lines (hand-drawn LineString placemarks in the KML, no relation to
any specific area code) drawn as a visual orientation overlay on the map -
see services/kml_import.py's parse_kml_boundary_lines() and
static/js/map.js's displayBoundaries(). A single JSON column, not a
dedicated table: these lines have no individual identity worth a row each,
and are always replaced wholesale on KML import, never edited one at a
time - the same "whole-blob" shape as circles.yearly_count_dates. Starts
NULL for every existing circle; nothing renders differently until a KML
containing such lines is (re-)imported.
"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('circles', sa.Column('major_area_boundaries', sa.JSON, nullable=True))


def downgrade():
    op.drop_column('circles', 'major_area_boundaries')
