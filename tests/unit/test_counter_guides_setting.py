# Updated by Claude AI on 2026-10-25
"""
circles.show_counter_guides (migration 0017): when on (the default) the registration
page shows the Birds Canada counter guide buttons; when off it shows a sentence linking
to the circle's count information page, or nothing if no URL is set. Circle admins
control it from the circle edit form.
"""

import pytest

from config.database import get_db_session
from models.circle import CircleModel
from tests.test_config import TEST_CIRCLE_SLUG

INFO_URL = 'https://example.org/our-count-info'
GUIDE_MARKER = 'Guide for Field Counters'
EDIT_URL = f'/bigbird/circles/{TEST_CIRCLE_SLUG}/edit'


def _update(**fields):
    db = get_db_session()
    db.rollback()
    CircleModel(db).update(TEST_CIRCLE_SLUG, fields)


@pytest.fixture
def restore_circle():
    db = get_db_session()
    original = CircleModel(db).get_by_slug(TEST_CIRCLE_SLUG)
    keep = {k: original[k] for k in ('show_counter_guides', 'count_info_url', 'is_cbc')}
    yield
    _update(**keep)


def _registration_html(client):
    return client.get('/').get_data(as_text=True)


def test_guides_shown_when_on(client, restore_circle):
    _update(show_counter_guides=True, count_info_url=INFO_URL, is_cbc=True)
    html = _registration_html(client)
    assert GUIDE_MARKER in html and 'Guide for Feeder Counters' in html
    assert 'for more information about the count' not in html


def test_off_with_url_links_to_count_info_page(client, restore_circle):
    _update(show_counter_guides=False, count_info_url=INFO_URL, is_cbc=True)
    html = _registration_html(client)
    assert GUIDE_MARKER not in html and 'Guide for Feeder Counters' not in html
    assert f'href="{INFO_URL}"' in html
    assert 'page for more information about the count.' in html


def test_off_without_url_shows_nothing(client, restore_circle):
    _update(show_counter_guides=False, count_info_url='', is_cbc=True)
    html = _registration_html(client)
    assert GUIDE_MARKER not in html
    assert 'for more information about the count' not in html


def test_form_shows_checkbox_reflecting_setting(super_admin_client, restore_circle):
    _update(show_counter_guides=False)
    html = super_admin_client.get(EDIT_URL).get_data(as_text=True)
    checkbox = html[html.index('name="show_counter_guides"'):][:200]
    assert 'checked' not in checkbox.split('>')[0]

    _update(show_counter_guides=True)
    html = super_admin_client.get(EDIT_URL).get_data(as_text=True)
    checkbox = html[html.index('name="show_counter_guides"'):][:200]
    assert 'checked' in checkbox.split('>')[0]


def _form_from_circle(**overrides):
    """A valid circle-edit submission mirroring the test circle's current values."""
    circle = CircleModel(get_db_session()).get_by_slug(TEST_CIRCLE_SLUG)
    form = {
        'circle_name': circle['circle_name'], 'name': circle['name'] or 'Test Org',
        'website': circle['website'] or '', 'contact': circle['contact'] or '',
        'count_contact': circle['count_contact'] or 'test-contact@example.com',
        'count_event_name': circle['count_event_name'] or '',
        'count_info_url': circle['count_info_url'] or '',
        'from_email': circle['from_email'] or '', 'test_recipient': circle['test_recipient'] or '',
        'display_timezone': circle['display_timezone'], 'is_cbc': 'on',
        'registration_opens_months': circle['registration_opens_months'],
        'registration_closes_days': circle['registration_closes_days'],
        'latitude': circle['latitude'] or '', 'longitude': circle['longitude'] or '',
        'count_date': [d for d in circle['yearly_count_dates'].values()] or ['2099-12-19'],
    }
    form.update(overrides)
    return form


def test_form_saves_setting(super_admin_client, restore_circle):
    _update(show_counter_guides=True)
    resp = super_admin_client.post(EDIT_URL, data=_form_from_circle())  # box unchecked
    assert resp.status_code == 302
    db = get_db_session()
    db.expire_all()
    assert CircleModel(db).get_by_slug(TEST_CIRCLE_SLUG)['show_counter_guides'] is False

    resp = super_admin_client.post(EDIT_URL, data=_form_from_circle(show_counter_guides='on'))
    assert resp.status_code == 302
    db.expire_all()
    assert CircleModel(db).get_by_slug(TEST_CIRCLE_SLUG)['show_counter_guides'] is True
