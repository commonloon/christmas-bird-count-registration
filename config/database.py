# Database configuration helper
import os
from google.cloud import firestore


def get_database_config():
    """Get database configuration based on environment."""
    flask_env = os.environ.get('FLASK_ENV', 'development')
    test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'
    
    # Determine database ID based on environment
    if flask_env == 'production' and not test_mode:
        database_id = 'cbc-register'  # Production database
    else:
        database_id = 'cbc-test'      # Test/development database
    
    return database_id


def get_firestore_client():
    """Get Firestore client configured for the appropriate database."""
    database_id = get_database_config()
    
    # Create client with specific database
    client = firestore.Client(database=database_id)
    
    return client, database_id