# Updated by Claude AI on 2026-08-31
from flask import Blueprint, jsonify, request, g, Response
from config.database import get_db_session
from config.circles import get_default_circle_slug
from models.circle import CircleModel, CircleAreaModel
from models.db import Circle
from models.participant import ParticipantModel
from models.area_signup_type import AreaSignupTypeModel
from services.limiter import limiter
from config.rate_limits import RATE_LIMITS

api_bp = Blueprint('api', __name__)


@api_bp.route('/circles/<slug>/contact')
@limiter.limit(RATE_LIMITS['api_general'])
def get_circle_contact(slug):
    """Get a circle's contact email on demand.

    Deliberately not included in the landing page's initial HTML/JSON payload -
    bots scraping a plaintext contact address from a public page caused a real
    spam problem previously, so the landing page's "show contact" button fetches
    it here instead, one circle at a time, rather than shipping every circle's
    email to every visitor up front.
    """
    circle = CircleModel(get_db_session()).get_by_slug(slug)
    if not circle:
        return jsonify({'error': 'Circle not found'}), 404
    return jsonify({'contact': circle['count_contact']})


@api_bp.route('/circles/<slug>/logo')
@limiter.limit(RATE_LIMITS['api_general'])
def get_circle_logo(slug):
    """Serve a circle's uploaded logo image, or 404 if it hasn't set one - public,
    no auth, since logos are embedded in public registration pages and in emails
    opened by anyone.

    Circle.logo_data is a deferred column (see models/db.py) - queried directly
    here rather than through CircleModel.get_by_slug()'s dict path, which
    deliberately excludes it to keep it out of every ordinary request's default
    SELECT. Supports conditional GETs (If-Modified-Since, keyed off the circle's
    updated_at) so an unchanged logo costs one indexed row lookup on repeat
    views, not a full blob re-transfer.
    """
    db = get_db_session()
    row = (
        db.query(Circle.logo_data, Circle.logo_content_type, Circle.updated_at)
        .filter_by(slug=slug)
        .first()
    )
    if not row or not row.logo_data:
        return jsonify({'error': 'No logo set for this circle'}), 404

    logo_data, content_type, updated_at = row
    last_modified = updated_at.replace(microsecond=0)  # HTTP dates have second precision

    response = Response(status=304) if (
        request.if_modified_since and last_modified <= request.if_modified_since
    ) else Response(logo_data, mimetype=content_type)
    response.last_modified = last_modified
    response.cache_control.max_age = 86400  # 1 day - logos change rarely; re-uploading
    # bumps updated_at, which invalidates stale client caches via revalidation above
    return response


@api_bp.route('/areas')
@limiter.limit(RATE_LIMITS['api_general'])
def get_areas():
    """Get all areas with current registration counts and signup type info for map display."""
    try:
        # Load area boundaries and map configuration
        circle_slug = getattr(g, 'circle_slug', None) or get_default_circle_slug()
        db = get_db_session()
        boundary_data = CircleAreaModel(db).get_boundary_data(circle_slug)
        areas = boundary_data['areas']
        map_config = boundary_data['map_config']

        participant_model = ParticipantModel(db)
        signup_type_model = AreaSignupTypeModel(db)

        # Get current registration counts
        try:
            area_counts = participant_model.get_area_counts()
        except Exception as e:
            print(f"Warning: Could not get area counts: {e}")
            area_counts = {}

        # Get signup type information
        try:
            signup_types = signup_type_model.get_all_signup_types()
        except Exception as e:
            print(f"Warning: Could not get signup types: {e}")
            signup_types = {}

        # Add current counts and signup type to area data
        for area in areas:
            area_code = area['letter_code']
            area['current_count'] = area_counts.get(area_code, 0)

            # Add signup type information
            if area_code in signup_types:
                area['admin_assignment_only'] = signup_types[area_code].get('admin_assignment_only', False)
            else:
                area['admin_assignment_only'] = False

            # Determine availability status based on relative counts
            all_counts = list(area_counts.values()) if area_counts else [0]
            avg_count = sum(all_counts) / len(all_counts) if all_counts else 0

            if area['current_count'] <= avg_count * 0.7:
                area['availability'] = 'high'
            elif area['current_count'] <= avg_count * 1.3:
                area['availability'] = 'medium'
            else:
                area['availability'] = 'low'

        return jsonify({'areas': areas, 'map_config': map_config})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/area_counts')
@limiter.limit(RATE_LIMITS['api_general'])
def get_area_counts():
    """Get current registration counts by area."""
    try:
        participant_model = ParticipantModel(get_db_session())
        counts = participant_model.get_area_counts()
        return jsonify(counts)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/areas_needing_leaders')
@limiter.limit(RATE_LIMITS['api_general'])
def get_areas_needing_leaders():
    """Get all areas with leadership status for map display."""
    try:
        # Load area boundaries and map configuration
        circle_slug = getattr(g, 'circle_slug', None) or get_default_circle_slug()
        boundary_data = CircleAreaModel(get_db_session()).get_boundary_data(circle_slug)
        areas = boundary_data['areas']
        map_config = boundary_data['map_config']

        # Get areas without leaders from current year
        from datetime import datetime

        try:
            current_year = datetime.now().year
            current_year_participant_model = ParticipantModel(get_db_session(), current_year)
            areas_without_leaders = current_year_participant_model.get_areas_without_leaders()
        except Exception as e:
            print(f"Warning: Could not get areas without leaders: {e}")
            areas_without_leaders = []

        return jsonify({
            'areas': areas,
            'areas_without_leaders': areas_without_leaders,
            'map_config': map_config,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
