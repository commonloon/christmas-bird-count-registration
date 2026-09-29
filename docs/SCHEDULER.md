# Scheduled Emails

Three emails go out on a schedule, per circle:

| Email type key | What it is | Default send times (circle's local time) |
|---|---|---|
| `team_update` | Changes to an area's team since its last update, to that area's leaders (only areas with changes) | 7:00 am and 6:00 pm, every day |
| `weekly_summary` | Same, over the last 7 days | Friday 11:00 pm |
| `admin_digest` | Unassigned participants, to the circle's admins (only when there are some) | 6:00 pm, every day |

Emails only go out from the day registration opens through the count date (inclusive). Outside that window
nothing runs and nothing is logged. Times and the season are evaluated in each circle's own
`display_timezone`, not server time (the server runs in UTC).

## How it runs

A single hourly cron entry runs a Flask CLI command. Nothing is reachable over HTTP, so there is no token to
manage.

```
0 * * * * cd <app directory> && <path to flask> tick-scheduled-emails
```

Install it in the `apache` user's crontab on the app node (`crontab -e -u apache` as root). The exact
`cd` directory and `flask` path (virtualenv) depend on how the app is installed on the node.

Each tick, for every row in `circle_email_schedules`:

1. Work out that row's most recent expected occurrence (in the circle's timezone).
2. Skip it if the row was created after that occurrence, if the occurrence was outside the circle's season,
   or if any attempt (success *or* failure) is already logged for it.
3. If it is within 3 hours of the occurrence, run it. If it is older than that and was never attempted,
   log a failure ("did not run within the 3h retry window") instead of running it late.

So a missed tick (cron or the app briefly down) is caught up automatically within 3 hours. A run that was
attempted and **failed is never retried automatically** - a retry after a partial send could email leaders twice.

Changing a circle's send times, adding a circle, or changing a count date never requires touching cron.

## Cron environment

Cron does not always inherit the environment the app runs with. The command needs `DATABASE_URL`,
`SECRET_KEY` and the `SMTP2GO_*` variables, and refuses to run (exit 1, message in the log) if `DATABASE_URL`
is missing. To check what cron sees, temporarily add this entry, wait a minute, read the file, then remove
both the entry **and the file** - it contains the secrets in plain text:

```
* * * * * printenv | sort > /var/www/webroot/logs/cron_env.txt
```

## Logging and exit status

- One JSON summary line per run goes to stdout, e.g.
  `{"attempted": 1, "succeeded": 1, "failed": 0, "expired": 0, "notified": false, "skipped_locked": false}`
- If `SCHEDULER_LOG_FILE` is set (suggested: `/var/www/webroot/logs/scheduler.log`, which is outside the
  web root `/var/www/webroot/ROOT`), scheduler logging also goes to that file, rotated at about 1 MB with 5
  backups. No logrotate configuration is needed. Set it in the cron entry:
  `0 * * * * cd <app directory> && SCHEDULER_LOG_FILE=/var/www/webroot/logs/scheduler.log <path to flask> tick-scheduled-emails`
  (the variable must come after the `cd ... &&`, or it applies to `cd` only), or set it as an app-node variable.
- Exit status is 1 if any job failed or missed its window, or the tick crashed; otherwise 0.
- Two ticks never run at once: a Postgres advisory lock makes a second one exit immediately with
  `"skipped_locked": true`. This also keeps things safe if the app is ever scaled to more than one instance.

Run by hand for one circle (this sends real email if anything is due): `flask tick-scheduled-emails --circle vancouver`

## Failures

When any job fails or misses its window in a tick:

- **Super-admins** get one summary email listing every failure with its error text.
- **Each affected circle's admins** get a short note about their own circle (no raw error text).
- The sender is the "Alert From address" on the super-admin Scheduler page
  (`/bigbird/scheduler`), default `birdcount@naturevancouver.ca`; it must be on an allowed domain.

Every attempt, including missed ones, is recorded in `email_schedule_run_log` and shown on the Scheduler page.

## Admin pages

- **Circle admins / super-admins:** `/bigbird/circles/<slug>/email-schedule` (linked from Circle Settings and
  the admin dashboard) - view and edit that circle's send times, see when its email season starts and ends,
  and see recent runs.
- **Super-admins:** `/bigbird/scheduler` - the alert sender setting, recent runs across all circles, and a
  collapsed **Manual run** section for recovery after a failure has been fixed. A manual run needs the circle's
  slug typed as confirmation, only works during the circle's season, and only sends what changed since each
  team's last email, so running it right after a normal run sends nothing new.

## Data

- `circle_email_schedules`: one row per send time. `hour` is the local hour; `day_of_week` follows Python's
  `date.weekday()` (0 = Monday ... 6 = Sunday, so Friday is 4), NULL meaning every day.
- `email_schedule_run_log`: append-only; the tick's only source of truth for "already attempted".
- `app_settings`: global key/value settings (currently the alert sender).
- Migration `0012` creates these and gives every existing circle the default schedule. Rows created by that
  migration ignore any occurrence earlier than the migration itself, so deploying it does not trigger a burst
  of catch-up emails.

Code: `services/scheduler_service.py` (logic), `services/scheduler_cli.py` (the command),
`models/email_schedule.py`, `models/app_settings.py`. Tests: `tests/unit/test_scheduler_service.py`,
`tests/unit/test_scheduler_admin_routes.py`.
