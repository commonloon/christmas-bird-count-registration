# Updated by Claude AI on 2026-09-11
"""
Tests for the decorative "major area group" boundary-line feature: KML
placemarks with <LineString> geometry (no area code, no individual
identity) drawn as a visual orientation overlay on top of the real
(possibly subdivided) area polygons - e.g. Comox's areas 3A/3B/3C all sit
inside one traditional "3" outline. See services/kml_import.py's
parse_kml_boundary_lines(), migration 0011 (circles.major_area_boundaries),
and static/js/map.js|leaders-map.js's displayBoundaries().
"""

import io

import pytest

from config.database import get_db_session
from models.circle import CircleModel, CircleAreaModel
from models.db import CircleArea
from services.kml_import import parse_kml_boundary_lines, KmlParseError
from tests.test_config import TEST_CIRCLE_SLUG

IMPORT_URL = f'/bigbird/circles/{TEST_CIRCLE_SLUG}/areas/import-kml'
TEST_AREA_CODE = 'ZZ'  # doesn't collide with the 'test' circle's real A-Y areas

KML_WITH_BOUNDARY = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Folder>
      <Placemark>
        <name>Area {TEST_AREA_CODE} Test Boundary Area</name>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>-124.0,49.0,0 -124.0,49.1,0 -123.9,49.1,0 -124.0,49.0,0</coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
      <Placemark>
        <name>Boundary</name>
        <LineString>
          <coordinates>-124.0,49.0,0 -123.9,49.1,0 -123.9,49.0,0</coordinates>
        </LineString>
      </Placemark>
    </Folder>
  </Document>
</kml>'''

KML_WITHOUT_BOUNDARY = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Folder>
      <Placemark>
        <name>Area {TEST_AREA_CODE} Test Boundary Area</name>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>-124.0,49.0,0 -124.0,49.1,0 -123.9,49.1,0 -124.0,49.0,0</coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
    </Folder>
  </Document>
</kml>'''


@pytest.fixture
def cleanup_test_boundary_state():
    """Removes the throwaway 'ZZ' area and resets major_area_boundaries on
    the shared 'test' circle after a test imports a KML into it - the KML
    import route has no delete-area capability of its own (see the session
    that added this feature), so cleanup goes straight through the DB."""
    yield
    db = get_db_session()
    db.query(CircleArea).filter_by(circle_slug=TEST_CIRCLE_SLUG, code=TEST_AREA_CODE).delete()
    db.commit()
    CircleModel(db).update(TEST_CIRCLE_SLUG, {'major_area_boundaries': None})


class TestParseKmlBoundaryLines:
    def test_extracts_linestring_placemark(self):
        lines = parse_kml_boundary_lines(KML_WITH_BOUNDARY)
        assert lines == [{
            'type': 'LineString',
            'coordinates': [[-124.0, 49.0], [-123.9, 49.1], [-123.9, 49.0]],
        }]

    def test_ignores_polygon_placemarks(self):
        """The area Polygon placemark in the same file must never be picked
        up as a boundary line - only actual <LineString> geometry counts."""
        lines = parse_kml_boundary_lines(KML_WITHOUT_BOUNDARY)
        assert lines == []

    def test_matches_any_linestring_regardless_of_name(self):
        kml = KML_WITH_BOUNDARY.replace('<name>Boundary</name>', '<name>Some Other Label</name>')
        lines = parse_kml_boundary_lines(kml)
        assert len(lines) == 1

    def test_malformed_xml_raises(self):
        with pytest.raises(KmlParseError):
            parse_kml_boundary_lines('<kml><Document>')

    def test_doctype_rejected(self):
        with pytest.raises(KmlParseError):
            parse_kml_boundary_lines('<!DOCTYPE kml><kml></kml>')


class TestGetBoundaryDataIncludesBoundaries:
    def test_defaults_to_empty_list(self):
        db = get_db_session()
        circle = CircleModel(db).get_by_slug(TEST_CIRCLE_SLUG)
        assert not circle.get('major_area_boundaries')
        data = CircleAreaModel(db).get_boundary_data(TEST_CIRCLE_SLUG)
        assert data['boundaries'] == []

    def test_reflects_stored_boundaries(self, cleanup_test_boundary_state):
        db = get_db_session()
        lines = [{'type': 'LineString', 'coordinates': [[-124.0, 49.0], [-123.9, 49.1]]}]
        CircleModel(db).update(TEST_CIRCLE_SLUG, {'major_area_boundaries': lines})

        data = CircleAreaModel(db).get_boundary_data(TEST_CIRCLE_SLUG)
        assert data['boundaries'] == lines


class TestKmlImportRouteStoresBoundaries:
    def test_import_with_boundary_line_stores_it(self, admin_client, cleanup_test_boundary_state):
        resp = admin_client.post(
            IMPORT_URL,
            data={'kml_file': (io.BytesIO(KML_WITH_BOUNDARY.encode()), 'areas.kml')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 302

        circle = CircleModel(get_db_session()).get_by_slug(TEST_CIRCLE_SLUG)
        assert circle['major_area_boundaries'] == [{
            'type': 'LineString',
            'coordinates': [[-124.0, 49.0], [-123.9, 49.1], [-123.9, 49.0]],
        }]

    def test_reimport_without_boundary_line_clears_it(self, admin_client, cleanup_test_boundary_state):
        """The KML is the full source of truth each time - importing a file
        with zero boundary lines clears whatever a previous import set,
        rather than leaving it stale."""
        admin_client.post(
            IMPORT_URL,
            data={'kml_file': (io.BytesIO(KML_WITH_BOUNDARY.encode()), 'areas.kml')},
            content_type='multipart/form-data',
        )
        resp = admin_client.post(
            IMPORT_URL,
            data={'kml_file': (io.BytesIO(KML_WITHOUT_BOUNDARY.encode()), 'areas.kml')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 302

        circle = CircleModel(get_db_session()).get_by_slug(TEST_CIRCLE_SLUG)
        assert circle['major_area_boundaries'] == []


class TestApiAreasIncludesBoundaries:
    def test_areas_endpoint_returns_boundaries_key(self, client, cleanup_test_boundary_state):
        db = get_db_session()
        lines = [{'type': 'LineString', 'coordinates': [[-124.0, 49.0], [-123.9, 49.1]]}]
        CircleModel(db).update(TEST_CIRCLE_SLUG, {'major_area_boundaries': lines})

        resp = client.get('/api/areas')
        assert resp.status_code == 200
        assert resp.get_json()['boundaries'] == lines
