# Circle Admin Guide
<!-- Restructured by Claude AI on 2026-10-18 -->

This guide is for the people who organize a bird count and run its registration. It is organized
around what you do during a count season, with the one-time setup tasks near the end.

You don't need any technical background. If you can fill in a web form and upload a file,
you can do everything here.

*A note on accuracy: much of this project's code and documentation was written with the help of an AI
assistant. This guide was written from the screens and behaviour of the site in 2026, but documents
tend to get out of date. If something here doesn't match what you see on the site, please let the
server administrator know.*

## Contents

- [The basics](#the-basics)
- [Signing in](#signing-in)
- [A count season at a glance](#a-count-season-at-a-glance)
- [Running the count](#running-the-count)
  - [The dashboard and your daily check](#the-dashboard-and-your-daily-check)
  - [Assigning people who are waiting](#assigning-people-who-are-waiting)
  - [Finding and changing a participant](#finding-and-changing-a-participant)
  - [Area leaders](#area-leaders)
  - [Opening and closing areas](#opening-and-closing-areas)
  - [Registration opening and closing](#registration-opening-and-closing)
  - [Exporting your data](#exporting-your-data)
  - [Past years](#past-years)
- [Telling people about the site](#telling-people-about-the-site)
  - [What the system emails for you](#what-the-system-emails-for-you)
  - [Sample announcement: area leaders](#sample-announcement-area-leaders)
  - [Sample announcement: participants](#sample-announcement-participants)
- [Setting up your circle](#setting-up-your-circle)
  - [First-time checklist](#first-time-checklist)
  - [Circle Settings](#circle-settings)
  - [Areas and the map](#areas-and-the-map)
  - [Customizing the emails](#customizing-the-emails)
  - [Changing when emails are sent](#changing-when-emails-are-sent)
- [Troubleshooting](#troubleshooting)
- [What only the server administrator can do](#what-only-the-server-administrator-can-do)

## The basics

The birdcount.ca website was designed to support many bird counts. It was created for the
Vancouver Christmas Bird Count, so it uses CBC terminology and refers to a count area as a
"circle", even though the geographic area of your count doesn't need to be remotely circular.

Each circle has its own web address, and everything you see and change as an administrator applies to
**your circle only**. You can't see or change another circle's settings or participants.

**Your circle's address** looks like `https://yourcircle.cbc.birdcount.ca` (for a Christmas Bird
Count) or `https://yourcircle.birdcount.ca` (for other counts). Add `/bigbird` to the end to reach
the admin pages, for example `https://yourcircle.cbc.birdcount.ca/bigbird`. Bookmark it.

**Who does what**

| Role | What they can do |
|---|---|
| **Participant** | Registers on the public page. Needs no account and no guide. The emails they receive tell them what to expect. |
| **Area leader** | Sees their own team. See the [Leader Guide](LEADER_GUIDE.md). |
| **Circle admin** (you) | Everything in this guide, for your circle. |
| **Server administrator** | Creates circles, adds or removes circle admins, and looks after the server itself. See the [Super-Admin Guide](SUPER_ADMIN_GUIDE.md). |

## Signing in

There are no passwords. You sign in with a one-time link sent to your email.

1. Go to your circle's admin address (see above). If you aren't signed in, you'll be taken to the
   login page.
2. Type your email address and click **Send login link**.
3. Open the email and click the link. It stops working after **15 minutes** and can only be used once.
4. On the page that opens, click **Continue signing in**.

Some things to know:

- Use the email address your server administrator has registered as a circle admin. If you
  use a different address, no email will arrive, and the page won't tell you why (this is on purpose,
  so strangers can't find out who is an admin).
- If the link email doesn't arrive, check your spam or junk folder, then try again.
- Some workplace email systems open every link in an email to scan it for viruses, which can use up
  the link before you get to it. If your link says it's expired the moment you click it, request a
  fresh one and click it straight away. If it keeps happening, tell the server administrator.
- Click **Logout** (top right) when you finish, especially on a shared computer.

## A count season at a glance

| When                           | What you do                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
|--------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Before registration opens**  | Do the [first-time checklist](#first-time-checklist) (or, in later years, check it over): set the count date, review areas and email wording, make sure each area has a leader. Tell your leaders the site is coming ([sample](#sample-announcement-area-leaders)).                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **Registration opens**         | Announce it to past participants and your members ([sample](#sample-announcement-participants)). The system starts sending its automatic emails.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **While registration is open** | You will receive a daily email listing unassigned [participants](#assigning-people-who-are-waiting) and [area leaders](#area-leaders).  Once you assign a leader to an area, they can view their leader dashboard and with get regular email updates about changes to their team.  For this reason, it's good to assign area leaders early in the count season.  Some participants will register "Where I'm needed most".  You should assign these unassigned participants to an area in plenty of time for their area leader to contact them with details about the count.  If an area attracts too many participants, you can [close it to new registrations](#opening-and-closing-areas). |
| **Registration closes**        | The public form closes on its own shortly before the count (by default 1 day before). You can still add and move people on the admin pages.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **Count day**                  | The automatic emails stop after the count date.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **Afterwards**                 | [Export](#exporting-your-data) what you need. Next year, enter the new count date and the cycle starts again.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |

## Running the count

### The dashboard and your daily check

The dashboard (`/bigbird`) is your home page. It shows:

- **Registration Status**: open or closed, and how long until it closes.
- Counts of **participants**, **assigned**, **unassigned**, and **areas without leaders**.
- Buttons for the most common tasks: **View All Participants**, **Manage Unassigned**, **Manage
  Leaders**, **Recent Registrations**, **Open/Close Areas** and **Export CSV**. The same pages are in the
  menu along the top.
- The latest registrations, a warning if anyone is waiting for an area, and a list of areas that
  still need a leader.

The system also emails circle admins a daily **admin digest** when people are still waiting to be assigned to an
area.
A good daily routine while registration is open takes a couple of minutes:

1. Review your daily admin digest email or look at the dashboard to see the current status.
2. If participants are waiting, [assign them](#assigning-people-who-are-waiting).
3. If areas need leaders, see [Area leaders](#area-leaders).
4. Glance at **Recent Registrations** to see who has signed up lately.



At the top of the dashboard is a **year selector**, described under [Past years](#past-years).

### Assigning people who are waiting

Most participants pick an area when they register and are placed in it automatically. People who chose
"wherever I'm needed most" wait for you to give them an area. Click **Manage Unassigned**:

1. The top of the page shows how many people each area has so far, to help you balance the teams.
2. For each waiting person, pick an area and click **Assign**.

Things worth considering when you choose an area: the person's skill level, whether they have
binoculars or a scope, and whether they've offered to lead.

Assigning someone doesn't send them an email by itself. Their area leader will hear about the new
team member in the next team update, but you may want to tell the person yourself, using the email
address shown for them.

Participants who asked for an area they couldn't be placed in will have been told in their confirmation
email that someone will be in touch. You are that someone: use their contact details on the
participants page, discuss options, then [move them](#finding-and-changing-a-participant).

Sometimes it's appropriate to wait before assigning a participant to an area, e.g. you may want to wait until closer
to the count date so you can assess which areas need more participants.  It might be a good idea to email the
participant to let them know why you're waiting, so they don't feel neglected.  Be sure to assign all participants
in time to let the area leader send them details about the count day.

### Finding and changing a participant

**View All Participants** lists everyone registered this year, grouped by area, with a "Jump to Area"
menu at the top. Each area heading shows how many people are in it, split into field counters and
feeder counters (people counting birds at home). Withdrawn people are shown separately in yellow.

Each row shows the person's contact details, skill level, experience, equipment (binoculars, scope),
notes, and whether they're interested in leading or scribing. Use the buttons on the right:

- **Pencil (edit)**: change any of their details. Click **Save** or **Cancel**.
- **Reassign**: move them to another area. If they are a leader, you'll be asked whether they
  should stay a leader in the new area or become an ordinary team member.
- **Withdraw**: mark them as no longer taking part, with an optional reason. Their record is kept,
  their row turns yellow, and they receive the withdrawal confirmation email. You can undo this with
  **Reactivate**.
- **Trash can (delete)**: permanently removes the record, with an optional reason. **This can't be
  undone.** If the person was a leader, that's removed too. Prefer **Withdraw** unless the record
  should really be gone (for example, a duplicate).

Skill levels are shown as **Novice, Beginner, Intermediate** and **Expert**.

**Recent Registrations** shows who registered recently. Choose a preset range (7, 14, 30, 60 or 90
days) or pick a date.

### Area leaders

Click **Manage Leaders** (or **Leaders** in the top menu) to see and manage who leads each area. Every
area can have more than one leader, but a person can lead only one area.

- The **map** shows areas that **need a leader in red** and areas that **have one in green**. Hover
  over a green area to see the leader's name.
- **Current Area Leaders** lists each leader with their area and contact details. Use the pencil to
  edit (area, name, email, phones) and the trash can to remove leader status. Removing leader status
  doesn't remove the person from the count; they remain registered as an ordinary team member.
- **Potential Leaders** lists registered participants who said they'd be interested in leading. Pick
  an area and click **Assign** to make one of them a leader.
- **Add New Area Leader**: fill in the form (name, email, cell phone and area are required) to add
  someone directly as a leader, for example a returning leader who hasn't registered yet.
- **Areas Needing Leaders** lists the areas that still have no leader.

Area leaders sign in with their own email address (the same email link as you) and see only their
own team. Making someone a leader is what gives them that access. Their team updates go to the email
address you have on file, so check it is right.

### Opening and closing areas

By default, every area accepts public sign-ups. You may close an area to the public when it has enough
people, or when it's one you would rather select the team yourself: e.g. an airport or other area with 
restricted access or an area counted from a boat with limited capacity.

Click **Open/Close Areas**. You'll see a map and a table:

- **Open**: participants can choose this area when they register.
- **Admin Only**: participants can't choose it. Only an admin can assign people to it.

Each area has an **Open** and an **Admin Only** button. Click the one you want. The change takes
effect straight away, and you can reverse it at any time. People already in the area stay there.

If a leader asks you to close their area, this is how.

### Registration opening and closing

Public registration opens and closes by itself, based on the count date and two settings in
[Circle Settings](#circle-settings): how many months before the count it opens, and how many days
before the count it closes.

- Until a count date is set for the current year, the public site shows "TBD" and registration
  stays **closed**. Each year, enter the new date (or several years' dates in advance).
- When the period ends, the public form closes on its own. You can still work with existing
  registrations, and add or move people, on the admin pages.
- If you need registration to stay open longer (or open earlier), change the closing or opening
  setting in Circle Settings.

### Exporting your data

Click **Export CSV** on the dashboard or the participants page to download a spreadsheet of the
participants for the year you're viewing. It opens in Excel, Google Sheets or similar. It includes
contact details, area, skill level, experience, equipment, leadership and scribe interest, notes and
the registration time, sorted by area.

**Please treat these files as private.** They contain people's personal contact details. Store them
somewhere safe, share them only with the people who need them, and delete copies you no longer need.

### Past years

The **year selector** at the top of the dashboard and most lists switches between this year and past
years for which your circle has records.

Past years are **read-only**. You can look, and you can export, but the edit, reassign, withdraw and
delete buttons are hidden, and a coloured background reminds you that you're looking at history.
They're useful for finding returning participants and for seeing how teams looked in earlier years.

A new year starts automatically: the first registration of a new year creates that year's records.

## Telling people about the site

### What the system emails for you

The system does a lot of the communicating for you. Knowing what it sends helps you decide what you
still need to write yourself.

| Email | Who gets it | When |
|---|---|---|
| **Registration confirmation** | A participant | Right after they register. Says which area they're in, or that someone will be in touch if they couldn't get their first choice or are waiting for an area. |
| **Withdrawal confirmation** | A participant | After you withdraw them. |
| **Team update** | Area leaders | When someone joins or leaves their team. By default checked twice a day (7:00 am and 6:00 pm); nothing is sent if nothing changed. |
| **Weekly summary** | Area leaders | Once a week (by default Friday at 11:00 pm) with the full team roster. |
| **Admin digest** | Circle admins | By default daily at 6:00 pm, only if people are still waiting for an area. |

These go out only from the day registration opens through the count date. You can change the wording
([Customizing the emails](#customizing-the-emails)) and the send times
([Changing when emails are sent](#changing-when-emails-are-sent)).

The system **doesn't** send a general announcement that registration is open, and it doesn't send
count-day instructions. You write and send those yourself, the way you always have, from your own
email. The samples below are a starting point. They are patterned on announcements the Vancouver
organizers send; adapt them freely.

Tips for announcements:

- Send **leaders** a heads-up a day or two before you tell everyone, so they aren't surprised.
- Put the registration link where people already look: your club's count page, newsletter and social
  media, as well as the email.
- Use BCC when you write to a list of people, so you don't expose their addresses.
- Don't paste participant lists into emails. Leaders see their own team on the leader page.

### Sample announcement: area leaders

Replace everything in [square brackets]. Delete any paragraph that doesn't apply to your count.

> **Subject:** [Year] [Count name]: Registration site opens [today / date]!
>
> Thank you for agreeing to lead an area for the [Year] [Count name] on [count date].
>
> This is a heads-up that we're launching the registration site on [date], to all counters by email
> and in [newsletter name]. You can get to it by:
>
> - clicking Register on the count page of our website: [link to your count page], or
> - using this direct link: [your circle's address, for example https://yourcircle.cbc.birdcount.ca/]
>
> **Some area leaders are already registered.**
>
> The registration page shows which areas still need leaders.  Please help us find leaders for the open areas.
> Participants can indicate interest in leading an area when they register, after which we can assign them to an area.
> 
> The registration system makes it easier for you as a leader to keep track of who wants to count in your area,
> and lets the organizers send important information about count day to everyone who takes part.
>
> **What's new this year** *(include only what has changed)*
> - [The link has changed. Please use this year's link: …]
> - [We've changed the wording of the registration confirmation emails. People are still
>   automatically added to the area they chose, but if we can't place someone in their preferred area,
>   the email says someone will be in touch to discuss options.]
> - We can close your area to new sign-ups at any time. Just let us know.
>
> **How it works**
>
> - Team members sign up at [your circle's address]. People who register for your area, as field
>   counters or feeder counters, are automatically added to your team.
> - Twice a day the system checks for changes and emails you if your team roster has changed. The
>   idea is to tell you about new team members promptly, so you can contact them while they're still
>   excited. You won't get an email if nothing has changed.
> - Every [Friday around 11 pm] you'll get a weekly email listing your whole team and the changes over
>   the past week.
> - Your leader page is at [your circle's address]/leader. It shows your team, from this year and past
>   years, and lets you download the roster as a CSV file. The first time you visit, you'll be asked
>   for your email address, and the site emails you a link to sign in. (There are no passwords.) The
>   roster contains personal information, which is why a secure link is needed.
> - For more help, see the Area Leader Guide: [link to your copy of the Leader Guide].
>
> [Our reg site can only show rosters from [first year] onward.]
>
> Please email [your count contact address] with any questions, concerns or suggestions.
>
> Thanks everyone!
> [Your name]
> [Role], [Count name]
> [Count date]

### Sample announcement: participants

> **Subject:** Registration open: [Count name] [Year]
>
> Registration is now open for the [Nth] [Count name] on [day, count date]. [One or two sentences
> about the count: its history, what it contributes to science, what a typical day is like.]
>
> Please register to join us for a fun day of community science: [your circle's address]
>
> This year's count is being coordinated by [names]. You can contact us at [your count contact
> address].
>
> Many of you count in the same area with the same team year after year. If that's you, wonderful!
> Please choose the area (and leader) you usually count with.
>
> If you're an intermediate or expert birder and don't have a strong preference, please consider
> signing up for "Wherever I'm needed most". Some areas end up short of counters, and we'd love the
> flexibility to place you where you're most needed.
>
> Thanks to everyone for volunteering. We look forward to birding with you on count day.
>
> [Your name]
>
> P.S. This email is going to everyone who registered for the [previous years] counts. Apologies if
> you've already asked to be removed from our list. From here on we'll only email people who register
> for this year's count.

Other messages worth sending yourself: a reminder as registration closes, a note to anyone still
unassigned, and your count-day instructions (meeting times, compilation details, safety). If an
area is still short of counters, a targeted message to past participants works better than a general
reminder.

## Setting up your circle

You do most of this once, when your circle is created. After that, a yearly review is usually all
that's needed: a new count date, a look at the areas and a quick read of the email wording.

### First-time checklist

The server administrator creates your circle and adds you as a circle admin. After that, you do the
rest. Work through these in order:

1. **[Circle Settings](#circle-settings)**: fill in your organization's name, contact addresses and
   this year's count date.
2. **Logo**: upload your organization's logo (on the same Circle Settings page).
3. **[Areas](#areas-and-the-map)**: upload the KML file of your count area boundaries.
4. **[Area details](#editing-an-areas-labels)**: tidy up each area's name and description if needed.
5. **[Emails](#customizing-the-emails)**: read each email and change the wording where you'd like.
   Use **Preview** to see the result.
6. **[Open/close areas](#opening-and-closing-areas)**: mark any area that shouldn't take public
   sign-ups (for example, an area you fill by hand).
7. **[Leaders](#area-leaders)**: add the area leaders you already know about.
8. **Try it out**: open your circle's public page and check that the map, the wording and the areas
   look right. Registration only opens once a count date is set.

### Circle Settings

Click **Circle** in the top menu, then **Circle Settings**. Change what you need and click **Save
Changes** at the bottom.

| Setting | What it's for |
|---|---|
| **Slug** | Your circle's short name in the web address. Fixed when the circle is created. |
| **Circle name** | The short name, such as "Vancouver". |
| **Managing organization** | The club or society running the count, such as "Nature Vancouver". |
| **Organization website** and **contact email** | Shown to the public and used in emails. |
| **Count coordinator contact email** | The address participants are told to write to with questions. Use one that someone reads. |
| **Count event name** | The full name shown on the site and in emails, such as "Vancouver Christmas Bird Count". |
| **Count info URL** | A link to a page with more about your count. Optional. |
| **Display timezone** | The timezone used when the site shows dates and times, and for email send times. Start typing a city or region and pick from the list. |
| **Registration opens (months before count)** | How far ahead of the count date public registration opens. |
| **Registration closes (days before count)** | How many days before the count date public registration stops. |
| **Count dates** | One date per year (two dates in the same year can't be saved). Use **+ Add another date** to enter future years as soon as they are known. |
| **Experience field label** | The wording for the "experience" question on the registration form (for example "CBC Experience"). |
| **Feeder counter option label** | The wording of the option for people who count birds at home. |
| **Notes field placeholder example** | Example text shown inside the "notes" box on the registration form. |
| **Christmas Bird Count checkbox** | Leave it ticked for a Christmas Bird Count. Untick it for another kind of count, such as a spring count. This affects the circle's web address and where it's listed. |

**The count date matters.** Until a date is set for the current year, the public site shows "TBD"
and registration stays **closed**. Registration then opens and closes automatically according to the
two settings above, and the automatic emails run from the day it opens until the count date. The
dashboard's **Registration Status** box shows whether registration is open right now.

**Settings you can see but not change** (they show a grey "Super-admin only" tag; ask the server
administrator): **From email** (the address the system sends mail from), **Test-mode recipient**,
and **Map latitude/longitude**. The map position is filled in for you when you import your areas.

**Logo.** Under the settings form, choose a PNG or JPEG file (up to 2 MB) and click **Upload logo**.
To swap it, upload a new one. **Remove current logo** puts back the plain placeholder.

### Areas and the map

Your count circle is divided into **areas**. Each area has a short **code** (like `A`, `B` or `12`),
a name, an optional description, and a shape on the map. Participants pick an area from the map or a
list when they register.

The areas page is at `https://yourcircle.cbc.birdcount.ca/bigbird/circles/yourcircle/areas`, using
your own circle's address and slug. (There is no menu link for it at the moment, so bookmark it.)

#### Adding or updating areas: import a KML file

The only way to create areas, or to change an area's map shape, is to import a **KML file**. This is
the file you get by exporting from a Google My Maps map.

**Preparing the map in Google My Maps**

1. Draw one shape (polygon) for each count area.
2. **Name each shape starting with its code**, in one of these styles:
   - `Area A: Stanley Park`
   - `Area 12 - North Shore`
   - `12 - North Shore`
   - `A: Stanley Park`
3. Put any description you want shown to leaders and participants in the shape's description box.
4. Shapes whose code contains a dash, such as `B-1`, are treated as **sub-areas** and skipped. Only
   the main areas are imported.
5. Export the map as **KML** (in Google My Maps, use the map's three-dot menu, then *Export to
   KML/KMZ*, and untick "Export to a .KMZ file" so you get a plain `.kml` file).

**Importing**

1. Open your circle's areas page.
2. Under **Import boundaries from KML**, choose your `.kml` file (up to 5 MB) and click **Import KML**.
3. A green message tells you how many areas were imported. If something is wrong, a red message says
   what, and **nothing is changed**.

What an import does:

- An area code that's already there is **updated**: its name, description and shape are replaced.
  Its difficulty and terrain labels are left alone.
- An area code that's new is **created**.
- An area that's not mentioned in the file is **left as it is**. Importing never deletes areas.
- Your circle's map position is recalculated from the shapes.
- Any decorative boundary lines in the file replace the ones from the last import.

You can import as many times as you like, for example to fix a boundary.

#### Editing an area's labels

On the areas page, click the **pencil** at the end of a row to edit that area's **name**,
**description**, **difficulty** and **terrain**. Click the **tick** to save or the **cross** to
cancel. Changes save straight away, with no page reload.

The **code** can't be edited. Participants and leaders are linked to areas by code, so changing one
would quietly disconnect them. If a code is wrong, fix it in your map and re-import; ask the server
administrator for help if people are already assigned to the wrong code.

### Customizing the emails

The system sends several emails on your circle's behalf. You can change the wording of the important
parts, so the emails sound like your organization. Click **Circle** in the top menu, then **Email
Content**.

There is one tab for each email:

| Tab | Who gets it |
|---|---|
| **Registration confirmation** | A participant, right after they register. |
| **Withdrawal confirmation** | A participant, after they're withdrawn. |
| **Team update** | An area leader, when their team changes. |
| **Weekly summary** | An area leader, once a week. |
| **Admin digest** | The circle's admins, listing people still waiting for an area. |

The registration confirmation is the one participants see first, so it's the most worth reading
closely. It sets expectations about getting their preferred area.

**To change wording**

1. Pick a tab. Each email is split into small parts (subject, welcome message, what happens next,
   closing message and so on), each with its own box.
2. Edit the text in any box. A grey **Inherited default** tag means you haven't changed that box; it
   is using the standard wording. Once you save your own text, the tag goes away.
3. Click **Save** at the bottom of the tab. Your changes only save for the tab you're on.
4. Click **Preview** at the top of the tab to see the finished email in a new window. It uses made-up
   sample names, and **sends nothing**. The registration confirmation has a second preview for
   participants who have not been assigned to an area yet.

**Placeholders.** Under each box you'll see a list such as `$count_event_name`. These are blanks the
system fills in for each email. Type them exactly as shown. For example,
`Welcome to the $count_event_name!` becomes "Welcome to the Vancouver Christmas Bird Count!". Only
the placeholders listed under a box work in that box. If you use one that isn't listed, the save is
refused and nothing is saved, with a message saying which one was the problem.

**To go back to the standard wording**, click **Reset "..." to default** under that box.

Tips:

- Each box has a length limit. The box stops you at the limit.
- Blank lines in the longer boxes are kept as paragraph breaks.
- Plain text only; formatting like bold or links won't work.
- After changing wording, use **Preview** before the emails go out for real.

### Changing when emails are sent

The defaults suit most circles, so you only need this if you want emails at different times. Click
**Circle** in the top menu, then **Email Schedule**.

The page shows when your emails' season starts (the day registration opens) and ends (the count date),
and a table of **send times** for the three scheduled emails (leader team update, leader weekly summary
and the admin digest). Each row has an email, a day (every day, or one weekday) and an hour, in your
circle's timezone.

- **Remove** deletes a send time. **Add a send time** adds one. Each email can have up to four.
- If an email has **no** send times, it isn't sent.
- Emails are only sent during the season, whatever the schedule says. If there is no upcoming count
  date, nothing is sent, and the page says so.
- The page also lists recent runs, so you can check that an email went out.

## Troubleshooting

**I never got my login email.** Check your spam folder. Make sure you used the address that's
registered as an admin for this circle. Wait a minute and try again. If it still doesn't come,
contact the server administrator.

**My login link says it's expired or already used.** Links last 15 minutes and work once. Request a
new one and click it straight away. Some email systems open links in advance to scan them; if that
keeps happening, tell the server administrator.

**"You do not have permission to manage this circle."** You are signed in, but you aren't an admin
for this particular circle. Check you're on your circle's own web address.

**People say they can't register.** Check the **Registration Status** box on the dashboard. If it says
closed, check that this year's count date is set under Circle Settings. Also check that the area they
want isn't marked **Admin Only**. If someone says they've already registered, look for them under
**View All Participants**; the site doesn't allow the same person to register twice.

**Someone didn't get their confirmation email.** Ask them to check spam. Confirm the email address is
correct on the participants page (use the pencil to fix a typo).

**A leader isn't getting emails.** Confirm their email address is right on the **Manage Leaders**
page and ask them to check spam. Check [Email Schedule](#changing-when-emails-are-sent): emails only
go out during the season, and only when something has changed. If nobody is getting any emails, tell
the server administrator.

**I can't edit anything.** You may be looking at a past year, which is read-only. Switch the year
selector to the current year.

**I deleted someone by mistake.** Deleting can't be undone. Ask the person to register again, or ask
the server administrator whether there's a backup.

**Something looks wrong or broken.** Tell the server administrator what you were doing and what
you saw (a screenshot helps).

## What only the server administrator can do

Ask the server administrator if you need to:

- **Add or remove a circle admin** for your circle.
- **Change the From email address** the system sends from.
- Change the **map position** of your circle on the overview map.
- Have a **new circle** created, or have a count listed as an **external count** (one whose
  registration happens on another website).
- Fix something in the data that the screens above don't allow (for example, an area code that's
  wrong after people have already been assigned to it).
