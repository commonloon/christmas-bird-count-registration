# Updated by Claude AI on 2025-09-12
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, g
from google.cloud import firestore
from config.database import get_firestore_client
from models.participant import ParticipantModel
from routes.auth import require_leader
from config.areas import get_area_info, get_all_areas
from datetime import datetime
import csv
import io

# Create blueprint
leader_bp = Blueprint('leader', __name__)

@leader_bp.before_request
def load_leader_areas():
    """Load the areas this leader is responsible for."""
    if hasattr(g, 'user_email'):
        try:
            db, _ = get_firestore_client()
            current_year = datetime.now().year
            leader_model = ParticipantModel(db, current_year)
            # For auth purposes, check all leaders with this email (family sharing supported)
            all_leaders = leader_model.get_leaders()
            g.leader_areas = []
            for leader in all_leaders:
                if leader.get('email') == g.user_email and leader.get('assigned_area_leader'):
                    g.leader_areas.append(leader.get('assigned_area_leader'))
        except Exception as e:
            g.leader_areas = []
            flash(f"Error loading leader areas: {e}", 'error')
    else:
        g.leader_areas = []

@leader_bp.route('/')
@require_leader
def dashboard():
    """Area leader dashboard showing their areas and participant counts."""
    try:
        db, _ = get_firestore_client()
        current_year = datetime.now().year
        participant_model = ParticipantModel(db, current_year)
        
        # Get statistics for leader's areas
        area_stats = {}
        for area_code in g.leader_areas:
            participants = participant_model.get_participants_by_area(area_code)
            area_info = get_area_info(area_code)
            
            area_stats[area_code] = {
                'name': area_info['name'],
                'participant_count': len(participants),
                'recent_registrations': [p for p in participants if 
                                       (datetime.now() - p.get('created_at', datetime.min)).days <= 7]
            }
        
        return render_template('leader/dashboard.html', 
                             area_stats=area_stats,
                             current_year=current_year)
        
    except Exception as e:
        flash(f"Error loading dashboard: {e}", 'error')
        return render_template('leader/dashboard.html', 
                             area_stats={},
                             current_year=datetime.now().year)

@leader_bp.route('/area/<area_code>')
@require_leader
def view_area(area_code):
    """View participants for a specific area (current year)."""
    if area_code not in g.leader_areas:
        flash("You don't have access to that area.", 'error')
        return redirect(url_for('leader.dashboard'))
    
    try:
        db, _ = get_firestore_client()
        current_year = datetime.now().year
        participant_model = ParticipantModel(db, current_year)
        
        participants = participant_model.get_participants_by_area(area_code)
        area_info = get_area_info(area_code)
        
        return render_template('leader/area_detail.html',
                             participants=participants,
                             area_code=area_code,
                             area_info=area_info,
                             current_year=current_year)
        
    except Exception as e:
        flash(f"Error loading area data: {e}", 'error')
        return redirect(url_for('leader.dashboard'))

@leader_bp.route('/area/<area_code>/history')
@require_leader
def view_area_history(area_code):
    """View historical participants for a specific area."""
    if area_code not in g.leader_areas:
        flash("You don't have access to that area.", 'error')
        return redirect(url_for('leader.dashboard'))
    
    try:
        db, _ = get_firestore_client()
        current_year = datetime.now().year
        participant_model = ParticipantModel(db, current_year)
        
        # Get historical participants (3 years back by default)
        years_back = int(request.args.get('years', 3))
        historical_participants = participant_model.get_historical_participants(area_code, years_back)
        
        area_info = get_area_info(area_code)
        
        return render_template('leader/area_history.html',
                             participants=historical_participants,
                             area_code=area_code,
                             area_info=area_info,
                             years_back=years_back,
                             current_year=current_year)
        
    except Exception as e:
        flash(f"Error loading historical data: {e}", 'error')
        return redirect(url_for('leader.dashboard'))

