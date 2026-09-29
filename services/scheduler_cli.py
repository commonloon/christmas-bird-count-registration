# Updated by Claude AI on 2026-09-28
"""
`flask tick-scheduled-emails` - the command the hourly cron entry runs.

Cron (apache user, on the FullHost app node), for example:
    0 * * * * cd /path/to/app && flask tick-scheduled-emails

Logging: one JSON summary line per run goes to stdout. If SCHEDULER_LOG_FILE is
set (e.g. /var/www/webroot/logs/scheduler.log - somewhere outside the web
root), all scheduler logging also goes to that file through a size-rotated
handler, so no logrotate configuration is needed.

Exit status: 0 when every due job succeeded (or nothing was due), 1 if any job
failed or missed its retry window, or if the tick itself crashed. Failures are
also emailed by the tick itself - the non-zero exit is just so cron output
and the log make it obvious.
"""

import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import click
from flask import current_app
from flask.cli import with_appcontext

from services.scheduler_service import tick

LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 5


def _configure_file_logging():
    """Attach the rotating file handler if SCHEDULER_LOG_FILE is set. An unwritable
    path must not stop the emails from going out, so it only warns."""
    log_file = os.environ.get('SCHEDULER_LOG_FILE')
    if not log_file:
        return
    try:
        handler = RotatingFileHandler(log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
    except OSError as e:
        click.echo(f'WARNING: cannot write SCHEDULER_LOG_FILE {log_file}: {e}', err=True)
        return
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)


@click.command('tick-scheduled-emails')
@click.option('--circle', 'circles', multiple=True,
              help='Only consider this circle slug (repeatable). Default: every circle.')
@with_appcontext
def tick_scheduled_emails_command(circles):
    """Run every scheduled email that is due right now (see services/scheduler_service.py)."""
    _configure_file_logging()
    log = logging.getLogger('scheduler.tick')

    if not os.environ.get('DATABASE_URL'):
        # Cron does not always inherit the app's environment - fail loudly, never send nothing quietly.
        log.error('DATABASE_URL is not set in this environment - refusing to run')
        click.echo('ERROR: DATABASE_URL is not set in this environment', err=True)
        sys.exit(1)

    try:
        summary = tick(current_app._get_current_object(), only_circles=circles or None)
    except Exception:
        log.exception('Scheduler tick crashed')
        click.echo('ERROR: scheduler tick crashed - see log', err=True)
        sys.exit(1)

    log.info(f'Tick complete: {json.dumps(summary)}')
    click.echo(json.dumps(summary))
    if summary['failed'] or summary['expired']:
        sys.exit(1)
