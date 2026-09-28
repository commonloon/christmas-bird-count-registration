# Updated by Claude AI on 2026-09-11
"""
Tests for services/kml_import.py's name/description cleanup, added when a
real Comox KML export was found to bake a redundant "Area <code>" label
into every placemark name (shown doubled wherever the app displays an area,
since it already prepends the code itself) and a "team leader NAME" phrase
into description (leader identity must come from the app's own
leader-assignment records, not static KML text - see CLAUDE.md).
"""

from services.kml_import import clean_area_name, clean_area_description, parse_kml_string


class TestCleanAreaName:
    def test_strips_area_prefix_with_colon(self):
        assert clean_area_name('Area A: Richmond Southeast', 'A') == 'Richmond Southeast'

    def test_strips_area_prefix_with_dash(self):
        assert clean_area_name('Area 4B - Departure Bay', '4B') == 'Departure Bay'

    def test_strips_area_prefix_with_plain_space(self):
        assert clean_area_name('Area 1 North Coast', '1') == 'North Coast'

    def test_strips_bare_code_dash_prefix(self):
        assert clean_area_name('1 - Iona Jetty', '1') == 'Iona Jetty'

    def test_normalizes_non_breaking_space(self):
        assert clean_area_name('Area 5C\xa0 Courtenay inland\n', '5C') == 'Courtenay inland'

    def test_normalizes_trailing_whitespace_and_newline(self):
        assert clean_area_name('Area 2 Town of Comox\n', '2') == 'Town of Comox'

    def test_case_insensitive_prefix(self):
        assert clean_area_name('area 3a courtenay east', '3A') == 'courtenay east'

    def test_bare_code_only_name_falls_back_unstripped(self):
        """Nothing left to show after stripping - keep the original (normalized)
        text rather than leaving an empty name."""
        assert clean_area_name('Area A', 'A') == 'Area A'

    def test_name_without_prefix_is_returned_normalized_only(self):
        assert clean_area_name('Ambleside/West Van Coastal', 'B') == 'Ambleside/West Van Coastal'

    def test_empty_name_returns_falsy_unchanged(self):
        assert clean_area_name('', 'A') == ''
        assert clean_area_name(None, 'A') is None


class TestCleanAreaDescription:
    def test_strips_team_leader_phrase(self):
        assert clean_area_description('team leader Steve Ellis') == 'Steve Ellis'

    def test_strips_team_leader_with_colon(self):
        assert clean_area_description('Team Leader: Jane Doe') == 'Jane Doe'

    def test_leaves_real_content_untouched(self):
        text = 'North of the Trans Canada Highway between Lynn Creek and the Capilano River.'
        assert clean_area_description(text) == text

    def test_bare_name_not_detected_or_altered(self):
        """Documented limitation: a bare leader name with no identifying phrase
        (Ladner's real data shape) can't be reliably distinguished from
        legitimate free-text content, so it's deliberately left as-is here -
        that case needs a scoped, human-reviewed data fix, not an automated
        import-time rule."""
        assert clean_area_description('Yousif Attia') == 'Yousif Attia'

    def test_empty_description_returns_falsy_unchanged(self):
        assert clean_area_description('') == ''
        assert clean_area_description(None) is None


class TestParseKmlStringAppliesCleanup:
    KML_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Folder>
      <Placemark>
        <name>Area 3A Courtenay East
</name>
        <description>team leader Nancy St Hilaire</description>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                -124.96,49.68,0 -124.95,49.68,0 -124.95,49.69,0 -124.96,49.68,0
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
    </Folder>
  </Document>
</kml>'''

    def test_parsed_area_has_clean_name_and_description(self):
        areas = parse_kml_string(self.KML_TEMPLATE)
        assert len(areas) == 1
        area = areas[0]
        assert area['letter_code'] == '3A'
        assert area['name'] == 'Courtenay East'
        assert area['description'] == 'Nancy St Hilaire'
