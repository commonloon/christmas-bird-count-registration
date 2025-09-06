from flask import Blueprint, render_template

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/')
def dashboard():
    """Admin dashboard - under construction."""
    return "<h1>Admin Dashboard</h1><p>Under construction</p>"

@admin_bp.route('/participants')
def participants():
    """View and manage all participants - under construction."""
    return "<h1>Participants Management</h1><p>Under construction</p>"

@admin_bp.route('/area/<area_code>')
def area_detail(area_code):
    """View participants for a specific area - under construction."""
    return f"<h1>Area {area_code} Details</h1><p>Under construction</p>"

@admin_bp.route('/delete_participant/<participant_id>', methods=['POST'])
def delete_participant(participant_id):
    """Delete a participant - under construction."""
    return f"<h1>Delete Participant</h1><p>Under construction - would delete participant {participant_id}</p>"

@admin_bp.route('/export_csv')
def export_csv():
    """Export all participants as CSV - under construction."""
    return "<h1>Export CSV</h1><p>Under construction</p>"