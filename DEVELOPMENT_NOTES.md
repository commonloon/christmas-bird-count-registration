# DEVELOPMENT NOTES - Christmas Bird Count Registration App

## COMPLETED TASKS (Most Recent Sessions)

### Admin Interface Implementation ✅
- **Security Fix**: Removed public admin link from base template 
- **OAuth Authentication**: Fixed Google Identity Services integration with proper client configuration
- **Complete Admin Templates**: Created all admin interface templates:
  - Dashboard with statistics and year selector
  - Participant management with delete functionality 
  - Unassigned participant assignment tools
  - Area detail views with team composition analysis
  - Leader management interface with manual entry and participant promotion

### Leader Management System ✅ 
- **Business Rules Implemented**:
  - Multiple leaders per area allowed
  - One area maximum per leader (enforced)
  - Manual leader entry as primary workflow (no participant registration required)
  - Required fields: first_name, last_name, email, cell_phone
- **Manual Leader Entry**: Complete form and backend with validation
- **Auto-Assignment Logic**: Leaders who register as participants are automatically assigned to their led area

### Leader Management UI Fixes ✅ 
- **Dropdown Population Fixed**: Area dropdowns now properly display area codes and names instead of "-"
- **Backend Validation Enhanced**: Added proper validation, error handling, and business rule enforcement
- **Interactive Map Implementation**: 
  - New map display showing areas needing leaders (red) vs areas with leaders (green)
  - Leader names appear in tooltips when hovering over areas with leaders
  - Map legend showing counts of areas with/without leaders
  - Click interactions for areas needing leaders
  - Enhanced visual feedback and user experience

### Inline Edit/Delete Functionality ✅ (Recent Session)
- **Inline Table Editing**: Complete edit/delete functionality for leaders table
  - Edit button (pencil icon) enables simultaneous editing of all fields
  - Area dropdown, name fields, email, and phone become editable inline
  - Save button with comprehensive validation and business rule enforcement
  - Delete button (trash icon) with confirmation modal (no reason required)
- **Live Map Updates**: Client-side data management for real-time map refresh
  - `window.refreshLeadersMap()` function for map updates after operations
  - Local `window.leaderData` synchronization without server API calls
  - Cached area boundary data for efficient refreshes
  - Immediate visual feedback: map colors and tooltips update instantly
- **Bug Fixes Applied**: Fixed dictionary access errors in add_leader route
  - Corrected `.leader_email` to `['leader_email']` attribute vs dictionary access
  - Fixed duplicate leader validation logic

### Technical Files Created/Modified ✅
- `static/js/leaders-map.js`: Interactive map with live refresh capability and client-side data management
  - Added `window.refreshLeadersMap()`, `clearMapLayers()`, `calculateAreasNeedingLeaders()`
  - Cached area boundary data for efficient refreshes
- `templates/admin/leaders.html`: Complete inline editing interface with dual display/edit modes
  - Bootstrap Icons integration for edit/delete buttons
  - Inline form controls with validation and AJAX operations
  - Client-side `window.leaderData` synchronization functions
- `templates/base.html`: Added Bootstrap Icons CDN for consistent iconography
- `routes/admin.py`: Enhanced with edit_leader and delete_leader JSON API endpoints
  - Fixed dictionary access bugs in add_leader route
  - Comprehensive validation and participant record synchronization
- `models/participant.py`: Added `get_participants_by_email()` method for leader-participant sync
- `routes/api.py`: Added `/areas_needing_leaders` endpoint (used for initial data caching)

## CURRENT STATE

### Working Features
1. **Public Registration**: Form with interactive map, email validation, leadership interest tracking
2. **Admin Authentication**: Google OAuth with email whitelist working properly  
3. **Complete Admin Interface**: Full CRUD operations for participants and leaders
4. **Enhanced Leader Management**: 
   - Manual entry with working dropdowns and validation
   - Participant-to-leader promotion from potential leaders list
   - Interactive map showing leadership gaps visually with live updates
   - Leader names displayed on map hover with real-time refresh
   - **Inline edit/delete functionality**: Direct table editing with validation
   - Business rule enforcement (one area per leader) with proper error handling
   - Client-side map updates without server round-trips
5. **Year-Based Data**: All models handle year-specific collections properly
6. **Live User Experience**: Immediate visual feedback for all leader management operations

