# Vancouver Christmas Bird Count Registration App - Specification

## Overview
Web application for Nature Vancouver's annual Christmas Bird Count registration with interactive map-based area selection. Users can register by clicking count areas on a map or using a dropdown menu, with automatic assignment to areas needing volunteers.

## Technical Stack
- **Backend**: Python 3.13, Flask
- **Database**: Google Firestore 
- **Frontend**: Bootstrap 5, Leaflet.js for mapping
- **Deployment**: Google Cloud Run
- **Data**: 24 count areas (A-X, excluding Y) with polygon boundaries from KML export

## Core Features

### Registration System
- Collect: name, email, phone, birding skill level, CBC experience, area preference, leader interest
- Dual area selection: interactive map clicking OR dropdown menu
- Auto-assignment option: "Wherever I'm needed most" assigns to area with fewest volunteers
- Email validation and duplicate registration prevention
- Mobile-responsive design (primary usage)

### Interactive Map
- Display 24 Vancouver CBC count areas as clickable polygons
- Color-coded by volunteer density: green (available), yellow (nearly full), red (full)
- Click area to auto-select in dropdown form
- Show current volunteer counts in tooltips
- Graceful fallback to dropdown-only if map fails

### Admin Interface
- View all participants and area assignments
- Export participant data as CSV
- Manual participant management (add/edit/delete)
- Area-specific participant lists
- Track participant removals for email notifications

### Email Notification System
- Twice-daily automated checks for team changes
- Email area leaders when participants added/removed
- Timestamp-based change detection to prevent missed notifications
- Race condition handling: better to notify twice than miss changes

## Data Model (Firestore Collections)

### participants
```
{
  id: auto_generated,
  first_name: string,
  last_name: string, 
  email: string,
  phone: string,
  skill_level: "Newbie|Beginner|Intermediate|Expert",
  experience: "None|1-2 counts|3+ counts",
  preferred_area: "A-X|ANYWHERE",
  is_leader: boolean,
  auto_assigned: boolean,
  created_at: timestamp,
  year: integer
}
```

### removal_log
```
{
  participant_name: string,
  area_code: string,
  removed_by: string,
  reason: string,
  removed_at: timestamp,
  year: integer,
  emailed: boolean
}
```

## Area Configuration
24 count areas with no capacity limits (areas can accommodate varying numbers based on habitat and accessibility). Area data includes:
- Letter code (A-X)
- Descriptive name and geographic boundaries
- Difficulty level and terrain type
- Polygon coordinates for map display

## Key Implementation Details

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
- Track last_email_sent timestamp per area
- Compare with participant last_modified timestamps
- Log removals separately since they're admin-only events
- Atomic timestamp capture prevents race conditions

### Deployment Configuration
- Containerized with Docker for Cloud Run
- Canadian hosting preferred for data sovereignty
- Firestore for scalability and offline development capability
- Environment-based configuration (dev/prod)

## File Structure
```
app.py                          # Flask entry point
requirements.txt                # Python dependencies
Dockerfile                      # Container configuration
config/
  areas.py                      # Area definitions
  settings.py                   # Environment configuration
models/
  participant.py                # Participant database operations
  removal_log.py               # Removal tracking
routes/
  main.py                      # Public registration routes
  admin.py                     # Admin interface
  api.py                       # JSON endpoints for map
templates/
  base.html                    # Base template
  index.html                   # Registration form
  registration_success.html    # Success page
static/
  css/main.css                 # Responsive styling
  js/map.js                    # Interactive map functionality
  js/registration.js           # Form validation and interactions
  data/area_boundaries.json    # Parsed area polygons
```

## User Workflows

### Volunteer Registration
1. Visit registration page with form and interactive map
2. Select area by clicking map polygon OR dropdown menu
3. Complete personal information and submit
4. Receive confirmation with area leader contact info

### Admin Management
1. View dashboard with area volunteer counts
2. Export participant lists for communication
3. Manually reassign participants as needed
4. Area leaders receive automated email updates

### Email Notifications
1. Twice-daily job checks for participant changes
2. Generate area-specific update emails
3. Mark changes as processed to prevent duplicates
4. Include both additions and removals in updates

## Constraints and Requirements
- Mobile-first design (most registrations via phone)
- No app installation required (web-based only)
- Canadian data hosting for privacy compliance
- Graceful degradation when services unavailable
- Integration with existing Google Sheets workflow
- Low maintenance overhead for volunteer organization