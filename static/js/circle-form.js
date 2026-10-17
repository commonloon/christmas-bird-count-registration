/* Circle create/edit form: external-count toggle, slug suggestion + availability check,
   multi-date list, click-to-place location map. Updated by Claude AI on 2026-10-17 */

// Same size the landing map draws each circle at (landing-map.js).
const LOCATION_RADIUS_METERS = 12000;

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('circle-form');
    if (!form) {
        return;
    }
    const externalBox = document.getElementById('is_external');

    initializeExternalToggle(form, externalBox);
    initializeCountDates();
    initializeLocationMap();
    if (form.dataset.isNew === 'true') {
        initializeSlugField(form);
    }

    form.addEventListener('submit', function(event) {
        const error = document.getElementById('form-client-error');
        error.textContent = '';
        const external = externalBox.checked;

        if (form.dataset.isNew === 'true' && form.dataset.slugAvailable === 'false') {
            event.preventDefault();
            error.textContent = 'Please choose a slug that is available.';
            document.getElementById('slug-input').focus();
            return;
        }
        if (form.dataset.isNew !== 'true' && !externalBox.disabled
                && String(external) !== form.dataset.initialExternal) {
            const message = external
                ? 'Change this circle to an external count? Its own registration pages will stop working and send visitors to the external web address (or the landing page). Its existing data is kept.'
                : 'Change this circle back to an internal count? Its own registration pages will start working again.';
            if (!window.confirm(message)) {
                event.preventDefault();
                return;
            }
        }
        const org = document.getElementById('org-name-input');
        if (external && !org.value.trim()
                && !window.confirm('Save without a managing organization?')) {
            event.preventDefault();
            org.focus();
        }
    });
});

function initializeExternalToggle(form, externalBox) {
    // Fields that only apply to one kind of circle are hidden AND disabled (so they
    // aren't submitted); `required` is remembered and restored when they come back.
    const remembered = new Map();
    form.querySelectorAll('[data-required-unless-external]').forEach(function(input) {
        remembered.set(input, true);
    });

    function apply() {
        const external = externalBox.checked;
        form.querySelectorAll('.internal-only').forEach(function(section) {
            setSectionActive(section, !external);
        });
        form.querySelectorAll('.external-only').forEach(function(section) {
            setSectionActive(section, external);
        });
        remembered.forEach(function(_, input) {
            input.required = !external && !input.disabled;
        });
    }

    function setSectionActive(section, active) {
        section.hidden = !active;
        section.querySelectorAll('input, select, textarea').forEach(function(input) {
            // The external URL box stays disabled for non-super-admins (server-rendered).
            if (input.dataset.serverDisabled === undefined) {
                input.dataset.serverDisabled = input.disabled ? 'true' : 'false';
            }
            input.disabled = !active || input.dataset.serverDisabled === 'true';
        });
    }

    externalBox.addEventListener('change', apply);
    apply();
}

function initializeCountDates() {
    const container = document.getElementById('count-dates');
    const addButton = document.getElementById('add-count-date');

    function rowFor(value) {
        const row = document.createElement('div');
        row.className = 'input-group mb-2 count-date-row';
        const input = document.createElement('input');
        input.type = 'date';
        input.name = 'count_date';
        input.className = 'form-control';
        input.value = value || '';
        input.setAttribute('aria-label', 'Count date');
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'btn btn-outline-secondary remove-count-date';
        remove.setAttribute('aria-label', 'Remove this date');
        remove.textContent = '×';
        row.append(input, remove);
        return row;
    }

    addButton.addEventListener('click', function() {
        const row = rowFor('');
        container.appendChild(row);
        row.querySelector('input').focus();
    });

    container.addEventListener('click', function(event) {
        const button = event.target.closest('.remove-count-date');
        if (!button) {
            return;
        }
        const rows = container.querySelectorAll('.count-date-row');
        if (rows.length > 1) {
            button.closest('.count-date-row').remove();
        } else {
            rows[0].querySelector('input').value = '';  // keep one empty row
        }
    });
}

