# Updated by Claude AI on 2026-09-09
"""
Tests for the per-circle customizable email content feature
(EMAIL_CUSTOMIZATION_PLAN.txt Stage 1): placeholder substitution safety,
content sanitization, EmailContentModel's 3-tier resolution and circle
isolation, and the admin routes' access control and save/reset behavior.
"""

import pytest

from config.database import get_db_session
from config.email_content_blocks import get_blocks
from models.db import EmailContentDefault, EmailContentOverride
from models.email_content import EmailContentModel
from services.email_content_service import substitute_placeholders, extract_placeholders
from services.email_service import email_service
from services.security import sanitize_email_content
from tests.test_config import TEST_CIRCLE_SLUG

# A second real circle (present in local dev data - see docs/TEST_SETUP.md)
# used only to prove overrides/defaults don't leak across circle_slug. Only
# email_content_overrides/defaults rows are ever written for this circle here
# (never participants or its own circle config), and every test that touches
# it cleans those rows up afterward.
OTHER_CIRCLE_SLUG = 'nanaimo'

EMAIL_TYPE = 'registration_confirmation'
BLOCK_KEY = 'subject'
BLOCK_DEF = get_blocks(EMAIL_TYPE)[BLOCK_KEY]


# --- Placeholder substitution safety -----------------------------------

class TestSubstitutePlaceholders:
    def test_known_placeholder_is_substituted(self):
        result = substitute_placeholders('Hi $first_name, welcome!', {'first_name': 'Alice'})
        assert result == 'Hi Alice, welcome!'

    def test_braced_placeholder_is_substituted(self):
        result = substitute_placeholders('${count_event_name} 2026', {'count_event_name': 'Test Count'})
        assert result == 'Test Count 2026'

    def test_unknown_placeholder_left_literal(self):
        """Defense in depth alongside the save-time whitelist check - an
        unrecognized $identifier must never raise or vanish, just stay as-is."""
        result = substitute_placeholders('Hi $unknown_field!', {'first_name': 'Alice'})
        assert result == 'Hi $unknown_field!'

    def test_cannot_execute_code(self):
        """string.Template.safe_substitute only ever does literal substring
        replacement - text that looks like a code/attribute reference must
        pass through inert, never be evaluated."""
        malicious = '${__class__.__init__.__globals__}'
        result = substitute_placeholders(malicious, {'first_name': 'Alice'})
        assert result == malicious

    def test_extract_placeholders_finds_both_syntaxes(self):
        found = extract_placeholders('Hi $first_name, from ${organization_name}. $undeclared')
        assert found == {'first_name', 'organization_name', 'undeclared'}

    def test_extract_placeholders_empty_for_plain_text(self):
        assert extract_placeholders('No placeholders here.') == set()


# --- Sanitization --------------------------------------------------------

class TestSanitizeEmailContent:
    def test_truncates_to_max_length(self):
        result = sanitize_email_content('x' * 500, max_length=10, allow_newlines=False)
        assert result == 'x' * 10

    def test_strips_newlines_when_disallowed(self):
        """Subject-line blocks are used as a mail header - newlines there
        enable header injection, so they must be stripped, not preserved."""
        result = sanitize_email_content('Subject line\nBcc: evil@example.com', max_length=200, allow_newlines=False)
        assert '\n' not in result

    def test_preserves_newlines_when_allowed(self):
        result = sanitize_email_content('Paragraph one.\n\nParagraph two.', max_length=200, allow_newlines=True)
        assert '\n' in result

    def test_non_string_input_returns_empty(self):
        assert sanitize_email_content(None, max_length=10, allow_newlines=True) == ''


# --- EmailContentModel resolution + isolation ----------------------------

STAGE1_EMAIL_TYPES = ('registration_confirmation', 'withdrawal_confirmation')


@pytest.fixture
def db_session():
    return get_db_session()


