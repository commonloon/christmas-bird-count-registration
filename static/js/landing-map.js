// Landing page map - shows all count circles on one map
/* Updated by Claude AI on 2026-08-30 */

function initializeLandingMap(circles) {
    // Default view covers the Lower Mainland; not tied to any one circle's boundary
    const map = L.map('circles-map').setView([49.15, -122.75], 9);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 15,
        minZoom: 7
    }).addTo(map);

    circles.forEach(function(circle) {
        if (circle.latitude == null || circle.longitude == null) {
            return;
        }

        // Built via DOM APIs (not an HTML string) so a circle name can never be
        // interpreted as markup - bindPopup renders whatever it's given as raw HTML.
        const link = document.createElement('a');
        link.href = `https://${circle.slug}.cbc.birdcount.ca/`;
        link.textContent = circle.name;

        const marker = L.marker([circle.latitude, circle.longitude]).addTo(map);
        marker.bindPopup(link);
    });
}
