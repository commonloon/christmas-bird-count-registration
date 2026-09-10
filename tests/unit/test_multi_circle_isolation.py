# Updated by Claude AI on 2026-09-09
"""
Tests that circle_slug scoping actually isolates data between circles, not
just that the one circle under test (TEST_CIRCLE_SLUG) happens to work.
Every existing test before this file would still pass even if circle_slug
scoping were silently broken, as long as it didn't affect TEST_CIRCLE_SLUG -
these tests specifically populate TWO circles and check neither leaks into
the other. See PROMPT.md's "Plan: Multi-Circle Test Coverage" item 3.

Uses tests/conftest.py's second_test_circle fixture (TEST_CIRCLE_SLUG_2 =
'test2', deliberately distinct field values from both TEST_CIRCLE_SLUG and
Vancouver's module constants).
"""

from datetime import datetime

import pytest

# Must import app (not routes.auth) first - routes.auth does `from app import
# csrf, circle_host` at module level, and if routes.auth is the first thing
# to trigger app.py's import chain (rather than app.py itself), app.py ends
# up registered in sys.modules under a second, separate identity mid-import,
# which then races routes.admin's own still-in-progress `from routes.auth
# import require_admin` and fails with a circular-import ImportError. See
# PROMPT.md's "Hard-won operational facts" for the same gotcha elsewhere.
import app  # noqa: F401

from config.database import get_db_session
from models.circle import CircleAdminModel, CircleAreaModel
from models.db import CircleArea, Participant
from models.participant import ParticipantModel
from routes.auth import get_user_role
from tests.test_config import TEST_CIRCLE_SLUG, TEST_CIRCLE_SLUG_2

CURRENT_YEAR = datetime.now().year

FAKE_GEOJSON = {
    'type': 'Polygon',
    'coordinates': [[[-123.10, 49.20], [-123.10, 49.30], [-123.00, 49.30], [-123.00, 49.20], [-123.10, 49.20]]],
}


# app/client fixtures come from tests/unit/conftest.py (shared, rate-limiting
# disabled there for the whole tests/unit/ tier).


@pytest.fixture
def db_session():
    return get_db_session()


@pytest.fixture
def two_circles_with_participants(second_test_circle, db_session):
    """One distinctly-named/emailed participant in each of TEST_CIRCLE_SLUG
    and TEST_CIRCLE_SLUG_2, same year - the minimal data needed to prove
    cross-circle isolation, not the full CSV fixture. second_test_circle's
    own teardown wipes everything scoped to TEST_CIRCLE_SLUG_2 (including
    this participant); only the TEST_CIRCLE_SLUG side needs cleaning here."""
    model_1 = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
    model_2 = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG_2)

    pid_1 = model_1.add_participant({
        'first_name': 'IsolationOne', 'last_name': 'Participant',
        'email': 'isolation-one@example.com', 'preferred_area': 'UNASSIGNED',
        'skill_level': 'Intermediate', 'experience': '1-2 counts', 'participation_type': 'regular',
    })
    pid_2 = model_2.add_participant({
        'first_name': 'IsolationTwo', 'last_name': 'Participant',
        'email': 'isolation-two@example.com', 'preferred_area': 'UNASSIGNED',
        'skill_level': 'Intermediate', 'experience': '1-2 counts', 'participation_type': 'regular',
    })

    yield pid_1, pid_2

    db_session.query(Participant).filter_by(id=pid_1).delete()
    db_session.commit()


class TestParticipantModelIsolation:
    """The core data-integrity property the whole multi-circle migration
    depends on: a ParticipantModel query scoped to one circle never returns
    another circle's rows, even for the same year."""

    def test_test_circle_query_never_returns_test2_participant(self, two_circles_with_participants, db_session):
        pid_1, pid_2 = two_circles_with_participants
        model_1 = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
        ids = {p['id'] for p in model_1.get_all_participants()}
        assert pid_1 in ids
        assert pid_2 not in ids

    def test_test2_circle_query_never_returns_test_participant(self, two_circles_with_participants, db_session):
        pid_1, pid_2 = two_circles_with_participants
        model_2 = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG_2)
        ids = {p['id'] for p in model_2.get_all_participants()}
        assert pid_2 in ids
        assert pid_1 not in ids