@pytest.fixture(autouse=True)
def clean_up_test_rows(db_session):
    """TEST_CIRCLE_SLUG ('test') is the dedicated always-safe-to-wipe test
    circle (see docs/TEST_SETUP.md) - route-level save tests below write
    overrides for every block of a Stage 1 email type at once (a real "Save"
    submits a whole section, not one block), so cleanup here is scoped to the
    whole email type for that circle, not just BLOCK_KEY. OTHER_CIRCLE_SLUG is
    a real circle (used only for isolation checks), so its cleanup stays
    narrowly scoped to the exact row the isolation test creates."""
    def _clean():
        db_session.query(EmailContentDefault).filter(
            EmailContentDefault.email_type.in_(STAGE1_EMAIL_TYPES),
        ).delete(synchronize_session=False)
        db_session.query(EmailContentOverride).filter(
            EmailContentOverride.email_type.in_(STAGE1_EMAIL_TYPES),
            EmailContentOverride.circle_slug == TEST_CIRCLE_SLUG,
        ).delete(synchronize_session=False)
        db_session.query(EmailContentOverride).filter(
            EmailContentOverride.email_type == EMAIL_TYPE,
            EmailContentOverride.block_key == BLOCK_KEY,
            EmailContentOverride.circle_slug == OTHER_CIRCLE_SLUG,
        ).delete(synchronize_session=False)
        db_session.commit()

    _clean()
    yield
    _clean()


class TestEmailContentModelResolution:
    def test_resolves_to_hardcoded_fallback_when_nothing_set(self, db_session):
        model = EmailContentModel(db_session)
        resolved = model.resolve_all(TEST_CIRCLE_SLUG, EMAIL_TYPE)
        assert resolved[BLOCK_KEY] == BLOCK_DEF['fallback']

    def test_resolves_to_super_admin_default_when_set(self, db_session):
        model = EmailContentModel(db_session)
        model.set_default(EMAIL_TYPE, BLOCK_KEY, 'DEFAULT TEXT $year', 'tester@example.com')

        resolved = model.resolve_all(TEST_CIRCLE_SLUG, EMAIL_TYPE)
        assert resolved[BLOCK_KEY] == 'DEFAULT TEXT $year'

    def test_circle_override_wins_over_default(self, db_session):
        model = EmailContentModel(db_session)
        model.set_default(EMAIL_TYPE, BLOCK_KEY, 'DEFAULT TEXT', 'tester@example.com')
        model.set_override(TEST_CIRCLE_SLUG, EMAIL_TYPE, BLOCK_KEY, 'OVERRIDE TEXT', 'tester@example.com')

        resolved = model.resolve_all(TEST_CIRCLE_SLUG, EMAIL_TYPE)
        assert resolved[BLOCK_KEY] == 'OVERRIDE TEXT'

    def test_override_on_one_circle_does_not_leak_to_another(self, db_session):
        """The core data-integrity property this feature depends on: one
        circle's override must never be visible when resolving another
        circle's email content."""
        model = EmailContentModel(db_session)
        model.set_default(EMAIL_TYPE, BLOCK_KEY, 'DEFAULT TEXT', 'tester@example.com')
        model.set_override(TEST_CIRCLE_SLUG, EMAIL_TYPE, BLOCK_KEY, 'TEST CIRCLE OVERRIDE', 'tester@example.com')

        other_resolved = model.resolve_all(OTHER_CIRCLE_SLUG, EMAIL_TYPE)
        assert other_resolved[BLOCK_KEY] == 'DEFAULT TEXT'

        this_resolved = model.resolve_all(TEST_CIRCLE_SLUG, EMAIL_TYPE)
        assert this_resolved[BLOCK_KEY] == 'TEST CIRCLE OVERRIDE'

    def test_delete_override_falls_back_to_default(self, db_session):
        model = EmailContentModel(db_session)
        model.set_default(EMAIL_TYPE, BLOCK_KEY, 'DEFAULT TEXT', 'tester@example.com')
        model.set_override(TEST_CIRCLE_SLUG, EMAIL_TYPE, BLOCK_KEY, 'OVERRIDE TEXT', 'tester@example.com')

        model.delete_override(TEST_CIRCLE_SLUG, EMAIL_TYPE, BLOCK_KEY)

        resolved = model.resolve_all(TEST_CIRCLE_SLUG, EMAIL_TYPE)
        assert resolved[BLOCK_KEY] == 'DEFAULT TEXT'

    def test_get_overrides_for_circle_excludes_defaults_and_fallback(self, db_session):
        model = EmailContentModel(db_session)
        model.set_default(EMAIL_TYPE, BLOCK_KEY, 'DEFAULT TEXT', 'tester@example.com')

        overrides = model.get_overrides_for_circle(TEST_CIRCLE_SLUG, EMAIL_TYPE)
        assert BLOCK_KEY not in overrides

    def test_get_defaults_for_type_without_fallback_only_returns_set_rows(self, db_session):
        model = EmailContentModel(db_session)
        defaults = model.get_defaults_for_type(EMAIL_TYPE, use_fallback=False)
        assert BLOCK_KEY not in defaults

    def test_get_defaults_for_type_with_fallback_fills_unset_blocks(self, db_session):
        model = EmailContentModel(db_session)
        defaults = model.get_defaults_for_type(EMAIL_TYPE, use_fallback=True)
        assert defaults[BLOCK_KEY] == BLOCK_DEF['fallback']

    def test_set_default_upserts_rather_than_duplicates(self, db_session):
        model = EmailContentModel(db_session)
        model.set_default(EMAIL_TYPE, BLOCK_KEY, 'FIRST', 'tester@example.com')
        model.set_default(EMAIL_TYPE, BLOCK_KEY, 'SECOND', 'tester@example.com')

        rows = db_session.query(EmailContentDefault).filter_by(
            email_type=EMAIL_TYPE, block_key=BLOCK_KEY,
        ).all()
        assert len(rows) == 1
        assert rows[0].content == 'SECOND'


