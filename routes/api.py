from flask import Blueprint, jsonify, request
from google.cloud import firestore
from models.participant import ParticipantModel
import json

api_bp = Blueprint('api', __name__)

# Initialize Firestore and models
try:
    db = firestore.Client()
    participant_model = ParticipantModel(db)
except Exception as e:
    print(f"Warning: Could not initialize Firestore: {e}")
    db = None
    participant_model = None


@api_bp.route('/areas')
def get_areas():
    """Get all areas with current registration counts for map display."""
    try:
        # Load area boundaries
        with open('static/data/area_boundaries.json', 'r') as f:
            areas = json.load(f)

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

        return jsonify(areas)

    except FileNotFoundError:
        return jsonify({'error': 'Area boundaries not found'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/area_counts')
def get_area_counts():
    """Get current registration counts by area."""
    if not participant_model:
        return jsonify({'error': 'Database unavailable'}), 500

    try:
        counts = participant_model.get_area_counts()
        return jsonify(counts)
    except Exception as e:
        return jsonify({'error': str(e)}), 500