def _admin_client_for_host(client, host):
    """A session logged in as the global super-admin, scoped to `host` -
    works for either circle without needing a per-circle circle_admins row."""
    with client.session_transaction(headers={'Host': host}) as sess:
        sess['user_email'] = 'cbc-test-admin1@naturevancouver.ca'
        sess['user_name'] = 'Test Super Admin'
    return client


class TestCsvExportIsolation:
    """The real /bigbird/export_csv route (not just the model) - it builds
    ParticipantModel(g.db, selected_year) with no explicit circle_slug,
    relying entirely on g.circle_slug resolved from the request's Host
    header. An end-to-end check that this actually scopes correctly."""

    def test_csv_export_for_test_circle_excludes_test2_participant(self, client, two_circles_with_participants):
        c = _admin_client_for_host(client, 'test.cbc.test')
        resp = c.get(f'/bigbird/export_csv?year={CURRENT_YEAR}', headers={'Host': 'test.cbc.test'})
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        assert 'IsolationOne' in body
        assert 'IsolationTwo' not in body

    def test_csv_export_for_test2_circle_excludes_test_participant(self, client, two_circles_with_participants):
        c = _admin_client_for_host(client, 'test2.cbc.test')
        resp = c.get(f'/bigbird/export_csv?year={CURRENT_YEAR}', headers={'Host': 'test2.cbc.test'})
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        assert 'IsolationTwo' in body
        assert 'IsolationOne' not in body


class TestCircleAreaIsolation:
    """CircleAreaModel.get_boundary_data(slug) - both circles get an area
    using the exact SAME area code, to prove that doesn't collide/leak
    across circles (circle_areas is only unique on (circle_slug, code))."""

    def test_get_boundary_data_returns_only_that_circles_areas(self, second_test_circle, db_session):
        area_model = CircleAreaModel(db_session)
        area_model.upsert_from_kml(TEST_CIRCLE_SLUG, 'ISO9', 'Test Isolation Area One', 'desc', FAKE_GEOJSON)
        area_model.upsert_from_kml(TEST_CIRCLE_SLUG_2, 'ISO9', 'Test Isolation Area Two', 'desc', FAKE_GEOJSON)
        try:
            names_1 = {a['name'] for a in area_model.get_boundary_data(TEST_CIRCLE_SLUG)['areas']}
            names_2 = {a['name'] for a in area_model.get_boundary_data(TEST_CIRCLE_SLUG_2)['areas']}

            assert 'Test Isolation Area One' in names_1
            assert 'Test Isolation Area Two' not in names_1

            assert 'Test Isolation Area Two' in names_2
            assert 'Test Isolation Area One' not in names_2
        finally:
            db_session.query(CircleArea).filter_by(circle_slug=TEST_CIRCLE_SLUG, code='ISO9').delete()
            db_session.commit()
            # test2's ISO9 row is cleaned up by second_test_circle's own teardown.


class TestAdminRoleIsolation:
    """The sharpest test of the single-table circle_admins design actually
    scoping correctly rather than granting access to every circle."""

    def test_circle_admin_resolves_to_admin_only_for_their_own_circle(self, second_test_circle, db_session):
        admin_model = CircleAdminModel(db_session)
        email = 'isolation-circle-admin@example.com'
        admin_model.add_admin(email, TEST_CIRCLE_SLUG)
        try:
            assert get_user_role(email, db_session, TEST_CIRCLE_SLUG) == 'admin'
            assert get_user_role(email, db_session, TEST_CIRCLE_SLUG_2) != 'admin'
            assert get_user_role(email, db_session, TEST_CIRCLE_SLUG_2) == 'public'
        finally:
            admin_model.remove_admin(email, TEST_CIRCLE_SLUG)

    def test_super_admin_resolves_to_super_admin_under_both_circles(self, second_test_circle, db_session):
        email = 'cbc-test-admin1@naturevancouver.ca'
        assert get_user_role(email, db_session, TEST_CIRCLE_SLUG) == 'super_admin'
        assert get_user_role(email, db_session, TEST_CIRCLE_SLUG_2) == 'super_admin'
