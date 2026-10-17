# Updated by Claude AI on 2026-10-17
"""
Super-admin circle form behaviour for externally-managed counts (migration 0014):
the slug availability endpoint, creating an external circle (optional organization
and URL, required location), field validation, the multi-date list, and that
flipping is_external keeps the internal-only fields.
"""

import pytest

from config.database import get_db_session
from models.circle import CircleModel
from models.db import Circle, CircleEmailSchedule

NEW_SLUG = 'zz-new-ext'
NEW_URL = '/bigbird/circles/new'
CHECK_URL = '/bigbird/circles/slug-check'


@pytest.fixture
def cleanup_new_circle():
    def delete():
        db = get_db_session()
        db.rollback()
        db.query(CircleEmailSchedule).filter_by(circle_slug=NEW_SLUG).delete()
        db.query(Circle).filter_by(slug=NEW_SLUG).delete()
        db.commit()
    delete()
    yield
    delete()


def _external_form(**overrides):
    form = {
        'slug': NEW_SLUG, 'is_external': 'on', 'circle_name': 'Zz New External',
        'name': '', 'count_contact': 'contact@example.org', 'external_url': '',
        'latitude': '49.1', 'longitude': '-123.2', 'display_timezone': 'America/Vancouver',
        'is_cbc': 'on', 'count_date': '2099-12-19',
    }
    form.update(overrides)
    return form


def _row():
    db = get_db_session()
    db.expire_all()
    return CircleModel(db).get_by_slug(NEW_SLUG)


class TestSlugCheck:
    def test_free_slug_is_available(self, super_admin_client, cleanup_new_circle):
        data = super_admin_client.get(CHECK_URL, query_string={'slug': NEW_SLUG}).get_json()
        assert data['available'] is True

    @pytest.mark.parametrize('slug,fragment', [
        ('test', 'already exists'), ('acme', 'reserved'),
        ('Bad Slug!', 'Invalid slug'), ('a' * 51, '50 characters'),
    ])
    def test_unusable_slugs(self, super_admin_client, slug, fragment):
        data = super_admin_client.get(CHECK_URL, query_string={'slug': slug}).get_json()
        assert data['available'] is False and fragment in data['message']

    def test_empty_slug(self, super_admin_client):
        assert super_admin_client.get(CHECK_URL).get_json()['available'] is False

    def test_requires_super_admin(self, client, admin_client):
        assert client.get(CHECK_URL, query_string={'slug': NEW_SLUG}).status_code == 302
        resp = admin_client.get(CHECK_URL, query_string={'slug': NEW_SLUG})
        assert resp.status_code == 302 and 'application/json' not in resp.content_type


class TestCreateExternalCircle:
    def test_form_renders_external_controls(self, super_admin_client):
        html = super_admin_client.get(NEW_URL).get_data(as_text=True)
        assert 'name="is_external"' in html and 'name="external_url"' in html
        assert 'id="location-map"' in html and 'js/circle-form.js' in html

    def test_minimal_external_circle_is_created(self, super_admin_client, cleanup_new_circle):
        resp = super_admin_client.post(NEW_URL, data=_external_form())
        assert resp.status_code == 302
        row = _row()
        assert row['is_external'] is True
        assert row['name'] is None and row['external_url'] is None
        assert row['latitude'] == 49.1 and row['longitude'] == -123.2
        assert row['yearly_count_dates'] == {2099: '2099-12-19'}
        # internal-only fields are left unset, not blanked strings
        assert row['from_email'] is None and row['count_event_name'] is None

    def test_external_circle_with_url_and_organization(self, super_admin_client, cleanup_new_circle):
        resp = super_admin_client.post(NEW_URL, data=_external_form(
            name='Zz Birds', external_url='https://reg.example/zz'))
        assert resp.status_code == 302
        row = _row()
        assert row['name'] == 'Zz Birds' and row['external_url'] == 'https://reg.example/zz'

    @pytest.mark.parametrize('overrides,field', [
        ({'latitude': '', 'longitude': ''}, 'latitude'),
        ({'longitude': ''}, 'longitude'),
        ({'latitude': '95'}, 'latitude'),
        ({'longitude': 'abc'}, 'longitude'),
        ({'count_contact': ''}, 'count_contact'),
        ({'circle_name': ''}, 'circle_name'),
        ({'external_url': 'javascript:alert(1)'}, 'external_url'),
        ({'external_url': 'example.org/no-scheme'}, 'external_url'),
    ])
    def test_invalid_external_forms_rejected(self, super_admin_client, cleanup_new_circle, overrides, field):
        resp = super_admin_client.post(NEW_URL, data=_external_form(**overrides))
        assert resp.status_code == 200
        assert _row() is None

    def test_taken_slug_rejected(self, super_admin_client, cleanup_new_circle):
        resp = super_admin_client.post(NEW_URL, data=_external_form(slug='test'))
        assert resp.status_code == 200
        assert 'already exists' in resp.get_data(as_text=True)

    def test_internal_circle_still_requires_allowed_from_email(self, super_admin_client, cleanup_new_circle):
        form = _external_form(is_external='', from_email='someone@gmail.com',
                              name='Org', count_event_name='Zz Count')
        form.pop('is_external')
        resp = super_admin_client.post(NEW_URL, data=form)
        assert resp.status_code == 200 and _row() is None


