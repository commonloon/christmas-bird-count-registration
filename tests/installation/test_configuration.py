"""
Phase 1: Configuration Validation Tests
Updated by Claude AI on 2025-10-18

These tests validate that all configuration files are properly set up for a
new Christmas Bird Count installation. They are designed to be portable and
work with any organization's configuration (different area codes, counts, etc.).

No hardcoded values - all validation is dynamic based on config/*.py files.
"""

import pytest
import os
import json
import re
from datetime import datetime

from config.areas import get_public_areas, get_all_areas, AREA_CONFIG
from config.organization import get_organization_variables
from config.cloud import (
    TEST_BASE_URL, PRODUCTION_BASE_URL,
    TEST_DATABASE, PRODUCTION_DATABASE,
    GCP_PROJECT_ID, GCP_LOCATION
)


class TestConfigurationFiles:
    """Validate that all required configuration files exist and are complete."""

    def test_cloud_config_complete(self, installation_config):
        """Verify config/cloud.py has all required settings."""
        cloud_settings = {
            'GCP_PROJECT_ID': installation_config['gcp_project'],
            'GCP_LOCATION': installation_config['gcp_location'],
            'TEST_DATABASE': installation_config['test_db'],
            'PRODUCTION_DATABASE': installation_config['prod_db'],
            'TEST_BASE_URL': installation_config['test_url'],
            'PRODUCTION_BASE_URL': installation_config['prod_url'],
        }

        for setting_name, value in cloud_settings.items():
            assert value, (
                f"Missing or empty value for {setting_name} in config/cloud.py\n"
                f"Edit config/cloud.py to set this value for your GCP project."
            )

    def test_organization_config_complete(self, installation_config):
        """Verify config/organization.py has all required settings."""
        org_vars = installation_config['org_vars']

        required_settings = {
            'organization_name': 'Name of your bird count organization',
            'organization_contact': 'Main contact email for organization',
            'count_contact': 'Bird count coordinator email address',
            'count_event_name': 'Name of your bird count event (e.g., "Vancouver Christmas Bird Count")',
            'count_info_url': 'URL to bird count information page',
            'organization_website': 'Organization website URL',
        }

        for key, description in required_settings.items():
            assert key in org_vars, (
                f"Missing required setting in config/organization.py: {key}\n"
                f"Description: {description}\n"
                f"Add this setting to config/organization.py"
            )
            assert org_vars[key], (
                f"Empty value for {key} in config/organization.py\n"
                f"Description: {description}\n"
                f"Update config/organization.py with your organization's information."
            )

    def test_areas_config_complete(self, installation_config):
        """Verify config/areas.py has at least one area defined."""
        areas = installation_config['all_areas']

        assert len(areas) > 0, (
            "No areas defined in config/areas.py\n"
            "Run: python utils/parse_area_boundaries.py <your-kml-file.kml>\n"
            "This will generate area configuration from your KML boundaries."
        )

    def test_all_areas_have_required_fields(self, installation_config):
        """Verify each area in config/areas.py has all required fields."""
        required_fields = ['name', 'description', 'difficulty', 'terrain', 'admin_assignment_only']
        area_config = installation_config['area_config']

        for area_code in installation_config['all_areas']:
            config = area_config[area_code]
            missing_fields = [f for f in required_fields if f not in config]

            assert not missing_fields, (
                f"Area {area_code} missing required fields: {missing_fields}\n"
                f"Current fields: {list(config.keys())}\n"
                f"Update config/areas.py to include: {', '.join(missing_fields)}"
            )

    def test_area_boundaries_json_exists(self):
        """Verify static/data/area_boundaries.json exists."""
        path = 'static/data/area_boundaries.json'
        assert os.path.exists(path), (
            f"Missing {path}\n"
            f"Run: python utils/parse_area_boundaries.py <your-kml-file.kml>\n"
            f"This will generate the area boundaries JSON file for the map."
        )

    def test_area_boundaries_has_map_config(self, area_boundaries_data):
        """Verify area_boundaries.json contains map_config section."""
        assert area_boundaries_data is not None, (
            "area_boundaries.json not loaded (file missing)\n"
            "Run: python utils/parse_area_boundaries.py <your-kml-file.kml>"
        )

        assert 'map_config' in area_boundaries_data, (
            "area_boundaries.json missing 'map_config' section\n"
            "Re-run: python utils/parse_area_boundaries.py <your-kml-file.kml>\n"
            "The latest version automatically generates map_config with center and bounds."
        )

        map_config = area_boundaries_data['map_config']
        required_fields = ['center', 'bounds', 'zoom']

        for field in required_fields:
            assert field in map_config, (
                f"map_config missing required field: {field}\n"
                f"Re-run: python utils/parse_area_boundaries.py <your-kml-file.kml>"
            )

    def test_area_codes_consistent_with_json(self, installation_config, area_boundaries_data):
        """Verify area codes match between config/areas.py and area_boundaries.json."""
        assert area_boundaries_data is not None, "area_boundaries.json not found"

        # Get areas from config
        config_areas = set(installation_config['all_areas'])

        # Get areas from JSON
        json_areas = set(area['letter_code'] for area in area_boundaries_data['areas'])

        # Check for mismatches
        missing_in_json = config_areas - json_areas
        extra_in_json = json_areas - config_areas

        error_parts = []
        if missing_in_json:
            error_parts.append(
                f"Areas in config/areas.py but missing from area_boundaries.json: {sorted(missing_in_json)}"
            )
        if extra_in_json:
            error_parts.append(
                f"Areas in area_boundaries.json but not in config/areas.py: {sorted(extra_in_json)}"
            )

        if error_parts:
            error_msg = "\n".join(error_parts)
            error_msg += "\n\nRe-run: python utils/parse_area_boundaries.py <your-kml-file.kml>"
            error_msg += "\nThen update config/areas.py to match the areas in your KML file."
            assert False, error_msg


