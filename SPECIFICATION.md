# Vancouver Christmas Bird Count Registration App - Complete Specification

## Overview
Web application for Nature Vancouver's annual Christmas Bird Count registration with interactive map-based area selection. Users can register by clicking count areas on a map or using a dropdown menu, with automatic assignment to areas needing volunteers.

## Technical Stack
- **Backend**: Python 3.13, Flask
- **Database**: Google Firestore with year-based collections
- **Authentication**: Google OAuth with role-based access control
- **Frontend**: Bootstrap 5, Leaflet.js for mapping
- **Deployment**: Google Cloud Run
- **Data**: 24 count areas (A-X, excluding Y) with polygon boundaries from KML export

## Annual Event Architecture

### Data Organization
Each year's data is stored in separate Firestore collections:
- `participants_2025`, `participants_2024`, etc.
- `area_leaders_2025`, `area_leaders_2024`, etc.

### Cross-Year Data Access
- Historical queries merge results from multiple yearly collections
- Email deduplication keeps most recent participant information
- Area leaders can access historical contact lists for recruitment

## Authentication & Authorization

### Three Access Levels

**Public Access (No Authentication)**
- Registration pages
- Success confirmation pages
- Static content

**Admin Access (Google OAuth + Whitelist)**
- Designated users listed in `config/admins.py`
- Full system access across all years
- Participant and area leader management

**Area Leader Access (Google OAuth + Leader Database)**
- Any Google account registered as area leader
- Access to own area's participant lists (current + historical)
- Read-only access to historical data

### Admin Configuration
```python
# config/admins.py
ADMIN_EMAILS = [
    'birdcount@naturevancouver.ca',
    'coordinator@naturevancouver.ca',
    'admin1@naturevancouver.ca'
]
```

### Authentication Flow
1. User visits protected route
2. Redirect to Google OAuth if not authenticated
3. Check user role based on email:
   - In admin list → admin access
   - In area_leaders_YYYY collection → leader access
   - Otherwise → public access only
4. Grant access based on role and route requirements

## Core Features

### Registration System
- Collect: name, email, phone, birding skill level, CBC experience, area preference
- Leadership interest tracking (separate from actual leadership assignment)
- Dual area selection: interactive map clicking OR dropdown menu
- Manual assignment option: "Wherever I'm needed most" creates participants with preferred_area="UNASSIGNED" for admin review
- Email validation and duplicate registration prevention (per year)
- Mobile-responsive design (primary usage)

### Interactive Map
- Display 24 Vancouver CBC count areas as clickable polygons
- Color-coded by volunteer density: green (available), yellow (nearly full), red (full)
- Click area to auto-select in dropdown form
- Show current volunteer counts in tooltips
- Graceful fallback to dropdown-only if map fails

### Admin Interface
- Year selector (defaults to current year)
- View all participants and area assignments by year
- Unassigned participant management with assignment tools
- Assign area leaders to specific areas
- Export participant data as CSV (current or historical)
- Manual participant management (add/edit/delete for current year only)
- Area-specific participant lists
- Track participant removals for email notifications
- Daily email digest of unassigned participants

### Area Leader Interface
- View own area's participant lists (current + historical years)
- Export contact information for recruitment emails
- Read-only access to historical data
- Area-specific registration statistics

### Email Notification System
- Twice-daily automated checks for team changes
- Email area leaders when participants added/removed from their areas
- Daily digest to admins listing unassigned participants
- Timestamp-based change detection to prevent missed notifications
- Race condition handling: better to notify twice than miss changes

## Data Models

### Participants Collection (per year: participants_YYYY)
```
{
  id: auto_generated,
  first_name: string,
  last_name: string, 
  email: string,
  phone: string,
  skill_level: "Newbie|Beginner|Intermediate|Expert",
  experience: "None|1-2 counts|3+ counts",
  preferred_area: "A-X|UNASSIGNED",
  interested_in_leadership: boolean,  // From form
  is_leader: boolean,                 // Admin-assigned only
  assigned_area_leader: string,       // Which area they lead, if any
  assigned_by: string,               // Admin who assigned (if assigned)
  assigned_at: timestamp,            // When assigned (if assigned)
  created_at: timestamp,
  updated_at: timestamp,
  year: integer                       // Explicit year field for data integrity
}
```

### Area Leaders Collection (per year: area_leaders_YYYY)
```
{
  id: auto_generated,
  area_code: string,              // "A" through "X"
  leader_email: string,           // Google account email
  leader_name: string,
  leader_phone: string,
  assigned_by: string,            // Admin email who made assignment
  assigned_date: timestamp,
  active: boolean,
  year: integer
}
```

### Removal Log Collection (per year: removal_log_YYYY)
```
{
  participant_name: string,
  area_code: string,
  removed_by: string,
  reason: string,
  removed_at: timestamp,
  year: integer,
  emailed: boolean,
  emailed_at: timestamp
}
```

## Area Configuration
24 count areas with no capacity limits (areas can accommodate varying numbers based on habitat and accessibility). Area data includes:
- Letter code (A-X)
- Descriptive name and geographic boundaries
- Difficulty level and terrain type
- Polygon coordinates for map display

Static configuration in `config/areas.py` (no year dependency).

## Key Implementation Details

### Year-Based Data Access
```python
class ParticipantModel:
    def __init__(self, db_client, year=None):
        self.db = db_client
        self.year = year or datetime.now().year
        self.collection = f'participants_{self.year}'
```

