# Updated by Claude AI on 2026-09-09
"""
Registry of admin-customizable prose blocks for outgoing emails.

This is the single source of truth for: which blocks exist per email type, the
admin-UI form fields (routes/admin.py's email content routes), the save-time
placeholder whitelist (a save is rejected if submitted text references a
$placeholder not listed here), and the tier-3 hardcoded fallback text used
when neither a circle override nor a super-admin default has been set yet
(models/email_content.py's EmailContentModel.resolve_all()).

Fallback text is today's exact current wording, extracted verbatim from
services/email_service.py and templates/emails/registration_confirmation.html
- so applying this migration changes no visible email content until an admin
actually edits a block. The two "whats_next_*" blocks are a deliberate
simplification of today's template: the live template further branches on
whether area leaders are already assigned and on FEEDER participation, which
free-text admin prose can't conditionally express - those two narrower cases
are folded into the general wording below.

Only registration_confirmation/withdrawal_confirmation are registered in
Stage 1 (the two live transactional emails). Stage 2 adds team_update,
weekly_summary, admin_digest once the scheduler's per-circle loop lands -
adding entries here is all that's needed to surface them in the same UI.
"""

EMAIL_CONTENT_BLOCKS = {
    'registration_confirmation': {
        'subject': {
            'label': 'Email subject',
            'allow_newlines': False,
            'max_length': 200,
            'placeholders': ['year', 'count_event_name'],
            'fallback': '$year $count_event_name Registration Confirmation',
        },
        'intro_assigned': {
            'label': 'Welcome message (participant assigned to an area)',
            'allow_newlines': True,
            'max_length': 500,
            'placeholders': ['area_name'],
            'fallback': "You have been registered for $area_name.",
        },
        'intro_unassigned': {
            'label': 'Welcome message (participant not yet assigned)',
            'allow_newlines': True,
            'max_length': 500,
            'placeholders': [],
            'fallback': "You have been registered for assignment wherever you're needed most.",
        },
        'whats_next_assigned': {
            'label': "What's Next (participant assigned to an area)",
            'allow_newlines': True,
            'max_length': 3000,
            'placeholders': ['count_event_name'],
            'fallback': (
                "Your area leader is your main contact for information about count day and will "
                "let you know where to meet and what to expect.\n\n"
                "The count typically begins early in the morning and lasts until dusk - please let "
                "your area leader know if you aren't available for the full day.\n\n"
                "The $count_event_name happens rain or shine, so dress to stay warm and dry, and "
                "bring binoculars and a sense of adventure!"
            ),
        },
        'whats_next_unassigned': {
            'label': "What's Next (participant not yet assigned)",
            'allow_newlines': True,
            'max_length': 3000,
            'placeholders': ['count_event_name'],
            'fallback': (
                "You will receive an email once an administrator has assigned you to a count area, "
                "usually within the next week. Once assigned, your area leader will be your main "
                "contact for count day details - they will let you know where to meet and what to "
                "expect.\n\n"
                "The count typically begins early in the morning and lasts until dusk - please let "
                "your area leader know if you aren't available for the full day.\n\n"
                "The $count_event_name happens rain or shine, so dress to stay warm and dry, and "
                "bring binoculars and a sense of adventure!"
            ),
        },
        'closing_message': {
            'label': 'Closing message',
            'allow_newlines': True,
            'max_length': 500,
            'placeholders': ['count_contact'],
            'fallback': 'Welcome to the count! For questions, contact: $count_contact',
        },
    },
    'withdrawal_confirmation': {
        'subject': {
            'label': 'Email subject',
            'allow_newlines': False,
            'max_length': 200,
            'placeholders': ['count_event_name'],
            'fallback': '[$count_event_name] Withdrawal Confirmation',
        },
        'intro_message': {
            'label': 'Intro message',
            'allow_newlines': True,
            'max_length': 500,
            'placeholders': ['first_name', 'last_name', 'year', 'count_event_name'],
            'fallback': (
                'Dear $first_name $last_name,\n\n'
                'Your withdrawal from the $year $count_event_name has been recorded.'
            ),
        },
        'closing_message': {
            'label': 'Closing message',
            'allow_newlines': True,
            'max_length': 1000,
            'placeholders': ['count_contact', 'organization_name', 'count_event_name'],
            'fallback': (
                'If your circumstances change and you would like to participate, please contact:\n'
                '$count_contact\n\n'
                'We hope to have you join us again in the future.\n\n'
                'Best regards,\n'
                '$organization_name - $count_event_name Registration System'
            ),
        },
    },
    # Stage 2: the three Task-Scheduler-driven digest emails (test/email_generator.py).
    # Unlike the two transactional types above, team_update/weekly_summary send one
    # email per area (looped per area code) - their subject blocks get $area_code/
    # $date substituted fresh per area, not once per circle. Fallback text here
    # replaces what were literal hardcoded strings in config/email_settings.py's old
    # EMAIL_SUBJECTS dict (which hardcoded "Vancouver CBC" unconditionally - a real
    # cross-circle bug this registry entry incidentally fixes) and the three
    # templates/emails/*.html files.
    'team_update': {
        'subject': {
            'label': 'Email subject',
            'allow_newlines': False,
            'max_length': 200,
            'placeholders': ['date', 'count_event_name', 'area_code'],
            'fallback': '$date $count_event_name Area $area_code Update',
        },
        'greeting_intro': {
            'label': 'Greeting / intro message',
            'allow_newlines': True,
            'max_length': 500,
            'placeholders': ['count_event_name'],
            'fallback': 'Your $count_event_name team has been updated. Here are the recent changes:',
        },
        'next_steps_body': {
            'label': "Next Steps (shown after the changes list)",
            'allow_newlines': True,
            'max_length': 2000,
            'placeholders': [],
            'fallback': (
                'Share meeting location and time information.\n\n'
                'Coordinate any special equipment or preparation needs.'
            ),
        },
    },
    'weekly_summary': {
        'subject': {
            'label': 'Email subject',
            'allow_newlines': False,
            'max_length': 200,
            'placeholders': ['date', 'count_event_name', 'area_code'],
            'fallback': '$date $count_event_name Area $area_code Weekly Summary',
        },
        'next_steps_body': {
            'label': "Next Steps (shown after the changes list)",
            'allow_newlines': True,
            'max_length': 2000,
            'placeholders': [],
            'fallback': (
                'Confirm count day logistics with your team.\n\n'
                'Share meeting location and time details.\n\n'
                'Coordinate transportation and equipment needs.\n\n'
                'Review count area boundaries and special considerations.'
            ),
        },
    },
    'admin_digest': {
        'subject': {
            'label': 'Email subject',
            'allow_newlines': False,
            'max_length': 200,
            'placeholders': ['date', 'count_event_name'],
            'fallback': '$date $count_event_name Unassigned Participants',
        },
        'greeting_salutation': {
            'label': 'Greeting / salutation',
            'allow_newlines': False,
            'max_length': 200,
            'placeholders': ['count_event_name'],
            'fallback': 'Dear Administrators,',
        },
        'recommended_actions_body': {
            'label': 'Recommended Actions',
            'allow_newlines': True,
            'max_length': 2000,
            'placeholders': [],
            'fallback': (
                'Review area capacity and assign participants to areas needing more volunteers.\n\n'
                'Consider leadership potential for participants expressing interest.\n\n'
                'Prioritize participants who have been waiting longest.\n\n'
                'Contact participants if clarification is needed on their preferences.'
            ),
        },
    },
}


def get_email_types():
    """Ordered list of email_type keys currently registered."""
    return list(EMAIL_CONTENT_BLOCKS.keys())


def get_blocks(email_type):
    """Block registry for one email_type, or {} if not registered (e.g. a Stage 2
    email type before Stage 2 lands)."""
    return EMAIL_CONTENT_BLOCKS.get(email_type, {})
