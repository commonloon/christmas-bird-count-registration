# Updated by Claude AI on 2026-09-11
"""
Tests for circle-admin self-service editing of their own circle's config
(admin.edit_circle): access control (a circle-admin may only reach their own
circle, a super-admin any circle), field-level locking of
test_recipient/latitude/longitude (super-admin only, both in the rendered
form and enforced server-side against a crafted POST), and that every other
field remains genuinely editable by a circle-admin.
"""

import re

import pytest

from config.database import get_db_session
from models.circle import CircleModel
from tests.test_config import TEST_CIRCLE_SLUG

# A second real circle, used read-only here (GET/denied-POST only, never
# written) purely to prove a circle-admin can't reach a circle that isn't
# their own - same pattern/circle as tests/unit/test_email_content.py.
OTHER_CIRCLE_SLUG = 'nanaimo'

LOCKED_FIELDS = ['test_recipient', 'latitude', 'longitude']
EDIT_URL = f'/bigbird/circles/{TEST_CIRCLE_SLUG}/edit'


def _input_tag(html, field_name):
    """Extract the full <input ...> tag for a given name= attribute, so a
    test can check for the disabled attribute on that specific field only."""
    match = re.search(rf'<input[^>]*name="{field_name}"[^>]*>', html)
    assert match, f'no <input name="{field_name}"> tag found in response'
    return match.group(0)


def _full_form(overrides=None):
    """A complete, valid admin.edit_circle form submission - every field the
    template renders, including deliberately attempted changes to the three
    locked fields (test_recipient/latitude/longitude), so tests can confirm
    those attempted changes are accepted or ignored depending on role."""
    form = {
        'circle_name': 'Test Circle Updated',
        'name': 'Nature Vancouver',
        'website': 'https://naturevancouver.ca',
        'contact': 'birdcount@naturevancouver.ca',
        'count_contact': 'birdcount@naturevancouver.ca',
        'count_event_name': 'Test Circle used for automated testing of the website code',
        'count_info_url': 'https://naturevancouver.ca',
        'from_email': 'birdcount@naturevancouver.ca',
        'test_recipient': 'attempted-change@naturevancouver.ca',
        'display_timezone': 'America/Vancouver',
        'registration_opens_months': '4',
        'registration_closes_days': '1',
        'count_date': '2026-12-25',
        'latitude': '99.9',
        'longitude': '88.8',
        'count_experience_label': 'CBC Experience',
        'feeder_counter_label': 'Count birds at my home feeder',
        'notes_placeholder_example': '',
        'is_cbc': 'on',
    }
    if overrides:
        form.update(overrides)
    return form


@pytest.fixture
def restore_test_circle():
    """Snapshots the shared 'test' circle's config row before the test and
    restores every field afterward, so these tests can freely POST real
    changes to admin.edit_circle without permanently mutating data the rest
    of the suite relies on."""
    model = CircleModel(get_db_session())
    original = model.get_by_slug(TEST_CIRCLE_SLUG)
    yield original
    model.update(TEST_CIRCLE_SLUG, original)


# --- Access control -------------------------------------------------------

class TestEditCircleAccessControl:
    def test_anonymous_redirected_to_login(self, client):
        resp = client.get(EDIT_URL)
        assert resp.status_code == 302

    def test_circle_admin_can_access_own_circle(self, admin_client):
        resp = admin_client.get(EDIT_URL)
        assert resp.status_code == 200

    def test_circle_admin_cannot_access_other_circle(self, admin_client):
        """admin_client is a circle-admin whose g.circle_slug resolves to
        TEST_CIRCLE_SLUG (via the test.cbc.test Host header) - it must not be
        able to manage a different real circle just by changing the URL."""
        resp = admin_client.get(f'/bigbird/circles/{OTHER_CIRCLE_SLUG}/edit')
        assert resp.status_code == 302

    def test_super_admin_can_access_any_circle(self, super_admin_client):
        resp = super_admin_client.get(f'/bigbird/circles/{OTHER_CIRCLE_SLUG}/edit')
        assert resp.status_code == 200


