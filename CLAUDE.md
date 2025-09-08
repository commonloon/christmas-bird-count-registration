# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About This Project

This is a Flask web application for Nature Vancouver's annual Christmas Bird Count registration system. Users can register for count areas using an interactive map or dropdown, with automatic assignment to areas needing volunteers.

## Core Architecture

### Annual Event Structure
- **Year-based data collections**: Each year's data is stored separately (e.g., `participants_2025`, `area_leaders_2025`)
- **Cross-year access**: Historical queries merge results from multiple yearly collections with email deduplication
- **Three access levels**: Public (no auth), Area Leader (Google OAuth), Admin (OAuth + whitelist)

### Key Components
- **Backend**: Flask with Blueprint routing architecture
- **Database**: Google Firestore with year-aware models
- **Authentication**: Google OAuth with role-based access control
- **Frontend**: Bootstrap 5 + Leaflet.js interactive map
- **Deployment**: Google Cloud Run + Firestore

## Essential Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py
# Serves on http://localhost:8080 with debug=True

# Test Firestore connection (requires GCP credentials)
python -c "from google.cloud import firestore; print('Firestore OK' if firestore.Client() else 'Failed')"
```

### Deployment
```bash
# Deploy to test environment
gcloud run deploy cbc-test --source . --platform managed --region us-west1 --allow-unauthenticated --set-env-vars GOOGLE_CLOUD_PROJECT=vancouver-cbc-registration

# Deploy to production
gcloud run deploy cbc-registration --source . --platform managed --region us-west1 --allow-unauthenticated --set-env-vars GOOGLE_CLOUD_PROJECT=vancouver-cbc-registration

# View logs
gcloud run services logs read cbc-test --region=us-west1 --limit=50
```

## Project Structure

### Core Files
- `app.py` - Flask application entry point with blueprint registration
- `requirements.txt` - Python dependencies (Flask, google-cloud-firestore, gunicorn)
- `Dockerfile` - Container configuration for Cloud Run deployment

### Configuration
- `config/areas.py` - Static area definitions (A-X, 24 areas)
- `config/admins.py` - Admin email whitelist
- `config/settings.py` - Environment configuration

### Models (Year-Aware)
- `models/participant.py` - Year-specific participant operations with Firestore
- `models/area_leader.py` - Year-specific leader management
- `models/removal_log.py` - Year-specific removal tracking

### Routes (Blueprints)
- `routes/main.py` - Public registration routes
- `routes/admin.py` - Admin interface with year selector  
- `routes/auth.py` - OAuth and authorization handling
- `routes/api.py` - JSON endpoints for map data

### Frontend
- `static/js/map.js` - Leaflet.js interactive map with area selection
- `static/js/registration.js` - Form validation and interactions
- `static/css/main.css` - Bootstrap-based responsive styling
- `static/data/area_boundaries.json` - GeoJSON area polygons for map

### Templates
- `templates/base.html` - Base template with auth status
- `templates/index.html` - Registration form with map
- `templates/admin/` - Admin interface templates
- `templates/errors/` - 404/500 error pages

## Key Implementation Patterns

### Year-Based Data Access
```python
# Models automatically use current year unless specified
participant_model = ParticipantModel(db)  # Uses current year
historical_model = ParticipantModel(db, 2024)  # Specific year

# Cross-year queries for historical data
historical_participants = participant_model.get_historical_participants('A', years_back=3)
```

### Authentication Flow
1. Google OAuth for protected routes
2. Role determination:
   - Admin: Email in `config/admins.py` → full access
   - Area Leader: Email in `area_leaders_YYYY` → area-specific access
   - Public: Unauthenticated → registration only

### Area Management
- 24 count areas (A-X, no Y) with static configuration
- Interactive map with clickable polygons synced to dropdown
- Auto-assignment to areas needing volunteers ("ANYWHERE" preference)
- No capacity limits - areas accommodate varying numbers

## Important Constraints

### Data Integrity
- Current year: full read/write access
- Historical years: read-only access (UI enforced + validation)
- Email deduplication across years (most recent data wins)
- Explicit year field in all records for data integrity

### Security
- Admin whitelist in version control (`config/admins.py`)
- Area leaders scoped to assigned areas only
- Historical data protection (read-only)
- CSRF protection on authenticated forms

### Mobile-First Design
- Primary usage via mobile devices
- Responsive Bootstrap layout
- Touch-optimized map interactions
- Graceful degradation if map fails

## Environment Setup

### Required Environment Variables
- `GOOGLE_CLOUD_PROJECT=vancouver-cbc-registration` (for Cloud Run)
- `SECRET_KEY` (Flask sessions, defaults to dev key)

### Google Cloud Services
- Cloud Run (application hosting)
- Firestore (data persistence)
- OAuth 2.0 (authentication)

## Testing and Validation

The application uses production Firestore - test carefully:
- Use test deployment: `cbc-test.naturevancouver.ca`
- Production deployment: `cbc-registration.naturevancouver.ca`
- Monitor with: `gcloud run services logs read SERVICE_NAME --region=us-west1`

## Common Development Tasks

### Adding New Areas
1. Update `config/areas.py` with new area definition
2. Update `static/data/area_boundaries.json` with polygon coordinates
3. Test map rendering and form dropdown

### Managing Admin Access
1. Edit `config/admins.py` email list
2. Redeploy application
3. Test authentication with new admin account

### Year Transition Setup
1. Models automatically create new year collections
2. Admin interface includes year selector
3. Historical data remains accessible read-only

### Debugging Firestore Issues
1. Check service account permissions
2. Verify `GOOGLE_CLOUD_PROJECT` environment variable
3. Monitor Cloud Run logs for connection errors
4. Test with: `gcloud firestore databases list`