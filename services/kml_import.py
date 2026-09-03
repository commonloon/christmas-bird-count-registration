# Updated by Claude AI on 2026-08-31
"""
KML boundary parsing, shared by the /bigbird/circles/<slug>/areas KML-upload
route and the standalone utils/parse_area_boundaries.py CLI script.

Lives in services/ (not utils/) because it's imported by application route
code at request time - see CLAUDE.md's deployment constraint that utils/ is
for one-off scripts only, never runtime app code.
"""
import re
import xml.etree.ElementTree as ET

KML_NS = {'kml': 'http://www.opengis.net/kml/2.2'}


class KmlParseError(Exception):
    """Raised for KML content that fails to parse or contains no usable areas."""


def extract_area_code(name):
    """
    Extract an area code from a placemark name using multiple patterns.
    Supports "Area A:", "Area A -", "1 - Name", "B-1:", etc.
    Returns the code as a string, or None if no pattern matched.
    """
    if not name:
        return None

    match = re.search(r'Area\s+([A-Z0-9]+-?[A-Z0-9]*)[\s:]', name, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    match = re.match(r'^([A-Z0-9]+-[A-Z0-9]+)[\s:]', name, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    match = re.match(r'^(\d+)\s*[-–—]', name)
    if match:
        return match.group(1)

    match = re.match(r'^Area\s+([A-Z0-9]+-?[A-Z0-9]*)', name, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    match = re.match(r'^([A-Z0-9]{1,3}):', name)
    if match:
        return match.group(1).upper()

    return None


def parse_coordinates_to_geojson(coord_string):
    """Convert a KML 'lng,lat,alt lng,lat,alt ...' string to [[lng, lat], ...].
    Raises KmlParseError on a non-numeric or out-of-range coordinate, rather than
    letting a ValueError escape and surface as an unhandled 500 to the caller."""
    coordinates = []
    for coord in coord_string.split():
        coord = coord.strip()
        if not coord:
            continue
        parts = coord.split(',')
        if len(parts) < 2:
            continue
        try:
            lng, lat = float(parts[0]), float(parts[1])
        except ValueError:
            raise KmlParseError(f'Could not parse coordinate pair: "{coord}"')
        if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
            raise KmlParseError(f'Coordinate out of range: "{coord}"')
        coordinates.append([lng, lat])
    return coordinates


def parse_kml_string(kml_content):
    """
    Parse KML text and extract area boundary data.

    Returns a list of {'letter_code', 'name', 'description', 'geometry'} dicts,
    naturally sorted by area code. Raises KmlParseError on malformed XML or a
    file with no recognizable area placemarks.
    """
    # Reject a DOCTYPE outright rather than parsing it: genuine KML exports
    # (Google My Maps etc.) never include one, and it's the mechanism behind
    # XXE/billion-laughs attacks against xml.etree - cheaper than a new
    # dependency (defusedxml isn't installed) given this route is admin-only.
    if re.search(r'<!DOCTYPE', kml_content, re.IGNORECASE):
        raise KmlParseError('This file has a DOCTYPE declaration, which is not supported.')

    try:
        root = ET.fromstring(kml_content)
    except ET.ParseError as e:
        raise KmlParseError(f'Could not parse KML/XML: {e}')

    areas = []
    for placemark in root.findall('.//kml:Placemark', KML_NS):
        name_elem = placemark.find('kml:name', KML_NS)
        if name_elem is None or not name_elem.text:
            continue

        name = name_elem.text
        area_code = extract_area_code(name)
        if not area_code:
            continue

        desc_elem = placemark.find('kml:description', KML_NS)
        description = desc_elem.text if desc_elem is not None and desc_elem.text else ''
        description = re.sub(r'<[^>]*>', '', description).strip()

        # Normally one <Polygon> per placemark, but a placemark can hold a
        # <MultiGeometry> with several <Polygon> fragments whose rings are meant
        # to be joined end-to-end into one boundary (each fragment's last point
        # matches the next fragment's first point) - an artifact of how some KML
        # exports split a single hand-drawn boundary into pieces. Concatenating
        # every fragment's coordinates in document order reconstructs the
        # original ring; grabbing only the first (the old behavior) silently
        # produced a tiny, wrong stub for any area exported this way.
        polygons = placemark.findall('.//kml:Polygon', KML_NS)
        coord_texts = []
        for polygon in polygons:
            coords_elem = polygon.find('.//kml:coordinates', KML_NS)
            if coords_elem is not None and coords_elem.text:
                coord_texts.append(coords_elem.text.strip())
        if not coord_texts:
            continue

        coordinates = parse_coordinates_to_geojson(' '.join(coord_texts))
        if len(coordinates) < 3:
            continue

        areas.append({
            'letter_code': area_code,
            'name': name,
            'description': description,
            'geometry': {'type': 'Polygon', 'coordinates': [coordinates]},
        })

    if not areas:
        raise KmlParseError('No placemarks with a recognizable area code were found in this file.')

    def sort_key(area):
        code = area['letter_code']
        try:
            return (0, int(code))
        except ValueError:
            return (1, code)

    areas.sort(key=sort_key)
    return areas


def filter_main_areas(areas):
    """Drop sub-areas (codes containing a hyphen, e.g. B-1, C-2), keeping only
    the main lettered/numbered areas."""
    return [area for area in areas if '-' not in area['letter_code']]


def calculate_map_center_and_bounds(areas):
    """
    Calculate a center point, bounding box, and suggested zoom from a list of
    areas (as returned by parse_kml_string). Returns None if areas is empty -
    callers should fall back to the circle's own latitude/longitude instead.
    """
    all_lats, all_lngs = [], []
    for area in areas:
        for lng, lat in area['geometry']['coordinates'][0]:
            all_lngs.append(lng)
            all_lats.append(lat)

    if not all_lats or not all_lngs:
        return None

    min_lat, max_lat = min(all_lats), max(all_lats)
    min_lng, max_lng = min(all_lngs), max(all_lngs)

    center_lat = (min_lat + max_lat) / 2
    center_lng = (min_lng + max_lng) / 2

    lat_padding = (max_lat - min_lat) * 0.10
    lng_padding = (max_lng - min_lng) * 0.10

    max_span = max(max_lat - min_lat, max_lng - min_lng)
    if max_span > 2.0:
        zoom = 8
    elif max_span > 1.0:
        zoom = 9
    elif max_span > 0.5:
        zoom = 10
    elif max_span > 0.2:
        zoom = 11
    else:
        zoom = 12

    return {
        'center': [round(center_lat, 6), round(center_lng, 6)],
        'bounds': [
            [round(min_lat - lat_padding, 6), round(min_lng - lng_padding, 6)],
            [round(max_lat + lat_padding, 6), round(max_lng + lng_padding, 6)],
        ],
        'zoom': zoom,
    }
