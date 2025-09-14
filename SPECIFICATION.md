# Vancouver Christmas Bird Count Registration App - Complete Specification
{# Updated by Claude AI on 2025-09-12 #}

## Overview
Web application for Nature Vancouver's annual Christmas Bird Count registration with interactive map-based area selection. Users can register by clicking count areas on a map or using a dropdown menu, with automatic assignment to areas needing volunteers.

## Technical Stack
- **Backend**: Python 3.13, Flask with Blueprint routing
- **Database**: Google Firestore with multi-database architecture:
  - `cbc-test`: Development/testing environment database
  - `cbc-register`: Production environment database
  - Year-based collections within each database (`participants_2025`, `area_leaders_2025`)
  - Automated database setup with composite indexes
- **Authentication**: Google Identity Services OAuth with Google Secret Manager for credentials
- **Frontend**: Bootstrap 5 + Bootstrap Icons, Leaflet.js for interactive mapping
- **Deployment**: Google Cloud Run with automated deployment scripts for both environments
- **Security**: Role-based access control with admin whitelist and area leader database
- **Data**: 25 count areas (A-Y) with admin-assignment-only flag system for flexible area management

## Annual Event Architecture

### Data Organization
Each year's data is stored in separate Firestore collections:
- `participants_2025`, `participants_2024`, etc.
- `area_leaders_2025`, `area_leaders_2024`, etc.

### Cross-Year Data Access
- Historical queries merge results from multiple yearly collections
- Email deduplication keeps most recent participant information
- Area leaders can access historical contact lists for recruitment

### Environment-Specific Database Architecture
- **Automatic Database Selection**: Environment-specific database selection based on `FLASK_ENV` and `TEST_MODE` variables
- **Database Setup Automation**: `utils/setup_databases.py` script creates both databases with proper indexes
- **Multi-Environment Support**: Seamless switching between test and production databases
- **Index Management**: Automated composite index creation for optimal query performance
- **Data Isolation**: Complete separation of test and production data

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
- **Personal Information**: First name, last name, email, phone number
- **Experience Data**: Birding skill level (Newbie|Beginner|Intermediate|Expert), CBC experience (None|1-2 counts|3+ counts)
- **Participation Options**: 
  - **Participation Type**: Regular participant or FEEDER counter (mandatory selection)
  - **Area Selection**: Interactive map clicking OR dropdown menu OR "Wherever I'm needed most"
- **Equipment Information**: 
  - Binoculars availability checkbox
  - Spotting scope availability checkbox ("Can bring spotting scope")
- **Communication**: Notes to organizers (optional textarea with 500+ character limit)
- **Role Interest Options**: 
  - **Leadership Interest**: Checkbox tracking (separate from actual leadership assignment) with clickable link to detailed responsibilities
  - **Scribe Interest**: Checkbox for new pilot role with clickable link to detailed information and eBird preparation guide
- **FEEDER Participant Constraints**:
  - Cannot select "UNASSIGNED" (must choose specific area)
  - Cannot indicate leadership interest (disabled automatically)
  - Represented ~20% of participant population
- **Validation Rules**:
  - Email validation and duplicate registration prevention (per year)
  - Client-side and server-side validation for FEEDER constraints
  - Required field validation for all core information
- **Mobile-responsive design** with touch-optimized form controls

### Information Pages with Form Data Preservation
**Area Leader Information (`/area-leader-info`)**
- Detailed 7-point list of area leader responsibilities and coordination duties
- Accessible via clickable "area leader" text in registration form
- Preserves all form data during navigation using generic form data capture

**Scribe Information (`/scribe-info`)**  
- Description of new pilot scribe role for partnering with expert birders
- eBird preparation requirements with direct link to eBird Essentials course
- Information about pilot program status and leader coordination
- Accessible via clickable "Scribe" text in registration form
- Preserves all form data during navigation using generic form data capture

**Form Data Preservation System**
- Generic FormData() capture automatically handles all form fields
- Bidirectional navigation maintains user input across page transitions
- No field-specific code required - automatically adapts to form changes
- URL parameter-based data passing for reliable form restoration

### Interactive Map
- Display 24 Vancouver CBC count areas as clickable polygons
- Color-coded by registration count: orange (0-3 registered), maroon (4-8 registered), navy (8+ registered)
- Yellow highlighting for selected areas
- Click area to auto-select in dropdown form
- Show current volunteer counts in tooltips
- Graceful fallback to dropdown-only if map fails

### Admin Interface
**Dashboard (`/admin/`)**
- Year selector with available years dropdown (defaults to current year)
- Statistics overview: total participants, assigned/unassigned counts, areas needing leaders
- Recent registrations preview (latest 10 participants)
- Quick action buttons for common management tasks
- **Email Testing Section (Test Server Only)**: Manual trigger buttons for testing all three email types with immediate feedback

**Participant Management (`/admin/participants`)**
- **Dual-Section Display**: Separate tables for FEEDER and regular participants
- **In-Page Navigation**: Jump links to quickly access FEEDER or regular participant sections
- **Area-Based Organization**: Participants grouped alphabetically by area with participant counts in headers
  - **Area Leader Information**: When leaders are assigned, displays leader name, email, and phone in area headers
- **Comprehensive Information Display**:
  - Contact info: name, email, phone with clickable mailto links
  - Experience data: skill level badges, CBC experience
  - **Equipment Icons**: Bootstrap binoculars icon, custom SVG spotting scope icon
  - **Notes Display**: Truncated to 50 characters with full text in hover tooltips
  - Area assignment with links to area detail views
  - Leadership status and interest indicators
  - **Scribe Interest Indicators**: Blue "Interested" badges for participants interested in scribe role (regular participants only)
  - Registration timestamps
- **Sorting**: Areas displayed in alphabetical order, participants within each area sorted alphabetically by first name
- **Actions**: Delete participants with confirmation modal and reason logging
- **Visual Indicators**: FEEDER participants clearly marked with type indicator

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
- **Potential Leaders Assignment**: Dropdown shows all areas (including admin-only areas T, Y) allowing multiple leaders per area
- Integration logic: auto-assign leader registrations, sync participant promotions

**Export and Reporting**
- **Comprehensive CSV Export**: All participant fields including new registration data:
  - Personal information (name, email, phone)
  - Experience data (skill level, CBC experience)
  - Participation type (regular/FEEDER)
  - Equipment information (binoculars, spotting scope)
  - Notes to organizers
  - Area assignments and leadership data
  - Registration timestamps and year
- **Export Sorting**: Data sorted alphabetically by area → participation type → first name
- **Multiple Export Locations**: Available from both dashboard and participants pages
- **Year-specific exports** for historical analysis
- **Email digest system** for unassigned participants

### Area Leader Interface
- View own area's participant lists (current + historical years)
- Export contact information for recruitment emails
- Read-only access to historical data
- Area-specific registration statistics

### Email Notification System (Core Complete, API Pending)
**Three Automated Email Types:**

1. **Twice-Daily Team Updates**:
   - Recipients: Area leaders when team composition changes
   - Subject: "CBC Area X Team Update"  
   - Content: New members, removed members, complete current team roster
   - Triggers: Participant additions, removals, area reassignments, email changes
   - Frequency: Automated checks twice daily (production scheduling pending)

2. **Weekly Team Summary (No Changes)**:
   - Recipients: Area leaders with no team changes in past week
   - When: Every Friday at 11pm Pacific
   - Subject: "CBC Area X Weekly Summary"
   - Content: "No changes this week" + complete team roster with contact details

3. **Daily Admin Digest**:
   - Recipients: All admins (from `config/admins.py`)
   - Subject: "CBC Registration: X Unassigned Participants"
   - Content: List of unassigned participants with details + admin interface link

**Implementation Architecture:**
- **Email Generation**: Core logic in `test/email_generator.py` with Flask app context support
- **Email Templates**: HTML templates in `templates/emails/` directory
- **Email Service**: `services/email_service.py` with test mode support (requires Google Cloud Email API)
- **Environment-Based Security**: Test email routes only registered when `TEST_MODE=true`
- **Test Mode Behavior**: All emails redirect to `birdcount@naturevancouver.ca` with modified subjects
- **Timezone Support**: Configurable display timezone via `DISPLAY_TIMEZONE` environment variable
- **Race Condition Prevention**: Timestamp selection before queries, update after successful send
- **Change Detection**: Participant diff tracking with detailed logging of additions/removals
- **Error Handling**: Graceful failure with detailed logging, continues processing other areas

**Current Implementation Status:**
- ✅ **Email Generation Logic**: Complete implementation with timezone-aware datetime handling
- ✅ **Email Templates**: HTML templates created for all three email types
- ✅ **Security**: Production servers do not expose test email routes
- ✅ **Timezone Handling**: UTC storage with configurable display timezone conversion
- ✅ **Test Interface**: Manual trigger buttons in admin dashboard (test server only)
- ✅ **Package Structure**: Proper Python imports and deployment-safe directory structure
- ❌ **Email Service**: Currently uses SMTP, needs Google Cloud Email API configuration
- ❌ **Production Automation**: Cloud Scheduler configuration pending for automated triggers

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
  participation_type: "regular|FEEDER",     // New: Type of participation
  has_binoculars: boolean,                   // New: Equipment availability
  spotting_scope: boolean,                   // New: Can bring spotting scope (shortened from can_bring_spotting_scope)
  notes_to_organizers: string,               // New: Optional participant notes
  interested_in_leadership: boolean,         // From form checkbox
  interested_in_scribe: boolean,             // New: Scribe role interest (pilot program)
  is_leader: boolean,                        // Admin-assigned only
  assigned_area_leader: string,              // Which area they lead, if any
  auto_assigned: boolean,                    // True if auto-assigned from leadership
  assigned_by: string,                       // Admin who assigned (if assigned)
  assigned_at: timestamp,                    // When assigned (if assigned)
  created_at: timestamp,
  updated_at: timestamp,
  year: integer                              // Explicit year field for data integrity
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

### Admin-Assignment-Only Flag System
The application uses a flexible area management system that allows clubs to designate certain areas as admin-only, which means that only admins can assign participants to the designated areas:

```python
# config/areas.py
AREA_CONFIG = {
    'A': {
        'name': 'Area A - North Shore West',
        'description': 'West of the Capilano River, North of the Trans Canada Highway',
        'difficulty': 'Moderate',
        'terrain': 'Mountainous, some trails',
        'admin_assignment_only': False  # Available for public registration
    },
    # ... areas B-S, U-X with admin_assignment_only: False
    'T': {
        'name': 'Area T - Richmond East',
        'description': 'Vancouver International Airport and surrounds',
        'difficulty': 'Easy',
        'terrain': 'Airport and surrounds',
        'admin_assignment_only': True   # Restricted access area
    },
    'Y': {
        'name': 'Area Y - Burrard Inlet/English Bay',
        'description': 'This area is counted from one or more boats',
        'difficulty': 'Moderate',
        'terrain': 'Marine, boat-based counting',
        'admin_assignment_only': True   # Marine area surveyed by boat
    }
}
```

### Area Access Logic
- **Public Registration**: Uses `get_public_areas()` - shows only areas with `admin_assignment_only: False` (A-S, U-X)
- **Admin Interfaces**: Uses `get_all_areas()` - shows all areas including admin-only (A-Y)
- **Dynamic Validation**: `validate_area_code()` automatically validates against current `AREA_CONFIG` keys, making the system portable for other clubs with different area naming schemes (numbers, custom codes, etc.)
- **Multiple Leaders**: All areas support multiple leaders per area (business rule enforced in application)
- **Map Display**: Public maps show public areas only (based on static boundaries JSON)

### Area Data Structure
25 count areas with no capacity limits (areas accommodate varying numbers based on habitat and accessibility):
- Letter codes A-Y (25 areas total)
- Descriptive names and geographic boundaries  
- Difficulty level and terrain type
- Admin-assignment-only flag requires admins to perform participant assignment for some areas, e.g. airports with restricted access or marine areas surveyed by boat
- Polygon coordinates for map display (restricted areas may not have public map boundaries)

Static configuration in `config/areas.py` (no year dependency) with helper functions:
- `get_all_areas()`: Returns all configured area codes (dynamically reads from `AREA_CONFIG.keys()`)
- `get_public_areas()`: Returns only public areas (excludes admin-only areas)
- `get_area_info(code)`: Returns area configuration details

**Portability Design**: The system uses dynamic area validation based on `AREA_CONFIG` keys rather than hardcoded patterns, making it easy to adapt for other Christmas Bird Count clubs with different area naming schemes (numbers, regions, custom codes).

## Key Implementation Details

### Color System Implementation
The application uses a centralized color management system based on the 20 distinct colors from sashamaps.net's 99.99% accessibility palette:

```python
# config/colors.py
DISTINCT_COLOURS = {
    'orange': '#f58231',  # 0-3 registered
    'maroon': '#800000',  # 4-8 registered  
    'navy': '#000075',    # 8+ registered
    'yellow': '#ffe119', # Selected area
    # ... 16 additional accessibility colors
}

MAP_COLORS = {
    'low_count': DISTINCT_COLOURS['orange'],
    'med_count': DISTINCT_COLOURS['maroon'], 
    'high_count': DISTINCT_COLOURS['navy'],
    'selected': DISTINCT_COLOURS['yellow']
}
```

**CSS Custom Properties Implementation:**
```css
:root {
    --map-color-low: #f58231;   /* Orange - 0-3 registered */
    --map-color-med: #800000;   /* Maroon - 4-8 registered */
    --map-color-high: #000075;  /* Navy - 8+ registered */
    --map-color-selected: #ffe119; /* Yellow - selected area */
}

.area-polygon-low-count {
    stroke: var(--map-color-low);
    fill: var(--map-color-low);
}
```

**JavaScript Integration:**
```javascript
function getAreaStyle(count) {
    const rootStyles = getComputedStyle(document.documentElement);
    if (count <= 3) {
        const color = rootStyles.getPropertyValue('--map-color-low').trim();
        return { color: color, fillColor: color };
    }
    // Additional count ranges...
}
```

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
- Registration count-based coloring (0-3: orange, 4-8: maroon, 8+: navy)
- CSS custom properties for centralized color management
- JavaScript integration with CSS variables via `getComputedStyle()`
- Synchronize map selection with form dropdown
- Mobile-optimized touch interactions

### Email Notification Logic
- **Email Templates**: HTML email templates for each email type with environment-aware links
- **SMTP Configuration**: Email service configuration with provider settings
- **Environment-Aware Links**: Test server links to `cbc-test.naturevancouver.ca`, production to `cbc-registration.naturevancouver.ca`
- **Delivery Monitoring**: Logging and error handling for email delivery failures
- **Test Mode Implementation**: Manual triggers via admin dashboard for development testing

### Leadership Management

**Assignment Methods:**
1. **Manual Entry (Primary)**: Admins directly enter leader information
   - Creates records only in `area_leaders_YYYY` collection with standardized field names
   - No participant registration required
   - Supports any email address (Google or non-Google)
   - Uses consistent schema: `first_name`, `last_name`, `cell_phone`, `leader_email`

2. **Participant Promotion (Exceptional)**: Promote existing participants to leaders
   - Updates both `participants` and `area_leaders` collections
   - Changes participant's area assignment to match led area
   - Sets `is_leader=True` in participant record
   - Creates area leader record with standardized field names

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
3. Complete personal information including leadership and scribe interest
4. **Optional**: Click "area leader" or "Scribe" links to view detailed role information (preserves all form data)
5. Submit and receive confirmation
6. If specific area selected: area leader receives automated notification
7. If "Wherever I'm needed most" selected: participant created with preferred_area="UNASSIGNED" for admin review

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
requirements.txt                # Python dependencies (Flask, google-cloud-firestore, gunicorn, Flask-WTF, Flask-Limiter)
Dockerfile                      # Container configuration for Cloud Run
deploy.sh                       # Automated deployment script (test/production/both)

config/
  areas.py                      # Static area definitions (24 areas A-X)
  settings.py                   # Environment configuration
  admins.py                     # Admin email whitelist
  colors.py                     # Color palette definitions with 20 distinct accessibility colors
  database.py                   # Database configuration helper for environment-specific databases
  email_settings.py             # Email service configuration and SMTP settings (to be created)
  rate_limits.py                # Rate limiting configuration with TEST_MODE-aware settings

models/
  participant.py                # Year-aware participant operations with Firestore
  area_leader.py               # Year-aware leader management
  removal_log.py               # Year-aware removal tracking for audit

routes/
  main.py                      # Public registration routes including information pages (/area-leader-info, /scribe-info)
  admin.py                     # Complete admin interface with all management features
  leader.py                    # Area leader interface (to be implemented)
  api.py                       # JSON endpoints for map data and leadership information
  auth.py                      # Google Identity Services OAuth handling

services/
  email_service.py             # Email service with test mode support
  security.py                  # Input sanitization and security validation functions
  limiter.py                   # Shared Flask-Limiter instance for rate limiting

templates/
  base.html                    # Base template with context-aware navigation and Bootstrap Icons
  index.html                   # Registration form with interactive map
  registration_success.html    # Registration confirmation page
  area_leader_info.html        # Area leader responsibilities information page
  scribe_info.html             # Scribe role information page with eBird preparation guide
  auth/
    login.html                 # Google OAuth login page
  admin/
    dashboard.html             # Admin overview with statistics
    participants.html          # Complete participant management
    unassigned.html           # Streamlined unassigned participant assignment tools
    area_detail.html          # Area-specific participant and leader views
    leaders.html              # Leader management with inline edit/delete and live map updates
  leader/                      # Leader interface templates (to be implemented)
  emails/                      # Email templates directory (to be created)
    team_update.html           # HTML template for twice-daily team updates
    weekly_summary.html        # HTML template for weekly team summaries  
    admin_digest.html          # HTML template for daily admin digest
  errors/                      # 404/500 error page templates

static/
  css/main.css                 # Bootstrap-based responsive styling with CSS custom properties
  js/map.js                    # Leaflet.js interactive map functionality for registration
  js/leaders-map.js            # Leaflet.js interactive map for leaders page with live refresh capability
  js/registration.js           # Enhanced form validation with FEEDER constraint handling and map-form synchronization
  icons/scope.svg              # Custom spotting scope icon for equipment display
  data/area_boundaries.json    # GeoJSON area polygons for map rendering

test/
  __init__.py                  # Package initialization for test directory
  email_generator.py           # Email generation logic for automated notifications

utils/
  setup_oauth_secrets.sh       # OAuth credential setup script for Google Secret Manager
  setup_databases.py           # Firestore database creation script with environment-specific databases
  generate_test_participants.py # Test data generation script with timestamped emails for uniqueness and CSRF token support
  requirements.txt             # Dependencies for utility scripts (requests, faker, firestore, beautifulsoup4)

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

## Security Architecture

### Comprehensive Security Implementation
The application implements multiple layers of security protection against common web application vulnerabilities:

### Input Sanitization & Validation
**All user inputs are sanitized using functions from `services/security.py`:**
- **Names**: `sanitize_name()` - max 100 chars, letters/spaces/hyphens/apostrophes, international character support
- **Emails**: `sanitize_email()` - max 254 chars, lowercase normalization, valid email character validation
- **Phone Numbers**: `sanitize_phone()` - max 20 chars, digits/spaces/hyphens/parentheses/plus signs only
- **Notes/Comments**: `sanitize_notes()` - max 1000 chars, allows newlines, removes control characters
- **Validation Functions**:
  - `validate_area_code()` - Dynamic validation against `AREA_CONFIG` keys (supports any naming scheme)
  - `validate_skill_level()`, `validate_experience()`, `validate_participation_type()` - Predefined value validation

### XSS Prevention
**Template Security (ALL user input displays):**
- HTML escaping using `|e` filter: `{{ user_input|e }}`
- Prevents script injection in names, emails, phone numbers, notes
- Applied to: `templates/admin/area_detail.html`, `templates/admin/participants.html`, all admin interfaces

### CSRF Protection  
**Cross-Site Request Forgery prevention:**
- Flask-WTF CSRFProtect enabled application-wide
- All POST forms include `{{ csrf_token() }}` hidden input
- AJAX requests include `csrf_token: '{{ csrf_token() }}'` in JSON payload
- Automatic validation on all POST endpoints

### Rate Limiting
**DoS prevention and cost control for Cloud Run:**
- **Production Limits**: 10 registrations/minute, 20 API calls/minute, 30 admin actions/minute, 5 auth attempts/minute
- **Test Environment**: 50 registrations/minute (TEST_MODE detection)
- **Implementation**: Flask-Limiter with in-memory storage
- **Cloud Run Protection**: Prevents cost runaway during attacks
- **Configuration**: `config/rate_limits.py` with environment-based limits

### Suspicious Input Detection
**Attack pattern recognition:**
- `is_suspicious_input()` function screens for script injection attempts
- Detects: `<script>`, `javascript:`, event handlers, `eval()`, document manipulation
- Security event logging with `log_security_event()`
- Blocks submissions containing suspicious patterns

### Authentication & Authorization
**Multi-tier access control:**
- **Public Access**: Registration and information pages (no auth required)
- **Admin Access**: Google OAuth + email whitelist in `config/admins.py`
- **Area Leader Access**: Google OAuth + database verification of leadership assignment
- **Session Management**: Flask sessions with secure cookie settings
- **Role Determination**: During OAuth callback with session storage

### Data Security
**Database and data protection:**
- **Year-based isolation**: Separate collections per year prevent cross-year data corruption
- **Historical data protection**: Read-only access to previous years via UI validation
- **Email deduplication**: Prevents duplicate registrations within same year
- **Area leader scoping**: Leaders can only access assigned areas
- **Admin audit trail**: All modifications logged with user attribution

### Environment Security
**Development vs Production separation:**
- **Database Isolation**: `cbc-test` vs `cbc-register` databases
- **Email Safety**: Test mode redirects all emails to admin
- **Secret Management**: Google Secret Manager for OAuth credentials
- **Environment Detection**: `TEST_MODE` and `FLASK_ENV` variables
- **Route Protection**: Test-only routes unavailable in production

### Security Testing
**Comprehensive security validation:**
- **Test Script Integration**: `utils/generate_test_participants.py` tests all security features
- **CSRF Testing**: Automatic token fetching and validation testing
- **Rate Limit Testing**: `--test-rate-limit` flag validates blocking behavior
- **Error Classification**: Rate limited, CSRF failures, other failures tracked separately

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

**Database Architecture:**
- **Environment-specific databases**: `cbc-test` for development, `cbc-register` for production
- **Automatic database selection**: Based on `FLASK_ENV` and `TEST_MODE` environment variables
- **Composite indexes**: Automatically created by database setup script for optimal performance
- **Year-based collections**: All data organized by year with explicit year fields for integrity

**OAuth Integration:**
- Google Identity Services (not traditional OAuth redirect flow)
- Client credentials must be stored in Google Secret Manager (never in code)
- OAuth consent screen must be **published** for authentication to work
- **Common Issues**: 
   - Trailing newlines in client ID secrets cause "invalid_client" errors
   - Duplicate email addresses cause registration failures (test script now uses timestamped emails for uniqueness)

**Database Design:**
- All Firestore operations must include explicit year fields for data integrity
- Composite indexes required for complex queries (created automatically by setup script)
- Email deduplication logic prevents duplicate registrations within same year
- **Consistent Field Names**: All area leader records use standardized schema (`first_name`, `last_name`, `cell_phone`, `leader_email`) across all creation methods

**Security Architecture:**
- No admin links visible to public users (security by obscurity)
- Authentication decorators on all protected routes
- Role determination happens during OAuth callback and stored in session
- Admin access requires both OAuth authentication AND email whitelist membership

**Template Requirements:**
- All admin templates require year selector and breadcrumb navigation
- **Context-aware navigation**: Admin templates show "Admin" branding and link to admin dashboard
- Mobile-responsive design mandatory (Bootstrap 5 classes)
- Error handling for missing data (empty collections, unavailable services)
- Consistent user feedback via Flask flash messaging system
- Inline editing capabilities with live updates for leader management

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
# Generate test participants with unique timestamped emails
python generate_test_participants.py                    # 20 regular + 5 leadership + random scribes
python generate_test_participants.py 50                # 50 regular + 5 leadership + random scribes  
python generate_test_participants.py 10 --seq 100      # 10 regular + 5 leadership, start at email 0100
python generate_test_participants.py 0 --seq 5000      # 0 regular + 5 leadership, start at email 5000
python generate_test_participants.py 20 --scribes 5    # 20 regular + 5 leadership + 5 explicit scribes

# Email format includes timestamp for uniqueness: birdcount-YYYY-MM-DD-TIMESTAMP-NNNN@naturevancouver.ca
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

# Test participant registration
python utils/generate_test_participants.py 2 --scribes 1  # Should create 2 regular + 5 leadership + 1 scribe participants
```

## File Modification Guidelines

### Timestamp Comments
When modifying files, add timestamp comments using date only (not specific times):
- **Python files**: `# Updated by Claude AI on YYYY-MM-DD` 
- **HTML templates (Jinja2)**: `{# Updated by Claude AI on YYYY-MM-DD #}`
- **JavaScript/CSS**: `/* Updated by Claude AI on YYYY-MM-DD */`

Use the current date from the environment context, not specific times since Claude doesn't have access to precise timestamps.

### Documentation Guidelines
- SPECIFICATION.md reflects current implementation state only
- Do not include future plans from DEVELOPMENT_NOTES.md in SPECIFICATION.md
- Update specifications based on actual implementation, not planning documentation
- Include all implemented features with sufficient technical detail for reproduction

---

This specification represents a Christmas Bird Count registration system with comprehensive admin management capabilities, including enhanced registration data collection, comprehensive participant management interfaces, and flexible admin-assignment-only area system for specialized counting areas.