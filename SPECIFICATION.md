# Vancouver Christmas Bird Count Registration App - Complete Specification

## Overview
Web application for Nature Vancouver's annual Christmas Bird Count registration with interactive map-based area selection. Users can register by clicking count areas on a map or using a dropdown menu, with automatic assignment to areas needing volunteers.

## Technical Stack
- **Backend**: Python 3.13, Flask with Blueprint routing
- **Database**: Google Firestore with environment-specific databases (`cbc-test`, `cbc-register`) and year-based collections
- **Authentication**: Google Identity Services OAuth with Google Secret Manager for credentials
- **Frontend**: Bootstrap 5, Leaflet.js for interactive mapping
- **Deployment**: Google Cloud Run with automated deployment scripts
- **Security**: Role-based access control with admin whitelist and area leader database
- **Data**: 24 count areas (A-X, excluding Y) with GeoJSON polygon boundaries

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
1. User visits protected route (e.g., `/admin`)
2. Authentication decorator redirects to `/auth/login` if not authenticated  
3. Google Identity Services presents OAuth consent screen
4. User grants permission, Google returns JWT token via POST to `/auth/oauth/callback`
5. Server verifies token and extracts user email and name
6. System determines user role based on email:
   - In `config/admins.py` whitelist → **admin** access
   - In `area_leaders_YYYY` collection → **leader** access  
   - Otherwise → **public** access only
7. Role stored in Flask session for subsequent requests
8. User redirected to appropriate interface:
   - Admins → `/admin/dashboard`
   - Leaders → `/leader/dashboard` 
   - Public → main registration page

## Core Features

### Registration System
- Collect: name, email, phone, birding skill level, CBC experience, area preference
- Leadership interest tracking (separate from actual leadership assignment)
- Dual area selection: interactive map clicking OR dropdown menu
- Manual assignment option: "Wherever I'm needed most" creates participants with preferred_area="UNASSIGNED" for admin review
- Consistent terminology: "UNASSIGNED" used throughout system (replaced legacy "ANYWHERE" references)
- Email validation and duplicate registration prevention (per year)
- Mobile-responsive design (primary usage)

### Interactive Map
- Display 24 Vancouver CBC count areas as clickable polygons
- Color-coded by volunteer density: green (available), yellow (nearly full), red (full)
- Click area to auto-select in dropdown form
- Show current volunteer counts in tooltips
- Graceful fallback to dropdown-only if map fails

### Admin Interface
**Dashboard (`/admin/`)**
- Year selector with available years dropdown (defaults to current year)
- Statistics overview: total participants, assigned/unassigned counts, areas needing leaders
- Recent registrations preview (latest 10 participants)
- Quick action buttons for common management tasks

**Participant Management (`/admin/participants`)**
- Complete participant list with search and filtering
- Participant details: contact info, skill level, area assignment, leadership interest
- Delete participants with confirmation modal and reason logging
- Direct navigation to area-specific views

**Unassigned Participant Management (`/admin/unassigned`)**
- Area capacity overview with color-coded participant counts (fixed to show actual counts)
- Individual assignment tools with area dropdowns showing current participant counts
- Streamlined interface focused on essential assignment workflow
- Quick assignment to areas needing more volunteers

**Area Detail Views (`/admin/area/<code>`)**  
- Area-specific participant lists and statistics
- Team composition analysis (skill levels, experience distribution)
- Area leader assignments and contact information
- Historical participant data (3-year lookback for recruitment)
- Area difficulty and habitat information

**Leader Management (`/admin/leaders`)**
- Interactive map showing areas needing leaders (red) vs areas with leaders (green)
- Leader names displayed in map tooltips when hovering over areas with leaders
- Live map updates after edit/delete operations using client-side data management
- Current area leader assignments with contact information and status
- **Inline edit/delete functionality**: Edit leader information directly in the table
  - Edit button (pencil icon) enables inline editing of all fields simultaneously
  - Area dropdown, name fields, email, and phone become editable
  - Save button validates and updates leader information with business rule enforcement
  - Delete button (trash icon) with simple confirmation dialog
  - Real-time map refresh after successful operations
  - Client-side data synchronization prevents server round-trips for map updates
- Manual leader entry form with validation and business rule enforcement (primary workflow)
- Participant-to-leader promotion from "Potential Leaders" list (exceptional case)
- Areas without assigned leaders highlighted on map and listed below
- Map legend showing counts of areas with/without leaders
- Enhanced area dropdowns with proper area codes and names
- Integration logic: auto-assign leader registrations, sync participant promotions

