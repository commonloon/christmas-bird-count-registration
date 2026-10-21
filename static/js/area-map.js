/* Updated by Claude AI on 2026-10-21 */
// Public read-only map of a circle's count areas (templates/map.html).
// /map?area=C highlights and zooms to area C. Data: /api/areas.

// Area names/leader names come from the DB (admin-entered or KML-imported) and
// Leaflet tooltips render strings as markup - escape before interpolating.
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}

function addHatchPattern(map, color) {
    const svg = map.getPane('overlayPane').querySelector('svg');
    if (!svg) return;
    const svgNS = 'http://www.w3.org/2000/svg';
    const defs = document.createElementNS(svgNS, 'defs');
    const pattern = document.createElementNS(svgNS, 'pattern');
    pattern.setAttribute('id', 'area-hatch');
    pattern.setAttribute('width', '8');
    pattern.setAttribute('height', '8');
    pattern.setAttribute('patternUnits', 'userSpaceOnUse');
    pattern.setAttribute('patternTransform', 'rotate(45)');
    const line = document.createElementNS(svgNS, 'line');
    line.setAttribute('x1', '0');
    line.setAttribute('y1', '0');
    line.setAttribute('x2', '0');
    line.setAttribute('y2', '8');
    line.setAttribute('style', `stroke: ${color}; stroke-width: 5;`);
    pattern.appendChild(line);
    defs.appendChild(pattern);
    svg.insertBefore(defs, svg.firstChild);
}

document.addEventListener('DOMContentLoaded', function() {
    const rootStyles = getComputedStyle(document.documentElement);
    const baseColor = rootStyles.getPropertyValue('--map-color-med').trim();
    const selectedColor = rootStyles.getPropertyValue('--map-color-selected').trim();
    const requestedArea = (new URLSearchParams(window.location.search).get('area') || '').toUpperCase();

    fetch('/api/areas')
        .then(response => response.json())
        .then(data => {
            if (data.error || !data.areas || data.areas.length === 0) {
                document.getElementById('count-area-map').textContent = 'Unable to load the map.';
                return;
            }

            const config = data.map_config || {};
            const map = L.map('count-area-map').setView(config.center || [49.2827, -123.1207], config.zoom || 10);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 17,
                minZoom: 8
            }).addTo(map);
            L.svg().addTo(map);
            addHatchPattern(map, baseColor);

            let highlighted = null;
            data.areas.forEach(area => {
                const isSelected = area.letter_code.toUpperCase() === requestedArea;
                const coords = area.geometry.coordinates[0].map(c => [c[1], c[0]]);
                const color = isSelected ? selectedColor : baseColor;
                const polygon = L.polygon(coords, {
                    color: color,
                    weight: isSelected ? 4 : 2,
                    opacity: isSelected ? 1 : 0.8,
                    fillColor: area.admin_assignment_only && !isSelected ? 'url(#area-hatch)' : color,
                    fillOpacity: isSelected ? 0.6 : (area.admin_assignment_only ? 0.6 : 0.3)
                }).addTo(map);

                const leaders = (area.leaders || []).map(escapeHtml).join(', ');
                polygon.bindTooltip(
                    `Area ${escapeHtml(area.letter_code)}: ${escapeHtml(area.name)}<br>` +
                    (leaders ? `Leader${area.leaders.length > 1 ? 's' : ''}: ${leaders}` : 'Leader: to be announced'),
                    { permanent: false, direction: 'center' });

                if (isSelected) {
                    highlighted = {polygon: polygon, area: area, leaders: leaders};
                }
            });

            if (highlighted) {
                map.fitBounds(highlighted.polygon.getBounds(), {padding: [20, 20]});
                const summary = document.getElementById('map-area-summary');
                summary.textContent = `Area ${highlighted.area.letter_code}: ${highlighted.area.name}` +
                    (highlighted.area.leaders.length ? ` - led by ${highlighted.area.leaders.join(', ')}` : '');
            }
        })
        .catch(() => {
            document.getElementById('count-area-map').textContent = 'Unable to load the map.';
        });
});