class TestConfigurationValidity:
    """Validate that configuration values are in valid formats."""

    def test_email_addresses_valid_format(self, installation_config):
        """Verify all email addresses in organization config are valid format."""
        org_vars = installation_config['org_vars']

        # Email fields that should be validated
        email_fields = ['organization_contact', 'count_contact', 'from_email', 'test_recipient']

        for field in email_fields:
            if field in org_vars and org_vars[field]:
                email = org_vars[field]

                # Basic email validation
                assert '@' in email, (
                    f"Invalid email format for {field}: {email}\n"
                    f"Email must contain '@' symbol.\n"
                    f"Update config/organization.py with a valid email address."
                )

                local, domain = email.rsplit('@', 1)

                assert local, (
                    f"Invalid email format for {field}: {email}\n"
                    f"Email missing local part (before @).\n"
                    f"Update config/organization.py"
                )

                assert domain and '.' in domain, (
                    f"Invalid email format for {field}: {email}\n"
                    f"Email domain must contain a period (e.g., 'example.com').\n"
                    f"Update config/organization.py"
                )

    def test_urls_valid_format(self, installation_config):
        """Verify all URLs in configuration are properly formatted."""
        urls_to_check = {
            'test_url': installation_config['test_url'],
            'prod_url': installation_config['prod_url'],
            'organization_website': installation_config['org_vars'].get('organization_website'),
            'count_info_url': installation_config['org_vars'].get('count_info_url'),
        }

        for url_name, url in urls_to_check.items():
            if url:
                assert url.startswith('http://') or url.startswith('https://'), (
                    f"Invalid URL format for {url_name}: {url}\n"
                    f"URL must start with 'http://' or 'https://'\n"
                    f"Update the corresponding config file."
                )

    def test_timezone_valid(self, installation_config):
        """Verify DISPLAY_TIMEZONE is a valid timezone string."""
        from datetime import datetime
        import pytz

        timezone_str = installation_config['org_vars'].get('display_timezone')

        if timezone_str:
            try:
                tz = pytz.timezone(timezone_str)
                # Try to use it
                datetime.now(tz)
            except pytz.UnknownTimeZoneError:
                pytest.fail(
                    f"Invalid timezone: {timezone_str}\n"
                    f"Must be a valid tz database timezone (e.g., 'America/Vancouver', 'America/New_York')\n"
                    f"See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones\n"
                    f"Update DISPLAY_TIMEZONE in config/organization.py"
                )

    def test_no_duplicate_area_codes(self, installation_config):
        """Verify area codes are unique (no duplicates in AREA_CONFIG)."""
        all_areas = installation_config['all_areas']
        unique_areas = set(all_areas)

        assert len(all_areas) == len(unique_areas), (
            f"Duplicate area codes found in config/areas.py\n"
            f"Total areas: {len(all_areas)}, Unique areas: {len(unique_areas)}\n"
            f"Each area code must be unique.\n"
            f"Check AREA_CONFIG in config/areas.py for duplicates."
        )

    def test_area_names_not_empty(self, installation_config):
        """Verify all areas have non-empty names."""
        area_config = installation_config['area_config']

        for area_code in installation_config['all_areas']:
            area_name = area_config[area_code].get('name', '')

            assert area_name and area_name.strip(), (
                f"Area {area_code} has empty or missing name in config/areas.py\n"
                f"Update AREA_CONFIG['{area_code}']['name'] with a descriptive name."
            )

    def test_difficulty_values_valid(self, installation_config):
        """Verify area difficulty values are from expected set."""
        valid_difficulties = {'Easy', 'Moderate', 'Difficult', 'Challenging', 'Expert'}
        area_config = installation_config['area_config']

        for area_code in installation_config['all_areas']:
            difficulty = area_config[area_code].get('difficulty', '')

            # Just warn if unusual, don't fail (different orgs might use different terms)
            if difficulty and difficulty not in valid_difficulties:
                print(
                    f"\nNote: Area {area_code} has difficulty '{difficulty}'\n"
                    f"Common values are: {sorted(valid_difficulties)}\n"
                    f"This is not an error, just informational."
                )