function initializeLocationMap() {
    const mapEl = document.getElementById('location-map');
    if (!mapEl) {
        return;  // circle-admins can't set the location
    }
    const latInput = document.getElementById('latitude-input');
    const lngInput = document.getElementById('longitude-input');

    const lat = parseFloat(latInput.value);
    const lng = parseFloat(lngInput.value);
    const hasPoint = !isNaN(lat) && !isNaN(lng);

    const map = L.map(mapEl).setView(hasPoint ? [lat, lng] : [50.0, -123.5], hasPoint ? 10 : 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 15,
        minZoom: 3
    }).addTo(map);

    let shape = null;
    function place(latitude, longitude) {
        if (shape) {
            shape.setLatLng([latitude, longitude]);
        } else {
            shape = L.circle([latitude, longitude], {
                radius: LOCATION_RADIUS_METERS,
                color: getComputedStyle(document.documentElement).getPropertyValue('--brand-primary').trim() || '#008072',
                weight: 2,
                fillOpacity: 0.15
            }).addTo(map);
        }
    }
    if (hasPoint) {
        place(lat, lng);
    }

    map.on('click', function(event) {
        const latitude = Math.round(event.latlng.lat * 100000) / 100000;
        const longitude = Math.round(event.latlng.lng * 100000) / 100000;
        latInput.value = latitude;
        lngInput.value = longitude;
        place(latitude, longitude);
    });

    // Typing coordinates moves the circle too.
    function fromInputs() {
        const typedLat = parseFloat(latInput.value);
        const typedLng = parseFloat(lngInput.value);
        if (!isNaN(typedLat) && !isNaN(typedLng)
                && Math.abs(typedLat) <= 90 && Math.abs(typedLng) <= 180) {
            place(typedLat, typedLng);
            map.panTo([typedLat, typedLng]);
        }
    }
    latInput.addEventListener('change', fromInputs);
    lngInput.addEventListener('change', fromInputs);
}

function slugify(text) {
    return text
        .normalize('NFD').replace(/[̀-ͯ]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .slice(0, 50)
        .replace(/-+$/g, '');
}

function initializeSlugField(form) {
    const nameInput = document.getElementById('circle-name-input');
    const slugInput = document.getElementById('slug-input');
    const status = document.getElementById('slug-status');
    let slugEdited = slugInput.value !== '';
    let timer = null;
    let latestRequest = 0;

    function setStatus(text, ok) {
        status.textContent = text;
        status.className = 'small mt-1 ' + (ok === null ? 'text-muted' : ok ? 'text-success' : 'text-danger');
    }

    function check() {
        const slug = slugInput.value.trim().toLowerCase();
        form.dataset.slugAvailable = 'unknown';
        if (!slug) {
            setStatus('', null);
            return;
        }
        setStatus('Checking...', null);
        const request = ++latestRequest;
        fetch(form.dataset.slugCheckUrl + '?slug=' + encodeURIComponent(slug))
            .then(function(response) { return response.json(); })
            .then(function(result) {
                if (request !== latestRequest) {
                    return;  // a newer keystroke superseded this answer
                }
                form.dataset.slugAvailable = result.available ? 'true' : 'false';
                setStatus(result.message, result.available);
            })
            .catch(function() {
                if (request === latestRequest) {
                    setStatus('Could not check availability - the server will check on submit.', null);
                }
            });
    }

    function scheduleCheck() {
        clearTimeout(timer);
        timer = setTimeout(check, 300);
    }

    nameInput.addEventListener('input', function() {
        if (!slugEdited) {
            slugInput.value = slugify(nameInput.value);
            scheduleCheck();
        }
    });
    slugInput.addEventListener('input', function() {
        slugEdited = slugInput.value !== '';
        scheduleCheck();
    });

    if (slugInput.value) {
        check();
    }
}