# --- Admin route access control -------------------------------------------

class TestCircleEmailContentRouteAccess:
    def test_anonymous_redirected_to_login(self, client):
        resp = client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_circle_admin_can_access_own_circle(self, admin_client):
        resp = admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content')
        assert resp.status_code == 200

    def test_circle_admin_cannot_access_other_circle(self, admin_client):
        """admin_client is a circle-admin whose g.circle_slug resolves to
        TEST_CIRCLE_SLUG for every request (from the fixed test Host) -
        hitting a *different* circle's slug in the URL must be denied, not
        silently treated as if it were their own circle. This is the
        access-control property the user specifically asked to confirm."""
        resp = admin_client.get(f'/bigbird/circles/{OTHER_CIRCLE_SLUG}/email-content')
        assert resp.status_code == 302
        assert 'email-content' not in resp.headers['Location']

    def test_super_admin_can_access_any_circle(self, super_admin_client):
        resp = super_admin_client.get(f'/bigbird/circles/{OTHER_CIRCLE_SLUG}/email-content')
        assert resp.status_code == 200


class TestEmailContentDefaultsRouteAccess:
    def test_circle_admin_denied_super_admin_only(self, admin_client):
        resp = admin_client.get('/bigbird/email-content/defaults')
        assert resp.status_code == 302

    def test_super_admin_can_access(self, super_admin_client):
        resp = super_admin_client.get('/bigbird/email-content/defaults')
        assert resp.status_code == 200


def _full_form(email_type, overrides=None):
    """All blocks of one email_type filled with their fallback text, with any
    overrides layered on top - a real "Save" submits every block in a section
    together (see routes/admin.py's circle_email_content 'save' action)."""
    form = {'email_type': email_type, 'action': 'save'}
    for key, block_def in get_blocks(email_type).items():
        form[f'{email_type}__{key}'] = block_def['fallback']
    for key, value in (overrides or {}).items():
        form[f'{email_type}__{key}'] = value
    return form


