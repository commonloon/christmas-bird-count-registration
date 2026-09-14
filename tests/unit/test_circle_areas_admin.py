# Updated by Claude AI on 2026-09-14
"""
Tests for the circle areas admin page (admin.circle_areas_manage) and its
inline-edit AJAX endpoint (admin.circle_areas_edit), which replaced the old
"Add or update an area's labels" form. Covers: access control (mirrors
test_circle_admin_permissions.py's pattern - a circle-admin may only reach
their own circle, a super-admin any circle), that the manual add-area form is
genuinely gone, and that circle_areas_edit updates only the four label fields
(name/description/difficulty/terrain) for an existing area's code - never
creates a new area, never changes a code, and rejects suspicious/missing
input.
"""

import pytest

from config.database import get_db_session
from models.circle import CircleAreaModel
from models.db import CircleArea
from tests.test_config import TEST_CIRCLE_SLUG

OTHER_CIRCLE_SLUG = 'nanaimo'
AREAS_URL = f'/bigbird/circles/{TEST_CIRCLE_SLUG}/areas'
EDIT_URL = f'/bigbird/circles/{TEST_CIRCLE_SLUG}/areas/edit'
TEST_AREA_CODE = 'ZZTEST'


@pytest.fixture
def db_session():
    return get_db_session()


@pytest.fixture
def test_area(db_session):
    """A fresh, throwaway area on the 'test' circle - not one of the real
    seeded areas, so editing/failing to edit it can't affect other tests."""
    row = CircleArea(
        circle_slug=TEST_CIRCLE_SLUG, code=TEST_AREA_CODE, name='Original Name',
        description='Original description', difficulty='Easy', terrain='Flat',
    )
    db_session.add(row)
    db_session.commit()
    yield TEST_AREA_CODE
    db_session.query(CircleArea).filter_by(circle_slug=TEST_CIRCLE_SLUG, code=TEST_AREA_CODE).delete()
    db_session.commit()


def _payload(code, **overrides):
    payload = {'code': code, 'name': 'Updated Name', 'description': 'Updated description',
               'difficulty': 'Hard', 'terrain': 'Hilly'}
    payload.update(overrides)
    return payload


# --- Page access control ---------------------------------------------------

class TestCircleAreasPageAccessControl:
    def test_anonymous_redirected_to_login(self, client):
        resp = client.get(AREAS_URL)
        assert resp.status_code == 302

    def test_circle_admin_can_access_own_circle(self, admin_client):
        resp = admin_client.get(AREAS_URL)
        assert resp.status_code == 200

    def test_circle_admin_cannot_access_other_circle(self, admin_client):
        resp = admin_client.get(f'/bigbird/circles/{OTHER_CIRCLE_SLUG}/areas')
        assert resp.status_code == 302

    def test_super_admin_can_access_any_circle(self, super_admin_client):
        resp = super_admin_client.get(f'/bigbird/circles/{OTHER_CIRCLE_SLUG}/areas')
        assert resp.status_code == 200


# --- The old manual add/update form is gone, replaced by inline edit -------

class TestCircleAreasPageContent:
    def test_manual_add_form_is_gone(self, super_admin_client, test_area):
        resp = super_admin_client.get(AREAS_URL)
        html = resp.get_data(as_text=True)
        assert "Add or update an area's labels" not in html
        assert 'Save Area' not in html

    def test_area_row_has_edit_affordance(self, super_admin_client, test_area):
        resp = super_admin_client.get(AREAS_URL)
        html = resp.get_data(as_text=True)
        assert 'btn-edit' in html
        assert f'data-code="{TEST_AREA_CODE}"' in html

    def test_kml_import_form_still_present(self, super_admin_client, test_area):
        """Boundary/new-area creation still only happens via KML import."""
        resp = super_admin_client.get(AREAS_URL)
        html = resp.get_data(as_text=True)
        assert 'Import KML' in html


# --- circle_areas_edit access control (JSON) --------------------------------

