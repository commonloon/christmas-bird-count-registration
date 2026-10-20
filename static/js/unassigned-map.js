/* Updated by Claude AI on 2026-10-20 */
// Participation map at the bottom of /bigbird/unassigned. Colours follow the same
// per-circle tiers as the public registration map (count-thresholds.js); changing them
// in the colour key also recolours this page's area buttons and dropdown warnings.
document.addEventListener('DOMContentLoaded', function () {
    const mapEl = document.getElementById('unassigned-map');
    if (!mapEl) return;

    const thresholds = CountThresholds.create(mapEl.dataset.circleSlug, {
        medium: parseInt(mapEl.dataset.mediumFrom, 10),
        high: parseInt(mapEl.dataset.highFrom, 10)
    });

    // The key appears twice - beside the area buttons, so admins needn't scroll down to
    // the map, and in a row under the map. Both stay in step.
    ['capacity-legend', 'map-legend'].forEach(function (id) {
        const container = document.getElementById(id);
        if (container) {
            container.appendChild(thresholds.legendElement());
        }
    });

    const polygons = [];
    const TIERS = ['low', 'med', 'high'];

    function areaStyle(count) {
        const color = getComputedStyle(document.documentElement)
            .getPropertyValue('--map-color-' + thresholds.tier(count)).trim();
        return { weight: 2, opacity: 0.8, fillOpacity: 0.4, color: color, fillColor: color };
    }

    // Buttons and dropdown options are rendered server-side from the circle's values;
    // re-tier them here in case this viewer has chosen different ones.
    function restyleControls() {
        document.querySelectorAll('.area-count-btn').forEach(function (btn) {
            const tier = thresholds.tier(parseInt(btn.dataset.areaCount, 10));
            TIERS.forEach(t => btn.classList.toggle('btn-tier-' + t, t === tier));
        });
        document.querySelectorAll('option[data-area-count]').forEach(function (option) {
            const high = thresholds.tier(parseInt(option.dataset.areaCount, 10)) === 'high';
            option.classList.toggle('text-warning', high);
        });
        polygons.forEach(p => p.layer.setStyle(areaStyle(p.count)));
    }

    // area.name / letter_code are admin-entered, so escape before they reach a tooltip
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    fetch('/api/areas')
        .then(response => response.json())
        .then(function (data) {
            if (data.error) throw new Error(data.error);
            const config = data.map_config || {};
            const map = L.map(mapEl).setView(config.center || [49.2827, -123.1207], config.zoom || 10);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 15,
                minZoom: 8
            }).addTo(map);
            if (config.bounds && config.bounds.length === 2) {
                map.setMaxBounds(config.bounds);
            }

            (data.areas || []).forEach(function (area) {
                const coords = area.geometry.coordinates[0].map(c => [c[1], c[0]]);
                const layer = L.polygon(coords, areaStyle(area.current_count)).addTo(map)
                    .bindTooltip('Area ' + escapeHtml(area.letter_code) + ': ' + escapeHtml(area.name) +
                        '<br>Registered: ' + area.current_count, { direction: 'center' });
                polygons.push({ layer: layer, count: area.current_count });
            });

            (data.boundaries || []).forEach(function (boundary) {
                L.polyline(boundary.coordinates.map(c => [c[1], c[0]]),
                    { color: '#0055CC', weight: 4, opacity: 0.85, interactive: false }).addTo(map);
            });

            thresholds.onChange(restyleControls);
            restyleControls();
        })
        .catch(function (error) {
            console.error('Unable to load the participation map:', error);
            mapEl.textContent = 'Unable to load the participation map.';
        });
});
