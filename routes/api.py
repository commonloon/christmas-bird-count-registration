# Updated by Claude AI on 2025-10-16
from flask import Blueprint, jsonify, request
from google.cloud import firestore
from config.database import get_firestore_client
from models.participant import ParticipantModel
from services.limiter import limiter
from config.rate_limits import RATE_LIMITS
import json

api_bp = Blueprint('api', __name__)

# Initialize Firestore and models
try:
    db, _ = get_firestore_client()
    participant_model = ParticipantModel(db)
except Exception as e:
    print(f"Warning: Could not initialize Firestore: {e}")
    db = None
    participant_model = None


@api_bp.route('/areas')
@limiter.limit(RATE_LIMITS['api_general'])
def get_areas():
    """Get all areas with current registration counts for map display."""
    try:
        # Load area boundaries and map configuration
        with open('static/data/area_boundaries.json', 'r') as f:
            data = json.load(f)

        # Handle both old format (array) and new format (object with map_config)
        if isinstance(data, dict) and 'areas' in data:
            areas = data['areas']
            map_config = data.get('map_config', {})
        else:
            # Old format - just array of areas
            areas = data
            map_config = {}

        # Get current registration counts
        if participant_model:
            area_counts = participant_model.get_area_counts()
        else:
            area_counts = {}

        # Add current counts to area data
        for area in areas:
            area_code = area['letter_code']
            area['current_count'] = area_counts.get(area_code, 0)

            # Determine availability status based on relative counts
            all_counts = list(area_counts.values()) if area_counts else [0]
            avg_count = sum(all_counts) / len(all_counts) if all_counts else 0

            if area['current_count'] <= avg_count * 0.7:
                area['availability'] = 'high'
            elif area['current_count'] <= avg_count * 1.3:
                area['availability'] = 'medium'
            else:
                area['availability'] = 'low'

        # Return areas with map configuration
        return jsonify({
            'areas': areas,
            'map_config': map_config
        })

    except FileNotFoundError:
        return jsonify({'error': 'Area boundaries not found'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/area_counts')
@limiter.limit(RATE_LIMITS['api_general'])
def get_area_counts():
    """Get current registration counts by area."""
    if not participant_model:
        return jsonify({'error': 'Database unavailable'}), 500

    try:
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
        with open('static/data/area_boundaries.json', 'r') as f:
            data = json.load(f)

        # Handle both old format (array) and new format (object with map_config)
        if isinstance(data, dict) and 'areas' in data:
            areas = data['areas']
            map_config = data.get('map_config', {})
        else:
            # Old format - just array of areas
            areas = data
            map_config = {}

        # Get areas without leaders from current year
        from datetime import datetime

        if db:
            current_year = datetime.now().year
            current_year_participant_model = ParticipantModel(db, current_year)
            areas_without_leaders = current_year_participant_model.get_areas_without_leaders()
        else:
            areas_without_leaders = []

        return jsonify({
            'areas': areas,
            'areas_without_leaders': areas_without_leaders,
            'map_config': map_config
        })

    except FileNotFoundError:
        return jsonify({'error': 'Area boundaries not found'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500