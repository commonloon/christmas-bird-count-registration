# Updated by Claude AI on 2026-09-28
"""Global (not per-circle) key/value settings, stored in the app_settings table."""

from datetime import datetime, timezone

from models.db import AppSetting

SCHEDULER_ALERT_FROM_EMAIL_KEY = 'scheduler_alert_from_email'
DEFAULT_SCHEDULER_ALERT_FROM_EMAIL = 'birdcount@naturevancouver.ca'

SETTING_DEFAULTS = {
    SCHEDULER_ALERT_FROM_EMAIL_KEY: DEFAULT_SCHEDULER_ALERT_FROM_EMAIL,
}


class AppSettingsModel:
    def __init__(self, db_session):
        self.db = db_session

    def get(self, key):
        """Stored value, else the setting's built-in default (None if it has none)."""
        row = self.db.query(AppSetting).filter_by(key=key).first()
        return row.value if row else SETTING_DEFAULTS.get(key)

    def set(self, key, value, updated_by=None):
        row = self.db.query(AppSetting).filter_by(key=key).first()
        now = datetime.now(timezone.utc)
        if row:
            row.value = value
            row.updated_at = now
            row.updated_by = updated_by
        else:
            self.db.add(AppSetting(key=key, value=value, updated_at=now, updated_by=updated_by))
        self.db.commit()

    def get_scheduler_alert_from_email(self):
        return self.get(SCHEDULER_ALERT_FROM_EMAIL_KEY)
