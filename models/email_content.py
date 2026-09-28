from datetime import datetime, timezone

from models.db import EmailContentDefault, EmailContentOverride
from config.email_content_blocks import get_blocks


class EmailContentModel:
    """Resolve and manage admin-customizable email prose blocks
    (config/email_content_blocks.py). Three-tier fallback per block: circle
    override -> super-admin global default -> hardcoded registry fallback."""

    def __init__(self, db_session):
        self.db = db_session

    def resolve_all(self, circle_slug, email_type):
        """{block_key: text} for every block registered under email_type, with
        the 3-tier fallback already applied. Two queries total (all overrides
        for this circle+type, all defaults for this type) - never one query
        per block, since a caller resolves every block for an email at once."""
        blocks = get_blocks(email_type)
        overrides = self.get_overrides_for_circle(circle_slug, email_type)
        defaults = self.get_defaults_for_type(email_type, use_fallback=False)

        resolved = {}
        for block_key, block_def in blocks.items():
            if block_key in overrides:
                resolved[block_key] = overrides[block_key]
            elif block_key in defaults:
                resolved[block_key] = defaults[block_key]
            else:
                resolved[block_key] = block_def['fallback']
        return resolved

    def get_overrides_for_circle(self, circle_slug, email_type):
        """Raw override text only (no fallback applied) - {block_key: text}
        for whichever blocks this circle has actually overridden. Used to show
        an override-vs-inherited badge in the circle admin UI."""
        rows = self.db.query(EmailContentOverride).filter_by(
            circle_slug=circle_slug, email_type=email_type,
        ).all()
        return {row.block_key: row.content for row in rows}

    def get_defaults_for_type(self, email_type, use_fallback=True):
        """{block_key: text} of super-admin global defaults for one email
        type. With use_fallback=True (the super-admin edit form's use case),
        any block with no default row yet is filled in with the registry's
        hardcoded fallback, so the form always shows "what renders today,"
        never a blank box."""
        rows = self.db.query(EmailContentDefault).filter_by(email_type=email_type).all()
        defaults = {row.block_key: row.content for row in rows}
        if use_fallback:
            for block_key, block_def in get_blocks(email_type).items():
                defaults.setdefault(block_key, block_def['fallback'])
        return defaults

    def set_default(self, email_type, block_key, content, updated_by):
        """Create or update a super-admin global default for one block."""
        row = self.db.query(EmailContentDefault).filter_by(
            email_type=email_type, block_key=block_key,
        ).first()
        now = datetime.now(timezone.utc)
        if row:
            row.content = content
            row.updated_at = now
            row.updated_by = updated_by
        else:
            row = EmailContentDefault(
                email_type=email_type, block_key=block_key, content=content,
                updated_at=now, updated_by=updated_by,
            )
            self.db.add(row)
        self.db.commit()

    def set_override(self, circle_slug, email_type, block_key, content, updated_by):
        """Create or update one circle's override for one block."""
        row = self.db.query(EmailContentOverride).filter_by(
            circle_slug=circle_slug, email_type=email_type, block_key=block_key,
        ).first()
        now = datetime.now(timezone.utc)
        if row:
            row.content = content
            row.updated_at = now
            row.updated_by = updated_by
        else:
            row = EmailContentOverride(
                circle_slug=circle_slug, email_type=email_type, block_key=block_key,
                content=content, updated_at=now, updated_by=updated_by,
            )
            self.db.add(row)
        self.db.commit()

    def delete_override(self, circle_slug, email_type, block_key):
        """Reset one block back to the super-admin default (or hardcoded
        fallback) by removing this circle's override row, if any."""
        self.db.query(EmailContentOverride).filter_by(
            circle_slug=circle_slug, email_type=email_type, block_key=block_key,
        ).delete()
        self.db.commit()
