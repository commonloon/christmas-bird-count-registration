/* Updated by Claude AI on 2026-10-21 */
// Public read-only map of a circle's count areas (templates/map.html), with a
// clickable list of areas below it. /map?area=C starts with area C highlighted.
// Data: /api/areas.

// Area names/descriptions/leader names come from the DB (admin-entered or
// KML-imported) and Leaflet tooltips render strings as markup - escape before
// interpolating. The list below the map is built with textContent instead.
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

function showMapError(message) {
    document.getElementById('count-area-map').textContent = message;
}

function leaderText(leaders) {
    return leaders.length
        ? `Leader${leaders.length > 1 ? 's' : ''}: ${leaders.join(', ')}`
        : 'Leader: to be announced';
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
                showMapError('Unable to load the map.');
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

            const layers = {};   // area code -> {polygon, area, item}
            let selectedCode = null;
            const selectEl = document.getElementById('area-select');
            const detailEl = document.getElementById('area-detail');
            const listEl = document.getElementById('area-list');
            selectEl.disabled = false;

            // Detail box above the map; built with textContent (admin-entered text)
            function showDetail(area) {
                detailEl.replaceChildren();
                const title = document.createElement('strong');
                title.textContent = `Area ${area.letter_code}: ${area.name}`;
                detailEl.appendChild(title);
                if (area.admin_assignment_only) {
                    const badge = document.createElement('span');
                    badge.className = 'badge text-bg-secondary ms-2';
                    badge.textContent = 'Assigned by organizers';
                    detailEl.appendChild(badge);
                }
                if (area.description) {
                    const desc = document.createElement('div');
                    desc.textContent = area.description;
                    detailEl.appendChild(desc);
                }
                const leaderLine = document.createElement('div');
                leaderLine.className = 'small text-muted';
                leaderLine.textContent = leaderText(area.leaders || []);
                detailEl.appendChild(leaderLine);
            }

            function polygonStyle(area, isSelected) {
                const color = isSelected ? selectedColor : baseColor;
                return {
                    color: color,
                    weight: isSelected ? 4 : 2,
                    opacity: isSelected ? 1 : 0.8,
                    fillColor: area.admin_assignment_only && !isSelected ? 'url(#area-hatch)' : color,
                    fillOpacity: isSelected ? 0.6 : (area.admin_assignment_only ? 0.6 : 0.3)
                };
            }

            function selectArea(code, zoom) {
                const current = layers[code];
                if (!current) return;
                if (selectedCode && layers[selectedCode]) {
                    const prev = layers[selectedCode];
                    prev.polygon.setStyle(polygonStyle(prev.area, false));
                    prev.item.classList.remove('active');
                }
                selectedCode = code;
                current.polygon.setStyle(polygonStyle(current.area, true));
                current.polygon.bringToFront();
                current.item.classList.add('active');
                if (zoom) {
                    map.fitBounds(current.polygon.getBounds(), {padding: [20, 20]});
                }
                selectEl.value = code;
                showDetail(current.area);
                history.replaceState(null, '', `?area=${encodeURIComponent(code)}`);
            }

            data.areas.forEach(area => {
                const code = area.letter_code.toUpperCase();
                const coords = area.geometry.coordinates[0].map(c => [c[1], c[0]]);
                const polygon = L.polygon(coords, polygonStyle(area, false)).addTo(map);

                polygon.bindTooltip(
                    `Area ${escapeHtml(area.letter_code)}: ${escapeHtml(area.name)}<br>` +
                    escapeHtml(leaderText(area.leaders || [])),
                    { permanent: false, direction: 'center' });

                // List row: a button, so it is keyboard-accessible
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'list-group-item list-group-item-action';
                const title = document.createElement('strong');
                title.textContent = `Area ${area.letter_code}: ${area.name}`;
                item.appendChild(title);
                if (area.admin_assignment_only) {
                    const badge = document.createElement('span');
                    badge.className = 'badge text-bg-secondary ms-2';
                    badge.textContent = 'Assigned by organizers';
                    item.appendChild(badge);
                }
                if (area.description) {
                    const desc = document.createElement('div');
                    desc.className = 'small text-muted';
                    desc.textContent = area.description;
                    item.appendChild(desc);
                }
                const leaderLine = document.createElement('div');
                leaderLine.className = 'small';
                leaderLine.textContent = leaderText(area.leaders || []);
                item.appendChild(leaderLine);
                listEl.appendChild(item);

                const option = document.createElement('option');
                option.value = code;
                option.textContent = `Area ${area.letter_code}: ${area.name}`;
                selectEl.appendChild(option);

                layers[code] = {polygon: polygon, area: area, item: item};
                polygon.on('click', () => selectArea(code, false));
                item.addEventListener('click', () => {
                    selectArea(code, true);
                    document.getElementById('count-area-map').scrollIntoView({behavior: 'smooth', block: 'nearest'});
                });
            });

            selectEl.addEventListener('change', () => {
                if (selectEl.value) selectArea(selectEl.value, true);
            });

            if (requestedArea) {
                selectArea(requestedArea, true);
            }
        })
        .catch(() => showMapError('Unable to load the map.'));
});