class TestCircleEmailContentSaveAndReset:
    def test_save_persists_and_resolves(self, admin_client, db_session):
        form = _full_form(EMAIL_TYPE, {BLOCK_KEY: 'CUSTOM SUBJECT $year'})
        resp = admin_client.post(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content', data=form)
        assert resp.status_code == 302

        resolved = EmailContentModel(db_session).resolve_all(TEST_CIRCLE_SLUG, EMAIL_TYPE)
        assert resolved[BLOCK_KEY] == 'CUSTOM SUBJECT $year'

    def test_save_rejects_disallowed_placeholder_and_persists_nothing(self, admin_client, db_session):
        """The whole section's save must be all-or-nothing: one block with a
        placeholder outside its whitelist rejects the entire submission, not
        just that one block."""
        form = _full_form(EMAIL_TYPE, {BLOCK_KEY: '$evil_placeholder'})
        resp = admin_client.post(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content', data=form)
        assert resp.status_code == 302

        overrides = EmailContentModel(db_session).get_overrides_for_circle(TEST_CIRCLE_SLUG, EMAIL_TYPE)
        assert overrides == {}

    def test_reset_removes_override(self, admin_client, db_session):
        model = EmailContentModel(db_session)
        model.set_override(TEST_CIRCLE_SLUG, EMAIL_TYPE, BLOCK_KEY, 'OVERRIDE TEXT', 'tester@example.com')

        resp = admin_client.post(
            f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content',
            data={'email_type': EMAIL_TYPE, 'action': 'reset', 'block_key': BLOCK_KEY},
        )
        assert resp.status_code == 302

        overrides = model.get_overrides_for_circle(TEST_CIRCLE_SLUG, EMAIL_TYPE)
        assert BLOCK_KEY not in overrides


class TestEmailContentPreviewRoute:
    def test_registration_confirmation_preview_renders(self, admin_client):
        resp = admin_client.get(
            f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/registration_confirmation')
        assert resp.status_code == 200
        assert b'Registration Confirmed' in resp.data

    def test_withdrawal_confirmation_preview_renders(self, admin_client):
        resp = admin_client.get(
            f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/withdrawal_confirmation')
        assert resp.status_code == 200

    def test_invalid_email_type_redirects(self, admin_client):
        resp = admin_client.get(
            f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/not_a_real_type')
        assert resp.status_code == 302


# --- Overrides actually reaching the generated emails ----------------------
#
# The tests above only prove the save -> DB -> resolve_all() chain works.
# They do NOT prove a saved override actually reaches the rendered email
# content - that's a separate wiring path (email_service.py's
# _resolve_registration_confirmation_content/_resolve_withdrawal_confirmation_content,
# the intro_text/whats_next_text/closing_text template variables, the nl2br
# filter) that could silently break independently of the DB layer. These
# tests close that gap by asserting the actual override text appears in the
# generated output - build_registration_confirmation_preview/
# build_withdrawal_confirmation_preview call the exact same resolution
# helpers send_registration_confirmation/send_withdrawal_confirmation do, so
# this exercises the real email-building code, just without sending anything.

class TestOverrideReachesGeneratedEmail:
    """build_registration_confirmation_preview() needs an active Flask app/
    request context (it calls current_app.app_context() internally, and
    org_vars resolution depends on g.circle being set from a real request's
    Host header) - so these drive it through the actual preview HTTP route
    via admin_client rather than calling the service method directly. That's
    also more realistic: it's exactly what clicking "Preview" does."""

    def test_registration_confirmation_override_appears_in_rendered_html(self, db_session, admin_client):
        EmailContentModel(db_session).set_override(
            TEST_CIRCLE_SLUG, 'registration_confirmation', 'closing_message',
            'UNIQUE MARKER: thanks for joining $count_contact', 'tester@example.com',
        )

        resp = admin_client.get(
            f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/registration_confirmation')

        assert b'UNIQUE MARKER: thanks for joining' in resp.data

    def test_registration_confirmation_subject_override_appears_in_subject(self, db_session, admin_client):
        EmailContentModel(db_session).set_override(
            TEST_CIRCLE_SLUG, 'registration_confirmation', 'subject',
            'UNIQUE SUBJECT MARKER $year', 'tester@example.com',
        )

        resp = admin_client.get(
            f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/registration_confirmation')

        assert b'UNIQUE SUBJECT MARKER' in resp.data

    def test_registration_confirmation_intro_variant_matches_assigned_vs_unassigned(self, db_session, admin_client):
        """The assigned/unassigned block choice isn't just a resolve_all() detail -
        it must actually select the right text in the rendered output for each variant."""
        model = EmailContentModel(db_session)
        # Deliberately non-overlapping markers - "ASSIGNED VARIANT MARKER" is a
        # literal substring of "UNASSIGNED VARIANT MARKER", which would make a
        # naive `in`/`not in` check pass even if the app served the wrong variant.
        model.set_override(TEST_CIRCLE_SLUG, 'registration_confirmation', 'intro_assigned',
                            'INTRO-HAS-AREA-MARKER', 'tester@example.com')
        model.set_override(TEST_CIRCLE_SLUG, 'registration_confirmation', 'intro_unassigned',
                            'INTRO-NO-AREA-MARKER', 'tester@example.com')

        assigned_resp = admin_client.get(
            f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/registration_confirmation')
        unassigned_resp = admin_client.get(
            f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/registration_confirmation?variant=unassigned')

        assert b'INTRO-HAS-AREA-MARKER' in assigned_resp.data
        assert b'INTRO-NO-AREA-MARKER' not in assigned_resp.data
        assert b'INTRO-NO-AREA-MARKER' in unassigned_resp.data
        assert b'INTRO-HAS-AREA-MARKER' not in unassigned_resp.data

    def test_withdrawal_confirmation_override_appears_in_body(self, db_session):
        """build_withdrawal_confirmation_preview() builds a plain string, with
        no template render/current_app dependency, so it can be called directly."""
        model = EmailContentModel(db_session)
        model.set_override(TEST_CIRCLE_SLUG, 'withdrawal_confirmation', 'intro_message',
                            'UNIQUE WITHDRAWAL MARKER for $first_name', 'tester@example.com')

        subject, body = email_service.build_withdrawal_confirmation_preview(TEST_CIRCLE_SLUG)

        assert 'UNIQUE WITHDRAWAL MARKER for Sample' in body

    def test_registration_confirmation_placeholder_is_substituted_not_left_literal(self, db_session, admin_client):
        """A block referencing an allowed placeholder must render the actual
        substituted value in the email, not the raw $placeholder text."""
        EmailContentModel(db_session).set_override(
            TEST_CIRCLE_SLUG, 'registration_confirmation', 'closing_message',
            'Questions? Contact $count_contact', 'tester@example.com',
        )

        resp = admin_client.get(
            f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/registration_confirmation')

        assert b'$count_contact' not in resp.data

    def test_form_save_is_reflected_in_preview_end_to_end(self, admin_client):
        """The most realistic check: POST the same form data the admin UI
        submits, then GET the preview route (a separate request, forcing a
        fresh DB read) and confirm the saved text actually appears in the
        rendered email - not just in resolve_all()."""
        form = _full_form('registration_confirmation', {
            'whats_next_assigned': 'END TO END MARKER: see you on count day!',
        })
        save_resp = admin_client.post(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content', data=form)
        assert save_resp.status_code == 302

        preview_resp = admin_client.get(
            f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/registration_confirmation')
        assert b'END TO END MARKER: see you on count day!' in preview_resp.data
