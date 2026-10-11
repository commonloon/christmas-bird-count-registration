# Updated by Claude AI on 2026-10-05
"""
Tests for splitting Vancouver's area W into W (south) and WW (north): the
repo KML (utils/Vancouver_CBC_Areas.kml), migration 0013, and that area code
WW is accepted by validation once the area exists.
"""

import importlib.util
import os

import pytest
from shapely.geometry import Polygon

from app import push_circle_context
from config.database import get_db_session
from models.db import CircleArea
from services.kml_import import parse_kml_string
from services.security import validate_area_code
from tests.test_config import TEST_CIRCLE_SLUG

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KML_PATH = os.path.join(REPO_ROOT, 'utils', 'Vancouver_CBC_Areas.kml')
MIGRATION_PATH = os.path.join(REPO_ROOT, 'migrations', 'versions', '0013_split_vancouver_area_ww.py')

# W and WW should share only an edge; a split with slivers or real overlap
# would exceed this fraction of W's area.
MAX_OVERLAP_FRACTION = 0.001


@pytest.fixture(scope='module')
def kml_areas():
    with open(KML_PATH, encoding='utf-8') as f:
        return {a['letter_code']: a for a in parse_kml_string(f.read())}


@pytest.fixture(scope='module')
def migration():
    spec = importlib.util.spec_from_file_location('migration_0013', MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _polygon(area):
    return Polygon(area['geometry']['coordinates'][0])


class TestKmlSplit:
    def test_w_and_ww_both_present(self, kml_areas):
        assert 'W' in kml_areas and 'WW' in kml_areas

    def test_polygons_are_valid(self, kml_areas):
        assert _polygon(kml_areas['W']).is_valid
        assert _polygon(kml_areas['WW']).is_valid

    def test_w_and_ww_share_an_edge_without_overlapping(self, kml_areas):
        w, ww = _polygon(kml_areas['W']), _polygon(kml_areas['WW'])
        assert w.intersection(ww).area / w.area < MAX_OVERLAP_FRACTION
        assert w.buffer(1e-4).intersects(ww)

    def test_ww_is_north_of_w(self, kml_areas):
        assert _polygon(kml_areas['WW']).centroid.y > _polygon(kml_areas['W']).centroid.y

    def test_descriptions_present(self, kml_areas):
        assert kml_areas['W']['description']
        assert kml_areas['WW']['description']


class TestMigrationData:
    def test_embedded_geometry_matches_kml(self, kml_areas, migration):
        """The migration embeds its own copy of the geometry; it must not drift
        from the repo KML (regenerate the migration data if the boundary moves
        before deploy)."""
        assert migration.NEW_W_GEOMETRY == kml_areas['W']['geometry']
        assert migration.NEW_WW_GEOMETRY == kml_areas['WW']['geometry']
        assert migration.NEW_W_DESCRIPTION == kml_areas['W']['description']
        assert migration.NEW_WW_DESCRIPTION == kml_areas['WW']['description']

    def test_revision_chain(self, migration):
        assert migration.revision == '0013'
        assert migration.down_revision == '0012'


@pytest.fixture
def rolled_back_session(db_session):
    """Run inside a SAVEPOINT that is always rolled back, so the migration helpers
    can be exercised against the 'test' circle without leaving any trace."""
    nested = db_session.begin_nested()
    yield db_session
    # Popping a request context (TestWwValidation) rolls the shared session
    # back itself, which closes the savepoint - nothing left to undo then.
    if nested.is_active:
        nested.rollback()
    db_session.rollback()


def _row(db, code):
    return db.query(CircleArea).filter_by(circle_slug=TEST_CIRCLE_SLUG, code=code).first()


def _ensure_w(db):
    """Make sure the test circle has an old-style area W and no WW."""
    db.query(CircleArea).filter_by(circle_slug=TEST_CIRCLE_SLUG, code='WW').delete()
    w = _row(db, 'W')
    if w is None:
        w = CircleArea(circle_slug=TEST_CIRCLE_SLUG, code='W', name='Test W', difficulty='Easy', terrain='Park')
        db.add(w)
    w.description = 'old'
    w.boundary_geojson = {'type': 'Polygon', 'coordinates': [[[0, 0], [0, 1], [1, 1], [0, 0]]]}
    db.flush()
    return w


def _others(db):
    return {r.code: (r.name, r.description, r.boundary_geojson)
            for r in db.query(CircleArea).filter_by(circle_slug=TEST_CIRCLE_SLUG)
            if r.code not in ('W', 'WW')}


class TestMigrationApplies:
    def test_split_updates_w_and_creates_ww(self, rolled_back_session, migration):
        db = rolled_back_session
        w = _ensure_w(db)
        name, difficulty, terrain = w.name, w.difficulty, w.terrain

        migration.split_w(db.connection(), slug=TEST_CIRCLE_SLUG)
        db.expire_all()

        w, ww = _row(db, 'W'), _row(db, 'WW')
        assert w.boundary_geojson == migration.NEW_W_GEOMETRY
        assert w.description == migration.NEW_W_DESCRIPTION
        assert (w.name, w.difficulty, w.terrain) == (name, difficulty, terrain)
        assert ww.boundary_geojson == migration.NEW_WW_GEOMETRY
        assert ww.name == migration.NEW_WW_NAME
        assert ww.description == migration.NEW_WW_DESCRIPTION
        assert (ww.difficulty, ww.terrain) == (difficulty, terrain)

    def test_split_leaves_other_areas_alone(self, rolled_back_session, migration):
        db = rolled_back_session
        _ensure_w(db)
        before = _others(db)
        migration.split_w(db.connection(), slug=TEST_CIRCLE_SLUG)
        db.expire_all()
        assert _others(db) == before

    def test_split_refuses_when_ww_exists(self, rolled_back_session, migration):
        db = rolled_back_session
        _ensure_w(db)
        db.add(CircleArea(circle_slug=TEST_CIRCLE_SLUG, code='WW', name='x'))
        db.flush()
        with pytest.raises(RuntimeError):
            migration.split_w(db.connection(), slug=TEST_CIRCLE_SLUG)

    def test_split_refuses_without_w(self, rolled_back_session, migration):
        db = rolled_back_session
        db.query(CircleArea).filter_by(circle_slug=TEST_CIRCLE_SLUG, code='W').delete()
        db.query(CircleArea).filter_by(circle_slug=TEST_CIRCLE_SLUG, code='WW').delete()
        db.flush()
        with pytest.raises(RuntimeError):
            migration.split_w(db.connection(), slug=TEST_CIRCLE_SLUG)

    def test_downgrade_restores_w_and_removes_ww(self, rolled_back_session, migration):
        db = rolled_back_session
        _ensure_w(db)
        migration.split_w(db.connection(), slug=TEST_CIRCLE_SLUG)
        migration.merge_ww_into_w(db.connection(), slug=TEST_CIRCLE_SLUG)
        db.expire_all()
        assert _row(db, 'WW') is None
        assert _row(db, 'W').boundary_geojson == migration.OLD_W_GEOMETRY
        assert _row(db, 'W').description == migration.OLD_W_DESCRIPTION


class TestWwValidation:
    def test_ww_valid_only_once_the_area_exists(self, migration):
        """validate_area_code() reads the request circle's DB-backed areas, so
        WW is accepted after the migration and not before. Uses the same
        get_db_session() session the validator reads through (the shared
        db_session fixture can be a different session by the time other test
        files have run), and rolls everything back at the end."""
        ctx = push_circle_context(TEST_CIRCLE_SLUG)
        db = get_db_session()
        try:
            _ensure_w(db)
            assert validate_area_code('WW') is False
            migration.split_w(db.connection(), slug=TEST_CIRCLE_SLUG)
            db.flush()
            assert validate_area_code('WW') is True
        finally:
            db.rollback()
            ctx.pop()