### Database & System Infrastructure ✅ (Recent Session)
- **Multi-Database Architecture**: Environment-specific Firestore databases implemented
  - `cbc-test` database for development/testing environment
  - `cbc-register` database for production environment
  - Automatic database selection based on `FLASK_ENV` and `TEST_MODE` environment variables
  - Database configuration helper: `config/database.py`
- **Automated Database Setup**: `utils/setup_databases.py` script with index creation
  - Creates both databases with proper Firestore indexes automatically
  - Handles "already exists" cases gracefully
  - Composite index creation for optimal query performance
  - Command line options: `--dry-run`, `--skip-indexes`, `--force`
- **Terminology Consistency**: Standardized on "UNASSIGNED" throughout system
  - Replaced all "ANYWHERE" references with "UNASSIGNED" 
  - Updated templates, JavaScript, and configuration
  - Fixed area capacity overview to show actual participant counts
- **Context-Aware Navigation**: Admin templates now show appropriate branding
  - "Vancouver CBC Registration Admin" for admin pages linking to admin dashboard
  - "Vancouver CBC Registration" for public pages linking to registration
  - Automatic detection using `request.endpoint.startswith('admin.')`

### NEXT PRIORITY: Email Automation System 🚧
**Current Task**: Implement automated email notifications to area leaders

#### **Email System Requirements (from EMAIL.md):**
1. **Twice-Daily Team Updates**:
   - Recipients: Area leaders when team composition changes
   - Subject: "Team Update for Vancouver CBC Area X"
   - Content: New members, removed members, complete current team roster
   - Triggers: Participant additions, removals, area reassignments, email changes

2. **Weekly Team Summary (No Changes)**:
   - Recipients: Area leaders with no team changes in past week
   - When: Every Friday at 11pm
   - Subject: "Weekly Team Summary for Vancouver CBC Area X"
   - Content: "No changes" note + complete team roster with all details

3. **Daily Admin Digest**:
   - Recipients: All admins (from `config/admins.py`)
   - Subject: "Vancouver CBC Participants not assigned to a count area"
   - Content: Link to admin/unassigned page + list of unassigned participants

#### **Test Email Trigger Implementation (Ready to Code):**
**Requirement**: Add test buttons to admin dashboard (test server only) for on-demand email testing

**Files to Modify**:
1. **`routes/admin.py`** - Add test trigger routes:
   ```python
   @admin_bp.route('/test/trigger-team-updates', methods=['POST'])
   @require_admin
   def test_trigger_team_updates():
       # Environment check: only work on test server
       if not is_test_server():
           return jsonify({'error': 'Test triggers only available on test server'}), 403
       
       # Generate twice-daily team updates for all areas with leaders
       results = generate_team_update_emails()
       return jsonify({'success': True, 'message': f'Team update emails generated: {results}'})
       
   @admin_bp.route('/test/trigger-weekly-summaries', methods=['POST'])
   @require_admin 
   def test_trigger_weekly_summaries():
       # Environment check: only work on test server
       if not is_test_server():
           return jsonify({'error': 'Test triggers only available on test server'}), 403
       
       # Generate weekly summaries for all areas with leaders
       results = generate_weekly_summary_emails()
       return jsonify({'success': True, 'message': f'Weekly summary emails generated: {results}'})
       
   @admin_bp.route('/test/trigger-admin-digest', methods=['POST'])
   @require_admin
   def test_trigger_admin_digest():
       # Environment check: only work on test server
       if not is_test_server():
           return jsonify({'error': 'Test triggers only available on test server'}), 403
       
       # Generate admin digest
       results = generate_admin_digest_email()
       return jsonify({'success': True, 'message': f'Admin digest email generated: {results}'})
   ```