# --- Field-level locking, as rendered in the form -------------------------

class TestEditCircleFieldLockingUI:
    def test_circle_admin_sees_locked_fields_disabled(self, admin_client):
        resp = admin_client.get(EDIT_URL)
        html = resp.get_data(as_text=True)
        for field in LOCKED_FIELDS:
            assert 'disabled' in _input_tag(html, field), f'{field} should be disabled for a circle-admin'
        assert html.count('Super-admin only') == len(LOCKED_FIELDS)

    def test_super_admin_sees_locked_fields_editable(self, super_admin_client):
        resp = super_admin_client.get(EDIT_URL)
        html = resp.get_data(as_text=True)
        for field in LOCKED_FIELDS:
            assert 'disabled' not in _input_tag(html, field), f'{field} should be editable for a super-admin'
        assert 'Super-admin only' not in html

    def test_circle_admin_other_fields_remain_editable(self, admin_client):
        resp = admin_client.get(EDIT_URL)
        html = resp.get_data(as_text=True)
        for field in ['circle_name', 'name', 'website', 'contact', 'count_contact',
                      'count_event_name', 'count_info_url', 'from_email',
                      'display_timezone', 'registration_opens_months',
                      'registration_closes_days', 'count_experience_label',
                      'feeder_counter_label', 'notes_placeholder_example']:
            assert 'disabled' not in _input_tag(html, field)


# --- Field-level locking, enforced server-side ----------------------------

class TestEditCircleFieldUpdatePermissions:
    def test_circle_admin_update_changes_allowed_fields(self, admin_client, restore_test_circle):
        form = _full_form({'circle_name': 'Circle Admin Edited', 'website': 'https://example.org/updated'})
        resp = admin_client.post(EDIT_URL, data=form)
        assert resp.status_code == 302

        updated = CircleModel(get_db_session()).get_by_slug(TEST_CIRCLE_SLUG)
        assert updated['circle_name'] == 'Circle Admin Edited'
        assert updated['website'] == 'https://example.org/updated'

    def test_circle_admin_cannot_change_locked_fields_even_if_submitted(self, admin_client, restore_test_circle):
        """A circle-admin's browser never submits these fields (disabled
        inputs), but the server must reject a crafted POST that includes
        them anyway - not just rely on the UI."""
        original = restore_test_circle
        resp = admin_client.post(EDIT_URL, data=_full_form())
        assert resp.status_code == 302

        updated = CircleModel(get_db_session()).get_by_slug(TEST_CIRCLE_SLUG)
        assert updated['test_recipient'] == original['test_recipient']
        assert updated['latitude'] == original['latitude']
        assert updated['longitude'] == original['longitude']

    def test_super_admin_can_change_locked_fields(self, super_admin_client, restore_test_circle):
        form = _full_form({
            'test_recipient': 'super-admin-changed@naturevancouver.ca',
            'latitude': '10.5',
            'longitude': '-20.5',
        })
        resp = super_admin_client.post(EDIT_URL, data=form)
        assert resp.status_code == 302

        updated = CircleModel(get_db_session()).get_by_slug(TEST_CIRCLE_SLUG)
        assert updated['test_recipient'] == 'super-admin-changed@naturevancouver.ca'
        assert updated['latitude'] == 10.5
        assert updated['longitude'] == -20.5

    def test_circle_admin_cannot_change_other_circle_by_posting_directly(self, admin_client, restore_test_circle):
        """Belt-and-suspenders: even a POST (not just a GET) to a different
        real circle's edit URL must be denied before any field is touched."""
        resp = admin_client.post(f'/bigbird/circles/{OTHER_CIRCLE_SLUG}/edit', data=_full_form())
        assert resp.status_code == 302
