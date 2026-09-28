from string import Template


def substitute_placeholders(text, values):
    """Safely substitute $identifier/${identifier} placeholders into
    admin-authored email prose. Uses string.Template.safe_substitute rather
    than Jinja/render_template_string/.format/% - those can execute code or
    reach into object attributes if the surrounding text is attacker- or
    admin-controlled; string.Template only ever does literal substring
    replacement and cannot execute anything. safe_substitute (not
    substitute) leaves any unrecognized $identifier in the text as-is rather
    than raising, as defense in depth alongside the save-time placeholder
    whitelist check in routes/admin.py."""
    return Template(text).safe_substitute(values)


def extract_placeholders(text):
    """Every $identifier/${identifier} referenced in text, for save-time
    validation against a block's placeholder whitelist
    (config/email_content_blocks.py)."""
    return set(m.group('named') or m.group('braced') for m in Template.pattern.finditer(text)
               if m.group('named') or m.group('braced'))