2. **`templates/admin/dashboard.html`** - Add test buttons section:
   ```html
   {% if is_test_server %}
   <div class="card mt-4">
       <div class="card-header">
           <h5 class="mb-0"><i class="bi bi-envelope-paper"></i> Email Testing (Test Server Only)</h5>
       </div>
       <div class="card-body">
           <p class="text-muted mb-3">Trigger email generation on demand for testing purposes. All emails will be sent to birdcount@naturevancouver.ca on the test server.</p>
           
           <div class="d-flex flex-wrap gap-2">
               <button type="button" class="btn btn-outline-primary" onclick="triggerTestEmail('team-updates')">
                   <i class="bi bi-people"></i> Trigger Team Updates
               </button>
               <button type="button" class="btn btn-outline-info" onclick="triggerTestEmail('weekly-summaries')">
                   <i class="bi bi-calendar-week"></i> Trigger Weekly Summaries
               </button>
               <button type="button" class="btn btn-outline-warning" onclick="triggerTestEmail('admin-digest')">
                   <i class="bi bi-person-gear"></i> Trigger Admin Digest
               </button>
           </div>
           
           <div id="test-email-results" class="mt-3" style="display: none;">
               <div class="alert alert-info">
                   <div class="d-flex align-items-center">
                       <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                       <span>Generating emails...</span>
                   </div>
               </div>
           </div>
       </div>
   </div>
   
   <script>
   function triggerTestEmail(emailType) {
       const resultsDiv = document.getElementById('test-email-results');
       resultsDiv.style.display = 'block';
       resultsDiv.innerHTML = '<div class="alert alert-info"><div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2"></div><span>Generating emails...</span></div></div>';
       
       const endpoints = {
           'team-updates': '/admin/test/trigger-team-updates',
           'weekly-summaries': '/admin/test/trigger-weekly-summaries', 
           'admin-digest': '/admin/test/trigger-admin-digest'
       };
       
       fetch(endpoints[emailType], {
           method: 'POST',
           headers: {
               'Content-Type': 'application/json'
           }
       })
       .then(response => response.json())
       .then(data => {
           if (data.success) {
               resultsDiv.innerHTML = `<div class="alert alert-success"><i class="bi bi-check-circle"></i> ${data.message}</div>`;
           } else {
               resultsDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Error: ${data.error || 'Unknown error'}</div>`;
           }
       })
       .catch(error => {
           resultsDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Network error: ${error.message}</div>`;
       });
   }
   </script>
   {% endif %}
   ```

#### **Core Email Generation Functions (to be implemented):**

**Environment Detection Helper**:
```python
def is_test_server():
    """Detect if running on test server for email trigger functionality."""
    # Check environment variable first
    if os.getenv('TEST_MODE', '').lower() == 'true':
        return True
    
    # Check if domain contains 'test' for deployed test server
    if request and hasattr(request, 'host') and 'test' in request.host.lower():
        return True
        
    return False
```

**Email Generation Functions**:
```python
def generate_team_update_emails():
    """Generate twice-daily team update emails for areas with changes."""
    # 1. Pick timestamp before querying to prevent race conditions
    current_time = datetime.utcnow()
    
    # 2. Get all areas with leaders
    # 3. For each area, check for changes since last_email_sent
    # 4. Generate email content with new/removed/current members
    # 5. Send email (test mode: birdcount@naturevancouver.ca)
    # 6. Update last_email_sent timestamp
    
def generate_weekly_summary_emails():
    """Generate weekly summary emails for areas with no changes."""
    # 1. Every Friday at 11pm (or manual trigger on test)
    # 2. Get areas with leaders but no changes in past week
    # 3. Generate "no changes" email with complete roster
    # 4. Send to area leaders (test mode: birdcount@naturevancouver.ca)
    
def generate_admin_digest_email():
    """Generate daily admin digest with unassigned participants."""
    # 1. Get all unassigned participants
    # 2. Build email with link to admin/unassigned page
    # 3. Send to all admins from config/admins.py
    # 4. Test mode: send to birdcount@naturevancouver.ca
```

#### **Email Implementation Strategy:**
- **Race Condition Prevention**: Choose `last_email_sent` timestamp BEFORE querying begins, update AFTER email sent successfully
- **Change Detection**: Track area assignments, additions, removals, email address changes
- **Test Mode**: `cbc-test` server sends all emails to `birdcount@naturevancouver.ca`
- **Environment Detection**: Use `TEST_MODE=true` or domain contains 'test' for test server identification
- **Timestamp Management**: Store per-area `last_email_sent` values to prevent duplicates (duplicates acceptable, missed notifications are not)
- **Email Content**: Include environment-aware links (cbc-test.naturevancouver.ca vs cbc-registration.naturevancouver.ca)

#### **Implementation Files to Create:**
1. **`utils/email_generator.py`** - Core email generation logic
2. **`templates/emails/team_update.html`** - HTML email template for team updates
3. **`templates/emails/weekly_summary.html`** - HTML email template for weekly summaries  
4. **`templates/emails/admin_digest.html`** - HTML email template for admin digest
5. **`config/email_settings.py`** - Email configuration and SMTP settings

#### **Immediate Next Steps:**
1. Add test email trigger buttons to admin dashboard (test server only) ✅ Ready to implement
2. Create email generation functions for each email type
3. Implement change detection logic with proper timestamp handling
4. Create email templates with environment-aware links
5. Test email automation end-to-end on cbc-test server
6. Add scheduled triggers for production (Cloud Scheduler or similar)

### Other Priority Tasks
1. **Implement area leader interface** (`/leader` routes):
   - Leader-specific dashboard showing their area
   - Participant contact lists for their assigned area
   - Historical participant data access (3 years back)
   - Export functionality for recruitment emails

2. **Complete participant management enhancements**:
   - Participant editing functionality (beyond delete)
   - Bulk participant operations
   - Advanced assignment tools
   - Enhanced search and filtering capabilities

## TECHNICAL CONTEXT

### Key Implementation Details
- **Database**: Google Firestore with year-based collections
- **Authentication**: Google Identity Services (not redirect flow) with Secret Manager credentials
- **Deployment**: Google Cloud Run in us-west1 region
- **Business Logic**: Auto-assignment when leaders register, one-area-per-leader rule enforcement
- **Maps**: Two separate Leaflet.js implementations with live refresh capability
  - Registration map: Area selection for participants
  - Leaders map: Real-time leadership status with client-side data management
- **Frontend Architecture**: Bootstrap 5 + Bootstrap Icons + Leaflet.js with AJAX operations
- **Data Synchronization**: Client-side `window.leaderData` management for instant UI updates

### Critical Files Structure
```
routes/
  admin.py           # Complete admin interface with inline edit/delete functionality
    - edit_leader: JSON API for inline editing with validation
    - delete_leader: JSON API for leader deletion with participant sync
    - add_leader: Manual leader entry (fixed dictionary access bugs)
  api.py            # JSON endpoints for map data caching
  
static/js/
  map.js            # Registration page interactive map
  leaders-map.js    # Leaders page map with live refresh and client-side data management
    - window.refreshLeadersMap(): Main refresh function
    - clearMapLayers(): Remove existing polygons for redraw
    - calculateAreasNeedingLeaders(): Client-side leadership calculation
  
templates/admin/
  leaders.html      # Inline editing interface with dual display/edit modes
    - Bootstrap Icons for edit/delete buttons
    - AJAX operations with window.leaderData synchronization
  
templates/base.html # Bootstrap Icons CDN integration

models/
  area_leader.py    # Business rule enforcement and validation
  participant.py    # Enhanced with get_participants_by_email() for sync
```

### Recent Bug Fixes Applied
1. **Dictionary Access Errors**: Fixed add_leader route treating dictionaries as objects
   - Changed `leader.leader_email` → `leader['leader_email']`
   - Changed `leader_areas[0].area_code` → `leader_areas[0]['area_code']`
2. **Template Name Field Population**: Fixed edit button clearing first/last name fields
   - Added intelligent handling of both `first_name`/`last_name` and `leader_name` data structures
   - Template now splits combined names when separate fields are unavailable
3. **Template Logic**: Fixed area dropdown rendering to use actual area data structure
4. **Backend Validation**: Added missing required field validation and area code validation
5. **Error Handling**: Proper logging and user feedback for all error conditions
6. **Data Consistency**: Enhanced business rule enforcement preventing duplicate assignments

## OAUTH SETUP STATUS ✅
- Google OAuth client configured and working
- Published consent screen (not in testing mode)  
- Credentials stored in Google Secret Manager
- JavaScript origins configured, redirect URIs removed
- Admin authentication fully functional

## DEVELOPMENT STATUS
The application has core functionality implemented:
- ✅ Public registration with map-based area selection
- ✅ Admin authentication and interface
- ✅ Leader management with interactive map
- ✅ Year-based data architecture
- ✅ Enhanced user experience and validation

**Still in active development** - additional testing and refinement needed before deployment.