### Area Boundary Extraction
1. Export KML from Google My Maps containing 24 count area polygons
2. Parse KML to extract coordinates and convert to GeoJSON format
3. Store as static JSON file for map rendering

### Map Integration
- Leaflet.js with OpenStreetMap tiles
- Parse GeoJSON polygons for clickable areas
- Synchronize map selection with form dropdown
- Mobile-optimized touch interactions

### Email Notification Logic
- Track last_email_sent timestamp per area per year
- Compare with participant last_modified timestamps
- Log removals separately since they're admin-only events
- Atomic timestamp capture prevents race conditions
- Test mode (TEST_MODE=true): All emails redirect to birdcount@naturevancouver.ca with modified subject/body indicating intended recipients
- Production mode (TEST_MODE=false or unset): Normal email delivery

### Leadership Management
- Participants can express interest but cannot self-assign leadership
- Admins review interested participants and assign leaders through interface
- Leaders get access to historical contact lists for their areas
- Multiple leaders per area supported

## User Workflows

### Volunteer Registration
1. Visit registration page with form and interactive map
2. Select area by clicking map polygon OR dropdown menu OR "Wherever I'm needed most"
3. Complete personal information including leadership interest
4. Submit and receive confirmation
5. If specific area selected: area leader receives automated notification
6. If "Wherever I'm needed most" selected: participant created with preferred_area="UNASSIGNED" for admin review

### Admin Management
1. Authenticate with Google OAuth (whitelisted admin account)
2. Select year (defaults to current)
3. View dashboard with area volunteer counts, recent registrations, and unassigned participants
4. Review daily digest of unassigned participants
5. Manually assign unassigned participants to appropriate areas
6. Assign area leaders from interested participants
7. Export participant lists for communication
8. Manually manage registrations as needed

### Area Leader Access
1. Authenticate with Google OAuth (any Google account)
2. System verifies leader status for current year
3. View own area's participants (current + historical years)
4. Export contact lists for recruitment emails
5. Cannot modify historical data

### Email Notifications
1. Twice-daily job checks for participant changes per area
2. Generate area-specific update emails for current year
3. Mark changes as processed to prevent duplicates
4. Include both additions and removals in updates

## File Structure
```
app.py                          # Flask entry point with OAuth integration
requirements.txt                # Python dependencies
Dockerfile                      # Container configuration
config/
  areas.py                      # Area definitions (static)
  settings.py                   # Environment configuration
  admins.py                     # Admin email whitelist
models/
  participant.py                # Year-aware participant operations
  area_leader.py               # Year-aware leader operations
  removal_log.py               # Year-aware removal tracking
routes/
  main.py                      # Public registration routes
  admin.py                     # Admin interface with year selector
  leader.py                    # Area leader interface
  api.py                       # JSON endpoints for map
  auth.py                      # OAuth and authorization handling
services/
  email_service.py             # Email service with test mode
templates/
  base.html                    # Base template with auth status
  index.html                   # Registration form
  registration_success.html    # Success page
  admin/                       # Admin interface templates
  leader/                      # Leader interface templates
  errors/                      # Error page templates
static/
  css/main.css                 # Responsive styling
  js/map.js                    # Interactive map functionality
  js/registration.js           # Form validation and interactions
  data/area_boundaries.json    # Parsed area polygons
```

## Historical Data Access Patterns

### Cross-Year Participant Lookup
```python
def get_historical_participants(area_code, years_back=3):
    current_year = datetime.now().year
    participants = {}  # email -> most recent data
    
    for year in range(current_year - years_back, current_year + 1):
        year_data = ParticipantModel(db, year).get_participants_by_area(area_code)
        for participant in year_data:
            participants[participant['email']] = participant
    
    return list(participants.values())
```

### Year Management
- Current year operations: full read/write access
- Historical years: read-only access (UI enforced + validation)
- Admin year selector with clear current/historical indicators
- Automatic year detection for new collections

## Constraints and Requirements
- Mobile-first design (most registrations via phone)
- No app installation required (web-based only)
- Canadian data hosting for privacy compliance (Google Cloud us-west1 or Montreal)
- Graceful degradation when services unavailable
- Integration with existing Google Sheets workflow (CSV export)
- Low maintenance overhead for volunteer organization
- Annual deployment cycle with minimal configuration changes

## Security Considerations
- Google OAuth integration for all authenticated access
- Admin whitelist maintained in version control
- Area leader permissions scoped to assigned areas only
- Historical data protection (read-only access)
- CSRF protection on all authenticated forms
- Session management with appropriate timeouts

## Deployment Architecture
- Google Cloud Run for application hosting
- Firestore for data persistence
- Custom domain: cbc-test.naturevancouver.ca (test), cbc-registration.naturevancouver.ca (production)
- Environment-based configuration (dev/test/prod)
- Automated SSL certificate management
- Scale-to-zero cost optimization during off-season

### Environment Variables
- `TEST_MODE=true` (test instance): Redirects all emails to birdcount@naturevancouver.ca with modified subject/body
- `TEST_MODE=false` or unset (production): Normal email delivery
- `GOOGLE_CLOUD_PROJECT=vancouver-cbc-registration` (required for Firestore)
- `SECRET_KEY` (Flask sessions, auto-generated if not set)