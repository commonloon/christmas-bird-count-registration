# Updated by Claude AI on 2026-10-22
"""
Throwaway-mailbox domains refused at registration. A bot used one of these
(fextemp.com) to harvest our registration confirmation emails, so a volunteer
supplying one is almost certainly not a real registrant. This is a small,
hand-maintained list of the most common services - add domains as new abuse
turns up in the logs. Subdomains of a listed domain are matched too.
"""

DISPOSABLE_EMAIL_DOMAINS = frozenset({
    'fextemp.com',
    'mailinator.com',
    'guerrillamail.com',
    'guerrillamail.net',
    'guerrillamail.org',
    'guerrillamailblock.com',
    'sharklasers.com',
    'grr.la',
    'yopmail.com',
    'yopmail.net',
    '10minutemail.com',
    '10minutemail.net',
    'temp-mail.org',
    'tempmail.com',
    'tempmail.net',
    'tempmailo.com',
    'tempail.com',
    'throwawaymail.com',
    'trashmail.com',
    'trashmail.net',
    'getnada.com',
    'nada.email',
    'dispostable.com',
    'maildrop.cc',
    'mailnesia.com',
    'mohmal.com',
    'emailondeck.com',
    'fakeinbox.com',
    'mintemail.com',
    'spamgourmet.com',
    'mytemp.email',
    'burnermail.io',
    'moakt.com',
    'discard.email',
    'inboxkitten.com',
})
