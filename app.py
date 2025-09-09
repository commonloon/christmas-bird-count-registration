# app.py - Flask application entry point
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, g
from google.cloud import firestore
from config.database import get_firestore_client
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
from datetime import datetime
import json
import logging

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OAuth configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

# Initialize Firestore client
try:
    db, database_id = get_firestore_client()
    logger.info(f"Firestore client initialized successfully for database: {database_id}")
except Exception as e:
    logger.error(f"Warning: Could not initialize Firestore client: {e}")
    db = None

# Import route modules
from routes.main import main_bp
from routes.admin import admin_bp
from routes.leader import leader_bp
from routes.api import api_bp
from routes.auth import auth_bp, init_auth

# Initialize authentication
init_auth(app)

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(leader_bp, url_prefix='/leader')
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/auth')

# Load area boundaries data
def load_area_boundaries():
    """Load area boundary data from JSON file."""
    try:
        with open('static/data/area_boundaries.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: Area boundaries file not found")
        return []

# Make area boundaries and common data available to templates
@app.context_processor
def inject_common_data():
    return {
        'areas': load_area_boundaries(),
        'current_year': datetime.now().year,
        'user_role': getattr(g, 'user_role', 'public'),
        'user_email': getattr(g, 'user_email', None),
        'is_authenticated': 'user_email' in session
    }

# Before request handler for authentication context
@app.before_request
def load_user():
    """Load user information into g context for templates."""
    if 'user_email' in session:
        g.user_email = session['user_email']
        g.user_name = session.get('user_name', '')
        g.user_role = session.get('user_role', 'public')
    else:
        g.user_email = None
        g.user_name = None  
        g.user_role = 'public'

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    # Development server - don't use in production
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))