@leader_bp.route('/area/<area_code>/export')
@require_leader
def export_area_contacts(area_code):
    """Export contact information for an area (current year)."""
    if area_code not in g.leader_areas:
        flash("You don't have access to that area.", 'error')
        return redirect(url_for('leader.dashboard'))
    
    try:
        db, _ = get_firestore_client()
        current_year = datetime.now().year
        participant_model = ParticipantModel(db, current_year)
        
        participants = participant_model.get_participants_by_area(area_code)
        area_info = get_area_info(area_code)
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['First Name', 'Last Name', 'Email', 'Phone', 
                        'Skill Level', 'Experience', 'Leadership Interest', 'Scribe Interest',
                        'Registration Date'])
        
        # Write participant data
        for participant in participants:
            writer.writerow([
                participant.get('first_name', ''),
                participant.get('last_name', ''),
                participant.get('email', ''),
                participant.get('phone', ''),
                participant.get('skill_level', ''),
                participant.get('experience', ''),
                'Yes' if participant.get('interested_in_leadership', False) else 'No',
                'Yes' if participant.get('interested_in_scribe', False) else 'No',
                participant.get('created_at', '').strftime('%Y-%m-%d') if participant.get('created_at') else ''
            ])
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=area_{area_code}_participants_{current_year}.csv'
        
        return response
        
    except Exception as e:
        flash(f"Error exporting data: {e}", 'error')
        return redirect(url_for('leader.view_area', area_code=area_code))

@leader_bp.route('/area/<area_code>/export-history')
@require_leader
def export_area_history(area_code):
    """Export historical contact information for an area."""
    if area_code not in g.leader_areas:
        flash("You don't have access to that area.", 'error')
        return redirect(url_for('leader.dashboard'))
    
    try:
        db, _ = get_firestore_client()
        current_year = datetime.now().year
        participant_model = ParticipantModel(db, current_year)
        
        # Get historical participants
        years_back = int(request.args.get('years', 3))
        participants = participant_model.get_historical_participants(area_code, years_back)
        area_info = get_area_info(area_code)
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['First Name', 'Last Name', 'Email', 'Phone', 
                        'Skill Level', 'Experience', 'Leadership Interest', 'Scribe Interest',
                        'Most Recent Year', 'Registration Date'])
        
        # Write participant data
        for participant in participants:
            writer.writerow([
                participant.get('first_name', ''),
                participant.get('last_name', ''),
                participant.get('email', ''),
                participant.get('phone', ''),
                participant.get('skill_level', ''),
                participant.get('experience', ''),
                'Yes' if participant.get('interested_in_leadership', False) else 'No',
                'Yes' if participant.get('interested_in_scribe', False) else 'No',
                participant.get('year', ''),
                participant.get('created_at', '').strftime('%Y-%m-%d') if participant.get('created_at') else ''
            ])
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=area_{area_code}_history_{years_back}years.csv'
        
        return response
        
    except Exception as e:
        flash(f"Error exporting historical data: {e}", 'error')
        return redirect(url_for('leader.view_area_history', area_code=area_code))

@leader_bp.route('/profile')
@require_leader
def profile():
    """Area leader profile and settings."""
    try:
        db, _ = get_firestore_client()
        current_year = datetime.now().year
        leader_model = ParticipantModel(db, current_year)

        # Get leader information (use first result for email-based lookup)
        all_leaders = leader_model.get_leaders()
        leader_info = None
        for leader in all_leaders:
            if leader.get('email') == g.user_email:
                leader_info = leader
                break
        
        return render_template('leader/profile.html',
                             leader_info=leader_info,
                             leader_areas=g.leader_areas,
                             current_year=current_year)
        
    except Exception as e:
        flash(f"Error loading profile: {e}", 'error')
        return render_template('leader/profile.html',
                             leader_info={},
                             leader_areas=g.leader_areas,
                             current_year=datetime.now().year)