class TestCountDatesList:
    def test_multiple_years_saved(self, super_admin_client, cleanup_new_circle):
        resp = super_admin_client.post(NEW_URL, data=_external_form(
            count_date=['2099-12-19', '2100-12-18', '']))
        assert resp.status_code == 302
        assert _row()['yearly_count_dates'] == {2099: '2099-12-19', 2100: '2100-12-18'}

    def test_two_dates_in_one_year_rejected(self, super_admin_client, cleanup_new_circle):
        resp = super_admin_client.post(NEW_URL, data=_external_form(
            count_date=['2099-12-19', '2099-12-26']))
        assert resp.status_code == 200 and _row() is None

    def test_invalid_date_rejected_and_redisplayed(self, super_admin_client, cleanup_new_circle):
        resp = super_admin_client.post(NEW_URL, data=_external_form(count_date=['2099-13-45']))
        assert resp.status_code == 200 and _row() is None
        assert 'not a valid date' in resp.get_data(as_text=True)

    def test_edit_form_lists_all_existing_dates(self, super_admin_client, cleanup_new_circle):
        super_admin_client.post(NEW_URL, data=_external_form(count_date=['2099-12-19', '2100-12-18']))
        html = super_admin_client.get(f'/bigbird/circles/{NEW_SLUG}/edit').get_data(as_text=True)
        assert 'value="2099-12-19"' in html and 'value="2100-12-18"' in html


class TestToggleExternal:
    def test_internal_fields_survive_an_external_round_trip(self, super_admin_client, cleanup_new_circle):
        internal = {
            'slug': NEW_SLUG, 'circle_name': 'Zz Round Trip', 'name': 'Zz Org',
            'count_contact': 'contact@example.org', 'count_event_name': 'Zz Count',
            'from_email': 'zz@naturevancouver.ca', 'display_timezone': 'America/Vancouver',
            'registration_opens_months': '4', 'registration_closes_days': '1',
            'latitude': '49.1', 'longitude': '-123.2', 'is_cbc': 'on', 'count_date': '2099-12-19',
        }
        assert super_admin_client.post(NEW_URL, data=internal).status_code == 302
        assert _row()['is_external'] is False

        edit = f'/bigbird/circles/{NEW_SLUG}/edit'
        as_external = {k: v for k, v in internal.items()
                       if k not in ('from_email', 'count_event_name', 'slug')}
        as_external.update(is_external='on', external_url='https://info.example/zz')
        assert super_admin_client.post(edit, data=as_external).status_code == 302
        row = _row()
        assert row['is_external'] is True and row['external_url'] == 'https://info.example/zz'
        assert row['from_email'] == 'zz@naturevancouver.ca'
        assert row['count_event_name'] == 'Zz Count'

        back = dict(internal)
        back.pop('slug')
        assert super_admin_client.post(edit, data=back).status_code == 302
        assert _row()['is_external'] is False