**Export and Reporting**
- CSV export of all participants with comprehensive data
- Year-specific exports for historical analysis
- Email digest system for unassigned participants

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
  leader_email: string,           // Any email (Google or non-Google)
  first_name: string,             // Required
  last_name: string,              // Required  
  cell_phone: string,             // Required
  assigned_by: string,            // Admin email who made assignment
  assigned_at: timestamp,         // When leader was assigned
  active: boolean,                // Currently active leader
  year: integer,                  // Explicit year field
  created_from_participant: boolean, // True if promoted from participant
  notes: string                   // Optional admin notes
}
```

**Business Rules:**
- Multiple leaders allowed per area
- One area maximum per leader (enforced by application logic with validation)
- Leaders with Google emails can access leader UI, others receive notifications only
- Manual entry creates area_leaders records only (no participant record required)
- Inline editing enforces business rules: prevents duplicate area assignments per leader
- Participant synchronization: editing leaders promoted from participants updates both records

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

**Assignment Methods:**
1. **Manual Entry (Primary)**: Admins directly enter leader information
   - Creates records only in `area_leaders_YYYY` collection
   - No participant registration required
   - Supports any email address (Google or non-Google)

2. **Participant Promotion (Exceptional)**: Promote existing participants to leaders
   - Updates both `participants` and `area_leaders` collections
   - Changes participant's area assignment to match led area
   - Sets `is_leader=True` in participant record

**Integration Logic:**
- If leader registers as participant → auto-assign to their led area
- Leader status tracked in both collections for data consistency
- Email notifications sent to leaders for team updates (no workflow automation)

**Access Control:**
- Leaders with Google emails: Access to leader UI (`/leader` routes)
- Leaders with non-Google emails: Receive notifications only
- All leaders: Included in team communication and updates

**Business Rules:**
- Multiple leaders per area allowed
- One area maximum per leader (enforced by application)
- Required fields: first_name, last_name, email, cell_phone

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
app.py                          # Flask entry point with OAuth initialization
requirements.txt                # Python dependencies
Dockerfile                      # Container configuration for Cloud Run
deploy.sh                       # Automated deployment script (test/production/both)

config/
  areas.py                      # Static area definitions (24 areas A-X)
  settings.py                   # Environment configuration
  admins.py                     # Admin email whitelist

models/
  participant.py                # Year-aware participant operations with Firestore
  area_leader.py               # Year-aware leader management
  removal_log.py               # Year-aware removal tracking for audit

routes/
  main.py                      # Public registration routes
  admin.py                     # Complete admin interface with all management features
  leader.py                    # Area leader interface (to be implemented)
  api.py                       # JSON endpoints for map data and leadership information
  auth.py                      # Google Identity Services OAuth handling

services/
  email_service.py             # Email service with test mode support

templates/
  base.html                    # Base template with conditional navigation and Bootstrap Icons
  index.html                   # Registration form with interactive map
  registration_success.html    # Registration confirmation page
  auth/
    login.html                 # Google OAuth login page
  admin/
    dashboard.html             # Admin overview with statistics
    participants.html          # Complete participant management
    unassigned.html           # Unassigned participant assignment tools
    area_detail.html          # Area-specific participant and leader views
    leaders.html              # Leader management with inline edit/delete and live map updates
  leader/                      # Leader interface templates (to be implemented)
  errors/                      # 404/500 error page templates

static/
  css/main.css                 # Bootstrap-based responsive styling
  js/map.js                    # Leaflet.js interactive map functionality for registration
  js/leaders-map.js            # Leaflet.js interactive map for leaders page with live refresh capability
  js/registration.js           # Form validation and map-form synchronization
  data/area_boundaries.json    # GeoJSON area polygons for map rendering

utils/
  setup_oauth_secrets.sh       # OAuth credential setup script for Google Secret Manager
  setup_databases.py           # Firestore database creation script
  generate_test_participants.py # Test data generation script for development/testing
  requirements.txt             # Dependencies for utility scripts (requests, faker, firestore)

OAUTH-SETUP.md                  # Complete OAuth setup instructions
CLAUDE.md                       # AI assistant instructions and troubleshooting guide
SPECIFICATION.md                # This complete project specification
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

### Google Cloud Platform Configuration
- **Google Cloud Run** for stateless application hosting with automatic HTTPS
- **Google Firestore** for document-based data persistence  
- **Google Secret Manager** for secure OAuth credential storage
- **Custom domains**: 
  - Test: `cbc-test.naturevancouver.ca`
  - Production: `cbc-registration.naturevancouver.ca`
- **Region**: `us-west1` (Oregon) for data residency
- **Auto-scaling**: Scale-to-zero during off-season for cost optimization

### Deployment Process
**Automated Scripts:**
```bash
./deploy.sh test           # Deploy to test environment
./deploy.sh production     # Deploy to production environment  
./deploy.sh both          # Deploy to both environments (default)
```

**OAuth Setup (One-time):**
```bash
# 1. Create OAuth client in Google Console (see OAUTH-SETUP.md)
# 2. Download client_secret.json to project root
./utils/setup_oauth_secrets.sh    # Extract credentials to Secret Manager
rm client_secret.json             # Remove sensitive file
```

### Environment Variables
**Test Environment:**
- `FLASK_ENV=development`
- `TEST_MODE=true` (redirects all emails to admin with modified subject)
- `GOOGLE_CLOUD_PROJECT=vancouver-cbc-registration`

**Production Environment:**  
- `FLASK_ENV=production`
- `TEST_MODE=false` (normal email delivery)
- `GOOGLE_CLOUD_PROJECT=vancouver-cbc-registration`

**Secret Manager Credentials:**
- `GOOGLE_CLIENT_ID` (Google OAuth client ID)
- `GOOGLE_CLIENT_SECRET` (Google OAuth client secret) 
- `SECRET_KEY` (Flask session encryption key)

### Security Configuration
**OAuth Client Requirements:**
- Application type: **Web application**
- Authorized JavaScript origins: `https://DOMAIN` (both test and production)
- Authorized redirect URIs: **None** (Google Identity Services uses direct callbacks)
- OAuth consent screen: **Published** (not in testing mode)

