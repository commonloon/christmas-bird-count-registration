# Updated by Claude AI on 2026-09-12
"""Known email/link-security scanners that should never be able to obtain an
authenticated session from a magic-link token - see routes/auth.py's
verify() for how this is used.

Matched by Referer, not by IP/host: this class of vendor runs distributed,
load-balanced scanning infrastructure with no stable IP range worth
allowlisting (confirmed via production logs - the same vendor's traffic
came from different addresses on different occasions), while the Referer
their proxy sets has been consistently reproducible.

Referer is a plain, client-supplied header - it proves nothing about who
actually sent the request, so a match here must NEVER be treated as "safe to
log in as normal, just don't mark the token used". That would let anyone who
later obtains a copy of an already-used token revive it by adding one
well-known header. Instead (see verify()), a match short-circuits before any
token/session logic runs at all: the request gets back bland, token-state-
independent content and can never obtain a session, so it doesn't matter
that its hit doesn't consume the token - there is nothing here to replay or
steal.
"""

KNOWN_LINK_SCANNERS = {
    # Trend Micro Email Security's link-scanning/rewriting proxy. Confirmed
    # via production access logs (fraser-estuary-kba.birdcount.ca) - both the
    # original magic-link-burned-by-a-scanner report and a later login on the
    # same circle showed this Referer on automated hits.
    'trendmicro_urlprotect': 'urlprotect.trendmicro.com',
}


def matched_known_link_scanner(referer):
    """Return the matched scanner's name for a Referer header value, or None."""
    if not referer:
        return None
    for name, referer_substring in KNOWN_LINK_SCANNERS.items():
        if referer_substring in referer:
            return name
    return None
