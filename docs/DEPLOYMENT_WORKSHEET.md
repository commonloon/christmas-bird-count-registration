# CBC Registration System - Installation Planning Worksheet
<!-- Updated by Claude AI on 2025-10-14 -->

## Purpose

Use this worksheet to plan and document all organization-specific values before starting your installation. Fill in the "My Installation" column, then use these values when configuring your system.

**Tip**: Copy this table to a spreadsheet for easier editing and sharing with your team.

---

## Google Cloud Project

| Generic Name | Example                      | My Installation |
|-------------|------------------------------|-----------------|
| `<YOUR-PROJECT-ID>` | `vancouver-cbc-registration` | |
| Project Name (descriptive) | `Vancouver CBC Registration` | |
| GCP Region | `us-west1` (Oregon) | |

**Notes:**
- Project ID must be globally unique across all Google Cloud
- Use lowercase letters, numbers, and hyphens only
- Cannot be changed after creation
- Configure in `config/cloud.py`: `GCP_PROJECT_ID` and `GCP_LOCATION`

---

## Firestore Databases

| Generic Name | Example | My Installation |
|-------------|---------|-----------------|
| `<TEST-DATABASE>` | `cbc-test` | |
| `<PROD-DATABASE>` | `cbc-register` | |

**Notes:**
- Configure in `config/cloud.py`: `TEST_DATABASE` and `PRODUCTION_DATABASE`
- Test and production databases are completely separate
- Database names must be unique within your Google Cloud project

---

## Cloud Run Services

| Generic Name | Example | My Installation |
|-------------|---------|-----------------|
| `<TEST-SERVICE>` | `cbc-test` | |
| `<PROD-SERVICE>` | `cbc-registration` | |

**Notes:**
- Configure in `config/cloud.py`: `TEST_SERVICE` and `PRODUCTION_SERVICE`
- Service names become subdomains (e.g., `cbc-test.yourclub.org`)
- Service names must be unique within your Google Cloud project

---

## Domain Names

| Generic Name | Example | My Installation |
|-------------|---------|-----------------|
| `<BASE-DOMAIN>` | `naturevancouver.ca` | |
| `<TEST-DOMAIN>` | `cbc-test.naturevancouver.ca` | |
| `<PROD-DOMAIN>` | `cbc-registration.naturevancouver.ca` | |

**Notes:**
- Configure in `config/cloud.py`: `BASE_DOMAIN`
- Deployment URLs are automatically constructed: `https://{SERVICE}.{BASE_DOMAIN}`
- Example: `TEST_SERVICE=cbc-test` + `BASE_DOMAIN=naturevancouver.ca` = `https://cbc-test.naturevancouver.ca`
- You must have DNS control for your base domain
- CNAME records will point to `ghs.googlehosted.com`
- SSL certificates are automatically provisioned (takes up to 24 hours)

---

## Organization Information

| Generic Name | Example | My Installation |
|-------------|---------|-----------------|
| Organization Name | `My Bird Club` | |
| Organization Website | `https://myclub.org` | |
| Organization Contact Email | `info@myclub.org` | |
| Count Contact Email | `cbc@myclub.org` | |
| Count Event Name | `My Club Christmas Bird Count` | |
| Count Info URL | `https://myclub.org/christmas-bird-count` | |

**Notes:**
- Configure in `config/organization.py`
- Used in emails, forms, and public-facing pages

---

## Admin Email Addresses

| Generic Name | Example | My Installation |
|-------------|---------|-----------------|
| Admin Email 1 | `admin@myclub.org` | |
| Admin Email 2 | `coordinator@myclub.org` | |
| Admin Email 3 | | |
| Admin Email 4 | | |
| Test Recipient Email | `test-admin@myclub.org` | |

**Notes:**
- Configure in `config/admins.py`
- Test recipient receives all emails in test mode
- Add as many admin emails as needed

---

## Count Areas

| Generic Name | Example | My Installation |
|-------------|---------|-----------------|
| Area Code Pattern | `A-X` (letters) or `1-24` (numbers) | |
| Number of Areas | `24` | |
| First Area Code | `A` or `1` | |
| Last Area Code | `X` or `24` | |

**Notes:**
- Configure in `config/areas.py`
- Must have matching boundaries in `static/data/area_boundaries.json`
- System supports any naming scheme (letters, numbers, custom codes)

