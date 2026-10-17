// Landing page map - shows all count circles on one map
/* Updated by Claude AI on 2026-10-17 */

// Official CBC circle size: 15 miles in diameter (~24km), i.e. 12km radius.
const CIRCLE_RADIUS_METERS = 12000;

function initializeLandingMap(circles) {
    // Fallback view if no circle has usable coordinates - covers the Lower
    // Mainland, arbitrarily. Normally overridden below by fitBounds() once real
    // circles are drawn, since circles are no longer all clustered near Vancouver
    // (e.g. Comox Valley, well up Vancouver Island, would render off-screen under
    // a fixed Lower-Mainland viewport).
    const map = L.map('circles-map').setView([49.15, -122.75], 9);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 15,
        minZoom: 7
    }).addTo(map);

    const shapes = [];
    circles.forEach(function(circle) {
        if (circle.latitude == null || circle.longitude == null) {
            return;
        }

        // Built via DOM APIs (not an HTML string) so a circle name can never be
        // interpreted as markup - bindPopup renders whatever it's given as raw HTML.
        // An external circle with no external URL is listed without a link.
        let popupContent;
        if (circle.url) {
            const link = document.createElement('a');
            link.href = circle.url;
            link.textContent = circle.circle_name;
            if (circle.is_external) {
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.textContent += ' \u2197';
            }
            popupContent = link;
        } else {
            popupContent = document.createElement('span');
            popupContent.textContent = circle.circle_name;
        }

        const circleShape = L.circle([circle.latitude, circle.longitude], {
            radius: CIRCLE_RADIUS_METERS,
            color: getComputedStyle(document.documentElement).getPropertyValue('--brand-primary').trim() || '#008072',
            weight: 2,
            fillOpacity: 0.15
        }).addTo(map);
        circleShape.bindPopup(popupContent);
        shapes.push(circleShape);
    });

    if (shapes.length > 0) {
        map.fitBounds(L.featureGroup(shapes).getBounds(), { padding: [30, 30] });
    }
}

function initializeProblemReports() {
    const modalEl = document.getElementById('reportProblemModal');
    const form = document.getElementById('report-problem-form');
    if (!modalEl || !form) {
        return;
    }
    const modal = new bootstrap.Modal(modalEl);
    const status = document.getElementById('report-problem-status');
    const submit = document.getElementById('report-problem-submit');

    function setStatus(text, isError) {
        status.textContent = text;
        status.className = 'small ' + (isError ? 'text-danger' : 'text-success');
    }

    document.querySelectorAll('.report-problem-btn').forEach(function(button) {
        button.addEventListener('click', function() {
            document.getElementById('report-problem-slug').value = button.dataset.slug;
            document.getElementById('report-problem-circle').textContent = button.dataset.name;
            setStatus('', false);
            submit.disabled = false;
            modal.show();
        });
    });

    form.addEventListener('submit', function(event) {
        event.preventDefault();
        if (!form.reportValidity()) {
            return;
        }
        submit.disabled = true;
        setStatus('Sending...', false);

        fetch('/report-problem', { method: 'POST', body: new FormData(form) })
            .then(function(response) {
                return response.json().catch(function() { return {}; }).then(function(data) {
                    return { ok: response.ok && data.ok, error: data.error };
                });
            })
            .then(function(result) {
                if (result.ok) {
                    form.reset();
                    setStatus('Thank you - your report has been sent.', false);
                } else {
                    submit.disabled = false;
                    setStatus(result.error || 'Sorry, the report could not be sent.', true);
                }
            })
            .catch(function() {
                submit.disabled = false;
                setStatus('Sorry, the report could not be sent.', true);
            });
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
