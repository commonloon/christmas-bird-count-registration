// Landing page map - shows all count circles on one map
/* Updated by Claude AI on 2026-08-30 */

// Official CBC circle size: 15 miles in diameter (~24km), i.e. 12km radius.
const CIRCLE_RADIUS_METERS = 12000;

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
        link.href = circle.url;
        link.textContent = circle.circle_name;

        const circleShape = L.circle([circle.latitude, circle.longitude], {
            radius: CIRCLE_RADIUS_METERS,
            color: '#0d6efd',
            weight: 2,
            fillOpacity: 0.15
        }).addTo(map);
        circleShape.bindPopup(link);
    });
}

function initializeContactButtons() {
    document.querySelectorAll('.show-contact-btn').forEach(function(button) {
        button.addEventListener('click', function() {
            const slug = button.dataset.slug;
            button.disabled = true;

            fetch(`/api/circles/${encodeURIComponent(slug)}/contact`)
                .then(function(response) {
                    if (!response.ok) {
                        throw new Error('Request failed');
                    }
                    return response.json();
                })
                .then(function(data) {
                    const link = document.createElement('a');
                    link.href = `mailto:${data.contact}`;
                    link.textContent = data.contact;
                    button.replaceWith(link);
                })
                .catch(function() {
                    button.disabled = false;
                    button.textContent = 'Unable to load - try again';
                });
        });
    });
}
