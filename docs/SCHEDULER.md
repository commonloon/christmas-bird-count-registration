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
0 * * * * /bin/bash -lc 'cd <app directory> && <path to python3> -m flask tick-scheduled-emails'
```

Install it in the `apache` user's crontab on the app node (`crontab -e -u apache` as root).

`<app directory>` is the directory containing `app.py` (the git repo root). `<path to python3>` is the app's
own Python interpreter. Run flask as a module (`python3 -m flask`) rather than as a bare `flask` command: the
`flask` executable is not on the login shell's `PATH` on the FullHost app node, and a cron entry using plain
`flask` fails with `flask: command not found`. Also set `FLASK_APP=app.py` so flask knows which file is the app.

Write each crontab entry as a **single line**, with any `--circle` flag **inside** the quoted command. A line
break (for example after `cd`) or a flag outside the quotes makes the entry fail or ignore the flag.

### Worked example (production app node)

The repo root and `app.py` are in `/var/www/webroot/ROOT`, the app's Python is `/opt/jelastic-python314/bin/python3`, and logs go to `/var/www/webroot/logs` (outside the
web root, must exist and be writable by `apache`; create it with `mkdir -p /var/www/webroot/logs`). The
complete crontab entry, run at the top of every hour:

```
0 * * * * /bin/bash -lc 'cd /var/www/webroot/ROOT && FLASK_APP=app.py SCHEDULER_LOG_FILE=/var/www/webroot/logs/scheduler.log /opt/jelastic-python314/bin/python3 -m flask tick-scheduled-emails'
```

Before installing it, run this once by hand as `apache`. It sends nothing (no circle has that slug) and should
print a JSON summary of zeros:

```
/bin/bash -lc 'cd /var/www/webroot/ROOT && FLASK_APP=app.py SCHEDULER_LOG_FILE=/var/www/webroot/logs/scheduler.log /opt/jelastic-python314/bin/python3 -m flask tick-scheduled-emails --circle no-such-circle'
```

Prerequisites: the code is pulled and migration `0012` has been run (without it the command fails on the missing
tables). After installing, check `scheduler.log` a little after the first full hour for a "Tick complete" line.
Nothing sends unless a circle is inside its email season.

Each tick, for every row in `circle_email_schedules`:

1. Work out that row's most recent expected occurrence (in the circle's timezone).
2. Skip it if the row was created after that occurrence, if the occurrence was outside the circle's season,
   or if any attempt (success *or* failure) is already logged for it.
3. If it is within 3 hours of the occurrence, run it. If it is older than that and was never attempted,
   log a failure ("did not run within the 3h retry window") instead of running it late.

A slot that has never had any attempt logged is not reported as missed (there is no evidence the scheduler was
running for it yet - for example, the migration created it hours before cron was first installed). It runs
normally once an occurrence falls within the 3-hour window, and from then on missed occurrences are reported.

So a missed tick (cron or the app briefly down) is caught up automatically within 3 hours. A run that was
attempted and **failed is never retried automatically** - a retry after a partial send could email leaders twice.

Changing a circle's send times, adding a circle, or changing a count date never requires touching cron.

## Cron environment

Cron starts jobs with almost no environment (`HOME`, `PATH=/usr/bin:/bin` and a few basics), **without** the
variables FullHost sets for the app (`DATABASE_URL`, `SECRET_KEY`, `SMTP2GO_*`, ...). Interactive and login
shells on the app node do get them, so the cron entry runs the command through a login shell
(`/bin/bash -lc '...'`). Because cron's `PATH` is so short, use the absolute path to the app's Python
(`python3 -m flask`, see above) in the entry.

Verified on the app node (2026-09-28): a cron entry running `/bin/bash -lc 'printenv | grep -c "^SMTP2GO_USERNAME="'`
printed `1`, while plain `printenv` from cron showed none of the app variables.

The command refuses to run (exit 1, message in the log) if `DATABASE_URL` is still missing, so a broken
environment shows up as an error rather than as silently unsent email. To re-check what cron sees, use a
temporary entry, and delete both the entry **and its output file** afterwards if it lists variable values:

```
* * * * * /bin/bash -lc 'printenv | grep -c "^SMTP2GO_USERNAME="' > /var/www/webroot/logs/cron_env_check.txt 2>&1
```

## Logging and exit status

- One JSON summary line per run goes to stdout, e.g.
  `{"attempted": 1, "succeeded": 1, "failed": 0, "expired": 0, "notified": false, "skipped_locked": false}`
- If `SCHEDULER_LOG_FILE` is set (suggested: `/var/www/webroot/logs/scheduler.log`, which is outside the
  web root `/var/www/webroot/ROOT`), scheduler logging also goes to that file, rotated at about 1 MB with 5
  backups. No logrotate configuration is needed. Set it in the cron entry:
  `0 * * * * /bin/bash -lc 'cd <app directory> && SCHEDULER_LOG_FILE=/var/www/webroot/logs/scheduler.log <path to python3> -m flask tick-scheduled-emails'`
  (the variable must come after the `cd ... &&`, or it applies to `cd` only), or set it as an app-node variable.
- Exit status is 1 if any job failed or missed its window, or the tick crashed; otherwise 0.
- Two ticks never run at once: a Postgres advisory lock makes a second one exit immediately with
  `"skipped_locked": true`. This also keeps things safe if the app is ever scaled to more than one instance.

Run by hand for one circle (this sends real email if anything is due): `/opt/jelastic-python314/bin/python3 -m flask tick-scheduled-emails --circle vancouver` (from `/var/www/webroot/ROOT`, with `FLASK_APP=app.py` set)

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