**Cloud Run Service Account:**
- Default compute service account with `secretmanager.secretAccessor` role
- Firestore access through `GOOGLE_CLOUD_PROJECT` environment variable
- No additional IAM configuration required

## Implementation Notes

### Critical Implementation Requirements

**OAuth Integration:**
- Google Identity Services (not traditional OAuth redirect flow)
- Client credentials must be stored in Google Secret Manager (never in code)
- OAuth consent screen must be **published** for authentication to work
- **Common Issue**: Trailing newlines in client ID secrets cause "invalid_client" errors

**Database Design:**
- All Firestore operations must include explicit year fields for data integrity
- Composite indexes required for complex queries (auto-created via error URLs)
- Email deduplication logic prevents duplicate registrations within same year

**Security Architecture:**
- No admin links visible to public users (security by obscurity)
- Authentication decorators on all protected routes
- Role determination happens during OAuth callback and stored in session
- Admin access requires both OAuth authentication AND email whitelist membership

**Template Requirements:**
- All admin templates require year selector and breadcrumb navigation
- Mobile-responsive design mandatory (Bootstrap 5 classes)
- Error handling for missing data (empty collections, unavailable services)
- Consistent user feedback via Flask flash messaging system

### Common Development Pitfalls

1. **OAuth Client Configuration**
   - Must use "Web application" type (not Desktop or Mobile)
   - JavaScript origins required, redirect URIs must be empty
   - Consent screen must be published (not in testing mode)

2. **Secret Management** 
   - Never commit OAuth credentials to version control
   - Use `.strip()` on all secret values to remove newlines
   - Test credential access in Cloud Run environment before deployment

3. **Firestore Operations**
   - All write operations should include explicit year fields
   - Handle missing collections gracefully (new years start with empty data)
   - Use composite indexes for filtering by multiple fields

4. **Year-Based Data Access**
   - Always validate year parameters to prevent unauthorized historical access
   - Display clear indicators for current vs. historical data
   - Enforce read-only access to historical years via UI validation

### Database Setup
For initial project setup or after database deletion:
```bash
# Install utility dependencies
cd utils
pip install -r requirements.txt

# Create required Firestore databases
python setup_databases.py --dry-run       # Preview what would be created
python setup_databases.py                # Create missing databases with indexes (cbc-test, cbc-register)
python setup_databases.py --skip-indexes # Create databases only (faster, but may have runtime delays)
python setup_databases.py --force        # Recreate all databases (with confirmation)
```

### Test Data Generation
For development and testing purposes:
```bash
# Generate test participants
python generate_test_participants.py                    # 20 regular + 5 leadership
python generate_test_participants.py 50                # 50 regular + 5 leadership  
python generate_test_participants.py 10 --seq 100      # 10 regular + 5 leadership, start at email 0100
python generate_test_participants.py 0 --seq 5000      # 0 regular + 5 leadership, start at email 5000
```

### Testing and Validation

**Pre-Deployment Checklist:**
- [ ] OAuth client properly configured with published consent screen
- [ ] All secrets stored in Secret Manager and accessible by Cloud Run
- [ ] Admin email whitelist updated with current coordinators
- [ ] All admin templates render without errors for empty data sets
- [ ] Mobile responsiveness tested on various screen sizes
- [ ] Year selector functionality verified across all admin interfaces

**Post-Deployment Verification:**
```bash
# Test OAuth flow
curl -I https://DOMAIN/admin  # Should redirect to login

# Verify admin authentication
# (Manual test: authenticate with whitelisted admin account)

# Check application logs for errors
gcloud run services logs read SERVICE --region=us-west1 --limit=50

# Verify Firestore connectivity and permissions
# (Admin dashboard should load without database errors)
```

This specification represents a complete, production-ready Christmas Bird Count registration system with comprehensive admin management capabilities.