---

## Email Settings

| Generic Name | Example | My Installation |
|-------------|---------|-----------------|
| SMTP Server | `smtp.gmail.com` | |
| SMTP Port | `587` | |
| SMTP Username | `notifications@myclub.org` | |
| Sender Email | `noreply@myclub.org` | |
| Sender Name | `My Club CBC Registration` | |

**Notes:**
- Configure in `config/email_settings.py`
- SMTP password stored in Google Secret Manager (not in config files)
- Currently uses SMTP; Google Cloud Email API integration pending

---

## Timezone and Locale

| Generic Name | Example | My Installation |
|-------------|---------|-----------------|
| Display Timezone | `America/Vancouver` | |
| Default Locale | `en_US` | |

**Notes:**
- Configure in `config/organization.py`
- Used for email timestamps and scheduling
- See [list of timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

---

## OAuth Client

| Generic Name | Example | My Installation |
|-------------|---------|-----------------|
| OAuth Client Type | `Web application` | |
| Application Name | `My Club CBC Registration` | |
| Authorized JavaScript Origins | `https://cbc-test.myclub.org, https://cbc-registration.myclub.org` | |

**Notes:**
- Created in Google Cloud Console
- Credentials stored in Google Secret Manager
- Detailed setup instructions in `OAUTH-SETUP.md`
- Authorized redirect URIs should be **empty** (Google Identity Services uses direct callbacks)

---

## DNS Records (for reference)

| Record Type | Name | Value | TTL |
|------------|------|-------|-----|
| CNAME | `<test-subdomain>` | `ghs.googlehosted.com` | 3600 |
| CNAME | `<prod-subdomain>` | `ghs.googlehosted.com` | 3600 |

**Example:**
| Record Type | Name | Value | TTL |
|------------|------|-------|-----|
| CNAME | `cbc-test` | `ghs.googlehosted.com` | 3600 |
| CNAME | `cbc-registration` | `ghs.googlehosted.com` | 3600 |

---

## Configuration Files Checklist

Use this checklist to ensure all files are updated with your installation values:

- [ ] `config/cloud.py` - GCP project ID, region, databases, services, base domain
- [ ] `config/organization.py` - Organization details, contact emails, timezone
- [ ] `config/admins.py` - Admin email addresses
- [ ] `config/areas.py` - Count area definitions and codes
- [ ] `config/email_settings.py` - SMTP settings (optional)
- [ ] `static/data/area_boundaries.json` - Geographic boundaries for your count circle

**Note:** `deploy.sh` now reads configuration from `config/cloud.py` - no manual edits needed!

---

## Quick Reference: Where to Use These Values

### During Initial Setup (Step-by-Step)

1. **Create Google Cloud Project** → Use `<YOUR-PROJECT-ID>` and Project Name
2. **Set Active Project** → `gcloud config set project <YOUR-PROJECT-ID>`
3. **Update ADC** → `gcloud auth application-default set-quota-project <YOUR-PROJECT-ID>`
4. **Configure Cloud Settings** → Edit `config/cloud.py` with GCP project, region, databases, services, and domain
5. **Configure Organization** → Edit `config/organization.py` with organization details and contact emails
6. **Configure Admins** → Edit `config/admins.py` with admin emails
7. **Create Databases** → Run `python utils/setup_databases.py` (reads from `config/cloud.py`)
8. **Deploy Services** → Run `./deploy.sh` (reads from `config/cloud.py` and `config/organization.py`)
9. **Map Domains** → Use service names and domain from `config/cloud.py`
10. **Update DNS** → Add CNAME records pointing subdomains to `ghs.googlehosted.com`

---

## Notes and Reminders

**Important:**
- All configuration is in `config/` directory - no code changes needed
- `config/cloud.py` is the central location for GCP-specific settings
- `deploy.sh` automatically reads from configuration files
- Deployment URLs are automatically constructed from `SERVICE_*` + `BASE_DOMAIN`
- Test all settings in test environment before deploying to production
- Keep this worksheet for reference during future maintenance

**Security:**
- Never commit OAuth credentials or SMTP passwords to version control
- Use Google Secret Manager for all sensitive values
- Admin emails control who has full system access
- Secret names are standard across installations (project-specific, no conflicts)