class TestCircleAreasEditAccessControl:
    def test_anonymous_gets_401_json(self, client, test_area):
        resp = client.post(EDIT_URL, json=_payload(TEST_AREA_CODE))
        assert resp.status_code == 401
        assert resp.get_json()['success'] is False

    def test_circle_admin_can_edit_own_circle(self, admin_client, test_area):
        resp = admin_client.post(EDIT_URL, json=_payload(TEST_AREA_CODE))
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_circle_admin_cannot_edit_other_circle(self, admin_client, test_area):
        resp = admin_client.post(f'/bigbird/circles/{OTHER_CIRCLE_SLUG}/areas/edit', json=_payload(TEST_AREA_CODE))
        assert resp.status_code == 403
        assert resp.get_json()['success'] is False

        # Belt-and-suspenders: this circle's own area is untouched by the denied attempt.
        area = CircleAreaModel(get_db_session()).get_area(TEST_CIRCLE_SLUG, TEST_AREA_CODE)
        assert area['name'] == 'Original Name'

    def test_super_admin_can_edit_any_circle(self, super_admin_client, test_area):
        resp = super_admin_client.post(EDIT_URL, json=_payload(TEST_AREA_CODE))
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True


# --- circle_areas_edit functional correctness -------------------------------

class TestCircleAreasEditBehaviour:
    def test_updates_all_four_label_fields(self, super_admin_client, test_area):
        resp = super_admin_client.post(EDIT_URL, json=_payload(TEST_AREA_CODE))
        assert resp.status_code == 200

        area = CircleAreaModel(get_db_session()).get_area(TEST_CIRCLE_SLUG, TEST_AREA_CODE)
        assert area['name'] == 'Updated Name'
        assert area['description'] == 'Updated description'
        assert area['difficulty'] == 'Hard'
        assert area['terrain'] == 'Hilly'

    def test_code_is_never_changed(self, super_admin_client, test_area):
        """The endpoint has no "new code" field at all - a code is used only
        to look up which row to update, never to rename it."""
        resp = super_admin_client.post(EDIT_URL, json=_payload(TEST_AREA_CODE, new_code='DIFFERENT'))
        assert resp.status_code == 200

        area = CircleAreaModel(get_db_session()).get_area(TEST_CIRCLE_SLUG, TEST_AREA_CODE)
        assert area is not None
        assert CircleAreaModel(get_db_session()).get_area(TEST_CIRCLE_SLUG, 'DIFFERENT') is None

    def test_optional_fields_can_be_cleared(self, super_admin_client, test_area):
        resp = super_admin_client.post(EDIT_URL, json=_payload(TEST_AREA_CODE, description='', difficulty='', terrain=''))
        assert resp.status_code == 200

        area = CircleAreaModel(get_db_session()).get_area(TEST_CIRCLE_SLUG, TEST_AREA_CODE)
        assert area['description'] == ''
        assert area['difficulty'] == ''
        assert area['terrain'] == ''

    def test_missing_name_is_rejected(self, super_admin_client, test_area):
        resp = super_admin_client.post(EDIT_URL, json=_payload(TEST_AREA_CODE, name=''))
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

        area = CircleAreaModel(get_db_session()).get_area(TEST_CIRCLE_SLUG, TEST_AREA_CODE)
        assert area['name'] == 'Original Name'

    def test_nonexistent_code_is_rejected(self, super_admin_client):
        resp = super_admin_client.post(EDIT_URL, json=_payload('NOSUCHAREA'))
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False

    def test_no_new_area_is_created(self, super_admin_client):
        """circle_areas_edit only ever updates an existing row - it must never
        silently create one for a code that doesn't exist yet."""
        super_admin_client.post(EDIT_URL, json=_payload('NOSUCHAREA'))
        assert CircleAreaModel(get_db_session()).get_area(TEST_CIRCLE_SLUG, 'NOSUCHAREA') is None

    def test_suspicious_input_is_rejected(self, super_admin_client, test_area):
        resp = super_admin_client.post(EDIT_URL, json=_payload(TEST_AREA_CODE, name='<script>alert(1)</script>'))
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

        area = CircleAreaModel(get_db_session()).get_area(TEST_CIRCLE_SLUG, TEST_AREA_CODE)
        assert area['name'] == 'Original Name'
