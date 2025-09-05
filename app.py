# app.py - Flask application entry point
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from google.cloud import firestore
import os
from datetime import datetime
import json

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Initialize Firestore client
try:
    db = firestore.Client()
except Exception as e:
    print(f"Warning: Could not initialize Firestore client: {e}")
    db = None

# Import route modules
from routes.main import main_bp
from routes.admin import admin_bp
from routes.api import api_bp

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(api_bp, url_prefix='/api')

# Load area boundaries data
def load_area_boundaries():
    """Load area boundary data from JSON file."""
    try:
        with open('static/data/area_boundaries.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: Area boundaries file not found")
        return []

# Make area boundaries available to templates
@app.context_processor
def inject_areas():
    return {'areas': load_area_boundaries()}

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