# Super-Admin Guide
<!-- Created by Claude AI on 2026-10-18 -->

This guide is for the people who look after the birdcount.ca registration platform as a whole: they
create count circles, appoint each circle's admins, and keep the scheduled emails running. It covers
the screens a super-admin has beyond those of a circle admin.

It is not a server or deployment guide. For that, see [DEPLOYMENT.md](DEPLOYMENT.md), [SCHEDULER.md](SCHEDULER.md) and
[TLS_CERT_RENEWAL.md](TLS_CERT_RENEWAL.md). The other deployment documents date from before the
move to FullHost and need rewriting.

*A note on accuracy: much of this project's code and documentation was written with the help of an AI
assistant. This guide was written from the screens and code as of October 2026. If something here
doesn't match what you see, trust the site and fix the guide.*

## Contents

- [What a super-admin is](#what-a-super-admin-is)
- [Signing in and getting around](#signing-in-and-getting-around)
- [Creating a circle](#creating-a-circle)
- [Handing a circle over to its admins](#handing-a-circle-over-to-its-admins)
- [Managing circle admins](#managing-circle-admins)
- [Editing a circle](#editing-a-circle)
- [External counts](#external-counts)
- [Email defaults](#email-defaults)
- [The Scheduler page](#the-scheduler-page)
- [Reports from the landing page](#reports-from-the-landing-page)
- [Blocked IP addresses](#blocked-ip-addresses)
- [Things that need a code change or the server](#things-that-need-a-code-change-or-the-server)

## What a super-admin is

| Role | Scope |
|---|---|
| **Super-admin** | Every circle. Creates circles and appoints their admins, and can do anything a circle admin can do in any circle. |
| **Circle admin** | One circle only. Runs the count: see the [Circle Admin Guide](ADMIN_GUIDE.md). |
| **Area leader** | One area of one circle. See the [Leader Guide](LEADER_GUIDE.md). |

Super-admins are not stored in the database. They are the email addresses listed in
`PRODUCTION_ADMIN_EMAILS` in `config/admins.py`, so adding or removing one is a code change that has to
be deployed. Circle admins, by contrast, are managed on screen (see below).

You will normally hand a circle to its organizers and leave them to it. Use your wider access to help
them, not to run their count for them. Everything on a circle's participants page is personal
information about volunteers.

## Signing in and getting around

Sign in the same way as a circle admin, with a one-time emailed link, on any circle's `/bigbird` address
or on the console itself. The **Count Super-Admin** console has three menu items:

- **Circles**: the list of circles, and the buttons for each. This is where most of the work happens.
- **Scheduler**: scheduled-email health across all circles.
- **Email Defaults**: the platform-wide wording for the emails.

To work *inside* a circle (see its dashboard, participants, leaders), go to that circle's own address
plus `/bigbird`, for example `https://vancouver.cbc.birdcount.ca/bigbird`. Your super-admin access works on
every circle. A **Manage Circles** link in the menu takes you back to the console.

The circle list has these buttons per row:

| Button | Opens |
|---|---|
| **Edit** | The circle's settings. |
| **Areas** | The circle's areas and KML import (not shown for external counts). |
| **Admins** | The circle's admin list. |
| **Email Content** | The circle's email wording (not shown for external counts). |
| **Schedule** | The circle's email send times (not shown for external counts). |

## Creating a circle

Click **Add Circle** on the Circles page and fill in the form. Most fields are described in the
[Circle Admin Guide](ADMIN_GUIDE.md#circle-settings). The ones that are yours alone:

**Slug.** The circle's short name, used as its web address:
`slug.cbc.birdcount.ca` for a Christmas Bird Count, `slug.birdcount.ca` otherwise. It must be
lowercase letters, digits and hyphens, no more than 50 characters, and unique across the whole site. The
form suggests one from the circle name and checks availability as you type. **It can't be changed after
the circle is created**, so choose carefully. A few names are reserved.

**From email.** The address the circle's emails are sent from. Its domain must be on the allowed list
(`ALLOWED_FROM_EMAIL_DOMAINS` in `config/email_settings.py`). To allow a new domain you need a code
change, and the domain must also be set up to send mail properly (SMTP2GO) or messages will fail or be
marked as spam.

**Test-mode recipient.** Where email goes when the site is running in test mode. Leave it as is for a
normal circle.

**Latitude / longitude.** Where the circle's pin appears on the landing-page map. Type coordinates or
click the map. For a hosted circle, importing the areas later recalculates the position from their
shapes. For an external count you must set it yourself.

**Count dates.** One date per year, any year. Registration doesn't open until a date is set for the
current year, and the circle admin can change these later.

**Managing organization** is required for a hosted circle, optional for an external one.

When you save, the circle is created with the default scheduled-email times (leader team updates at 7:00
am and 6:00 pm, weekly summary Friday 11:00 pm, admin digest 6:00 pm), which the circle's admins can edit.

**No DNS or certificate work is needed for a new circle.** The wildcard DNS records and certificate
already cover every `*.cbc.birdcount.ca` and `*.birdcount.ca` address, so the new address works as soon
as the circle exists. If a circle's address shows a certificate warning, see
[TLS_CERT_RENEWAL.md](TLS_CERT_RENEWAL.md).

## Handing a circle over to its admins

A new circle is empty, and nobody can run it until it has an admin.

1. Click **Admins** on the circle's row and add the organizer's email address (see below).
2. Tell the organizer their circle's address (`…/bigbird`), and send them the [Circle Admin
   Guide](ADMIN_GUIDE.md). Its [first-time checklist](ADMIN_GUIDE.md#first-time-checklist) takes them
   through the rest: settings, logo, areas, email wording.
3. Make sure they can sign in. They must use exactly the address you entered.

Things only you can do for them, if they ask: change the From address, set the map position, and fix
data the screens don't allow.

## Managing circle admins

Click **Admins** on the circle's row. To add someone, type their email address and click **Add**. To
remove someone, click **Remove** beside their address. Both take effect immediately.

- A circle can have as many admins as it needs. Two or more is wise, so the count isn't stranded when
  someone is away.
- Matching is by email address. A person who uses two addresses needs both listed.
- Removing an admin doesn't delete anything they did.
- A circle with **no** admins is reported to the super-admins in a daily email (about 8:00 am Pacific
  time), so a forgotten circle gets noticed. Nobody receives that circle's admin digest in the meantime.

Circle admins can't add other admins. For now every change goes through you.

## Editing a circle

Click **Edit** on the circle's row. As a super-admin you see every field enabled. A circle admin sees
**From email**, **Test-mode recipient**, **Map latitude/longitude** and the external-count fields greyed
out with a "Super-admin only" tag, and the server ignores them even if they try to submit changes.

Some practical notes:

- Changing the **count dates** replaces the whole list. A stored value that isn't a real date (such as
  "TBD") is dropped on save.
- Changing the **timezone** changes when scheduled emails go out, since send times are in the circle's own
  timezone.
- To fix a wrong area code after people are already assigned to it, you need a data fix. See [the last
  section](#things-that-need-a-code-change-or-the-server).

## External counts

Some counts take registration somewhere else (for example on Birds Canada's registration site) but
still want to appear on the birdcount.ca overview map and table. You can set a circle up as an **external
count**. This is a super-admin-only setting, partly because it controls where visitors are sent.

To make one, tick **External count** on the create or edit form (click **What's this?** beside it for a
short explanation). Editing an existing circle asks you to confirm when you switch the box.

For an external count:

- The count is listed on the landing page with its name, location, next count date and contact
  details. Its map pin, table row and info box link to the **web address** entered on the form (a
  registration site or a plain information page) and open in a new tab. If you leave the address
  blank, the count is listed without links. It must start with `http://` or `https://`.
- Anyone who visits the circle's own address on this site is sent to that web address (or to the
  landing page if there is none). Registration, leader and area pages are not used.
- Admin pages (`/bigbird`) and sign-in still work, so the circle's admins can sign in and look at
  existing data. The Areas, Email Content and Schedule buttons are hidden in the circle list.
- The form shows only the fields that apply: no registration emails, event name or registration
  window. A **map location is required**, set by typing coordinates or clicking the map. A **contact
  email** and **circle name** are required too.
- A **managing organization** is optional (a count may be run by an individual) but encouraged, since it
  helps visitors trust the listing. The form nudges you to enter one.
- The landing page shows the next upcoming count date, or the latest past one marked "(past)", or
  "TBA".

Switching the box off again restores the circle's earlier hosted-here settings, so nothing is lost.

## Email defaults

**Email Defaults** (in the console menu) edits the platform-wide wording of the emails: registration
confirmation, withdrawal confirmation, team update, weekly summary and admin digest. These are what every
circle uses until its admins write their own wording for a given part of an email. Circle admins see
these as the grey "Inherited default" text.

It works like the circle admin's [Email Content page](ADMIN_GUIDE.md#customizing-the-emails), with the
same tabs and placeholders, except that it applies to all circles. Changing a default changes the emails
of every circle that hasn't overridden that part, **starting with the next email sent**. Write defaults
that suit any circle: don't mention one organization or event by name; use placeholders such as
`$count_event_name`.

## The Scheduler page

**Scheduler** in the console menu shows whether the scheduled emails are healthy.

- **Failure alerts**: the "From" address used when the system emails you about a failed or missed job. It
  must be on an allowed domain.
- **Circles**: each circle's timezone and email season (active, not yet, or no upcoming count date), with
  a link to its send times.
- **Recent runs** across every circle, including failures.
- **Manual run** (collapsed): a recovery tool for after a failure has been fixed. You must type the
  circle's slug to confirm, it only works during that circle's season, and it only sends what has
  changed since each team's last email, so running it straight after a normal run sends nothing new.

When a job fails or misses its 3-hour window, you get one summary email listing every failure, and the
affected circle's admins get a short note for their own circle.

How the hourly job itself is installed and run on the server is in [SCHEDULER.md](SCHEDULER.md).

## Reports from the landing page

The landing page footer has a **Report a problem** button for visitors, mainly for stale or wrong
listings. Reports are emailed to **all super-admins**, not to the circle's contact, because the contact
details may be the thing that's wrong. If the report is about a circle's listing, you can fix it on the
circle's Edit page.

## Blocked IP addresses

The site automatically blocks addresses that behave like scanners or bots (for example, repeatedly
requesting pages that don't exist, or touching a trap page). There is a page to review them at
`/bigbird/blocked-ips` on any circle's address, but **no menu link** points to it, so bookmark it if you
need it.

It shows how many blocks are active and why, and lets you **unblock** an address (for a real person who
was blocked by mistake) or **clean up expired blocks**. Blocks expire by themselves.

## Things that need a code change or the server

These can't be done on screen:

- **Add or remove a super-admin** (`config/admins.py`).
- **Allow a new From-address domain** (`config/email_settings.py`).
- **Change the slug of an existing circle**.
- **Delete a circle**. There is no delete button.
- **Fix data the screens don't allow**, such as changing an area's code after people are assigned to it.
- **Run migrations or restart the server** after a release. Whoever deploys does this themselves; nothing
  on these screens does it.
- **Hourly scheduler job and certificate renewal**: see [SCHEDULER.md](SCHEDULER.md) and
  [TLS_CERT_RENEWAL.md](TLS_CERT_RENEWAL.md).