class TestConfigurationConsistency:
    """Validate consistency across different configuration files."""

    def test_database_names_not_empty(self, installation_config):
        """Verify TEST_DATABASE and PRODUCTION_DATABASE are configured."""
        test_db = installation_config['test_db']
        prod_db = installation_config['prod_db']

        assert test_db, (
            "TEST_DATABASE is empty in config/cloud.py\n"
            "Set TEST_DATABASE to your test Firestore database name\n"
            "(e.g., 'cbc-test', 'ladner-cbc-test')"
        )

        assert prod_db, (
            "PRODUCTION_DATABASE is empty in config/cloud.py\n"
            "Set PRODUCTION_DATABASE to your production Firestore database name\n"
            "(e.g., 'cbc-register', 'ladner-cbc-register')"
        )

    def test_gcp_project_id_set(self, installation_config):
        """Verify GCP_PROJECT_ID is configured."""
        project_id = installation_config['gcp_project']

        assert project_id, (
            "GCP_PROJECT_ID is empty in config/cloud.py\n"
            "Set GCP_PROJECT_ID to your Google Cloud Platform project ID"
        )

        # Check format (GCP project IDs have specific constraints)
        assert re.match(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$', project_id), (
            f"Invalid GCP project ID format: {project_id}\n"
            f"Project IDs must:\n"
            f"  - Start with a lowercase letter\n"
            f"  - Contain only lowercase letters, numbers, and hyphens\n"
            f"  - Be between 6 and 30 characters\n"
            f"  - End with a letter or number\n"
            f"Update GCP_PROJECT_ID in config/cloud.py"
        )

    def test_databases_different_names(self, installation_config):
        """Verify test and production databases have different names."""
        test_db = installation_config['test_db']
        prod_db = installation_config['prod_db']

        assert test_db != prod_db, (
            f"TEST_DATABASE and PRODUCTION_DATABASE have the same name: {test_db}\n"
            f"Test and production databases must be separate to prevent accidental data mixing.\n"
            f"Update config/cloud.py to use different database names."
        )

    def test_test_and_prod_urls_different(self, installation_config):
        """Verify test and production URLs are different."""
        test_url = installation_config['test_url']
        prod_url = installation_config['prod_url']

        assert test_url != prod_url, (
            f"TEST_BASE_URL and PRODUCTION_BASE_URL are the same: {test_url}\n"
            f"Test and production environments must have separate URLs.\n"
            f"Update config/cloud.py to use different service names or domains."
        )

    def test_public_areas_subset_of_all_areas(self, installation_config):
        """Verify get_public_areas() returns a subset of get_all_areas()."""
        all_areas = set(installation_config['all_areas'])
        public_areas = set(installation_config['public_areas'])

        # Public areas should be a subset of all areas
        assert public_areas.issubset(all_areas), (
            f"Public areas contains codes not in all areas.\n"
            f"Public areas: {sorted(public_areas)}\n"
            f"All areas: {sorted(all_areas)}\n"
            f"Extra in public: {sorted(public_areas - all_areas)}\n"
            f"Check get_public_areas() implementation in config/areas.py"
        )

    def test_admin_only_areas_excluded_from_public(self, installation_config):
        """Verify areas with admin_assignment_only=True are not in public areas."""
        area_config = installation_config['area_config']
        public_areas = set(installation_config['public_areas'])

        admin_only_areas = set()
        for area_code, config in area_config.items():
            if config.get('admin_assignment_only', False):
                admin_only_areas.add(area_code)

        incorrectly_public = admin_only_areas & public_areas

        assert not incorrectly_public, (
            f"Areas marked admin_assignment_only=True are in public areas: {sorted(incorrectly_public)}\n"
            f"These areas should not be available for public registration.\n"
            f"Check get_public_areas() implementation in config/areas.py"
        )

    def test_map_center_reasonable(self, area_boundaries_data):
        """Verify map center coordinates are reasonable values."""
        if area_boundaries_data is None or 'map_config' not in area_boundaries_data:
            pytest.skip("area_boundaries.json or map_config not available")

        center = area_boundaries_data['map_config']['center']

        assert isinstance(center, list) and len(center) == 2, (
            f"Map center should be [latitude, longitude], got: {center}\n"
            f"Re-run: python utils/parse_area_boundaries.py <your-kml-file.kml>"
        )

        lat, lon = center

        # Reasonable latitude range: -90 to 90
        assert -90 <= lat <= 90, (
            f"Map center latitude out of range: {lat}\n"
            f"Latitude must be between -90 and 90.\n"
            f"Re-run: python utils/parse_area_boundaries.py <your-kml-file.kml>"
        )

        # Reasonable longitude range: -180 to 180
        assert -180 <= lon <= 180, (
            f"Map center longitude out of range: {lon}\n"
            f"Longitude must be between -180 and 180.\n"
            f"Re-run: python utils/parse_area_boundaries.py <your-kml-file.kml>"
        )

    def test_base_domain_in_urls(self, installation_config):
        """Verify BASE_DOMAIN appears in test and production URLs."""
        base_domain = installation_config['base_domain']
        test_url = installation_config['test_url']
        prod_url = installation_config['prod_url']

        assert base_domain in test_url, (
            f"BASE_DOMAIN '{base_domain}' not found in TEST_BASE_URL '{test_url}'\n"
            f"Check URL construction in config/cloud.py"
        )

        assert base_domain in prod_url, (
            f"BASE_DOMAIN '{base_domain}' not found in PRODUCTION_BASE_URL '{prod_url}'\n"
            f"Check URL construction in config/cloud.py"
        )
