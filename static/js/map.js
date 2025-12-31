// Map functionality for CBC Registration
/* Updated by Claude AI on 2025-11-30 */
let map;
let areaLayers = {};
let selectedArea = null;
let isUpdatingProgrammatically = false;

// Initialize map when page loads
document.addEventListener('DOMContentLoaded', function() {
    loadAreaData();
});

function initializeMap(mapConfig) {
    // Use map configuration from area boundaries data, or fall back to default
    const center = mapConfig.center || [49.2827, -123.1207];
    const zoom = mapConfig.zoom || 10;
    const bounds = mapConfig.bounds || null;

    // Create map with dynamic center and zoom
    map = L.map('count-area-map').setView(center, zoom);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 15,
        minZoom: 8
    }).addTo(map);

    // Set map bounds if available
    if (bounds && bounds.length === 2) {
        map.setMaxBounds(bounds);
    }
}

function loadAreaData() {
    // Fetch area data from API
    fetch('/api/areas')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error loading area data:', data.error);
                showMapError('Unable to load area boundaries');
                return;
            }

            // Initialize map with configuration from data
            const mapConfig = data.map_config || {};
            initializeMap(mapConfig);

            // Display areas
            const areas = data.areas || data;  // Support both new and old format
            displayAreas(areas);

            // Display count circle boundary if available
            if (data.count_circle) {
                displayCountCircle(data.count_circle);
            }
        })
        .catch(error => {
            console.error('Error fetching area data:', error);
            showMapError('Unable to load map data');
        });
}

function displayAreas(areas) {
    areas.forEach(area => {
        const areaCode = area.letter_code;
        const coordinates = area.geometry.coordinates[0];

        // Convert coordinates to Leaflet format [lat, lng]
        const leafletCoords = coordinates.map(coord => [coord[1], coord[0]]);

        // Determine style based on registration count
        const style = getAreaStyle(area.current_count);

        // Create polygon
        const polygon = L.polygon(leafletCoords, style)
            .addTo(map)
            .bindTooltip(`Area ${areaCode}: ${area.name}<br>Current volunteers: ${area.current_count}`, {
                permanent: false,
                direction: 'center'
            });

        // Add click handler
        polygon.on('click', function(e) {
            if (area.admin_assignment_only) {
                // Show message for admin-only areas
                showAdminOnlyMessage(areaCode, area.name);
            } else {
                // Select open areas normally
                selectAreaOnMap(areaCode, area.name, polygon);
            }
        });

        // Store reference for later use
        areaLayers[areaCode] = {
            polygon: polygon,
            data: area
        };
    });
}

function displayCountCircle(countCircle) {
    // Draw the count circle boundary as a non-interactive line
    const coordinates = countCircle.geometry.coordinates;

    // Convert coordinates to Leaflet format [lat, lng]
    const leafletCoords = coordinates.map(coord => [coord[1], coord[0]]);

    // Create a polyline (not polygon) for the count circle boundary
    const circleStyle = {
        color: '#0000FF',       // Blue color
        weight: 3,              // Line thickness
        opacity: 0.7,           // Slightly transparent
        fillOpacity: 0,         // No fill
        interactive: false,     // NOT clickable or hoverable
        className: 'count-circle-boundary'
    };

    L.polyline(leafletCoords, circleStyle).addTo(map);

    console.log('Count circle boundary displayed');
}

function getAreaStyle(count) {
    // Colors from DISTINCT_COLOURS palette (config/colors.py) using CSS variables
    const rootStyles = getComputedStyle(document.documentElement);
    const baseStyle = {
        weight: 2,
        opacity: 0.8,
        fillOpacity: 0.3
    };

    if (count <= 3) {
        const color = rootStyles.getPropertyValue('--map-color-low').trim();
        return { ...baseStyle, color: color, fillColor: color }; // Orange: 0-3 registered
    } else if (count <= 8) {
        const color = rootStyles.getPropertyValue('--map-color-med').trim();
        return { ...baseStyle, color: color, fillColor: color }; // Maroon: 4-8 registered
    } else {
        const color = rootStyles.getPropertyValue('--map-color-high').trim();
        return { ...baseStyle, color: color, fillColor: color }; // Navy: 8+ registered
    }
}

function selectAreaOnMap(areaCode, areaName, polygon) {
    // Clear previous selection
    if (selectedArea && areaLayers[selectedArea]) {
        const prevStyle = getAreaStyle(
            areaLayers[selectedArea].data.current_count
        );
        areaLayers[selectedArea].polygon.setStyle(prevStyle);
    }

    // Clear any admin-only area messages
    const formContainer = document.querySelector('.col-lg-6');
    if (formContainer) {
        const existingAlert = formContainer.querySelector('.alert-warning');
        if (existingAlert) {
            existingAlert.remove();
        }
    }

    // Highlight selected area
    const rootStyles = getComputedStyle(document.documentElement);
    const selectedColor = rootStyles.getPropertyValue('--map-color-selected').trim();
    polygon.setStyle({
        weight: 4,
        opacity: 1,
        color: selectedColor,
        fillColor: selectedColor,
        fillOpacity: 0.6
    });

    // Update form
    updateAreaSelection(areaCode, areaName);

    // Store selection
    selectedArea = areaCode;

    // Center map on selected area
    map.fitBounds(polygon.getBounds(), { padding: [20, 20] });
}

function updateAreaSelection(areaCode, areaName) {
    // Update dropdown
    const dropdown = document.getElementById('preferred_area');
    if (dropdown) {
        // Set flag to prevent recursive calls
        isUpdatingProgrammatically = true;
        window.isUpdatingProgrammatically = true;

        dropdown.value = areaCode;

        // Trigger change event for any listeners
        dropdown.dispatchEvent(new Event('change'));

        // Reset flag
        isUpdatingProgrammatically = false;
        window.isUpdatingProgrammatically = false;
    }

    // Update visual feedback
    updateSelectionFeedback(areaCode, areaName);
}

function updateSelectionFeedback(areaCode, areaName) {
    let feedbackDiv = document.getElementById('area-selection-feedback');

    if (!feedbackDiv) {
        // Create feedback div if it doesn't exist
        feedbackDiv = document.createElement('div');
        feedbackDiv.id = 'area-selection-feedback';
        feedbackDiv.className = 'selection-feedback';

        // Insert after the map
        const mapDiv = document.getElementById('count-area-map');
        mapDiv.parentNode.insertBefore(feedbackDiv, mapDiv.nextSibling);
    }

    if (areaCode === 'UNASSIGNED') {
        feedbackDiv.innerHTML = '🎯 Wherever I\'m needed most selected';
        feedbackDiv.className = 'selection-feedback';
    } else if (areaCode) {
        feedbackDiv.innerHTML = `✓ Selected: Area ${areaCode} - ${areaName}`;
        feedbackDiv.className = 'selection-feedback area-selected';
    } else {
        feedbackDiv.innerHTML = 'No area selected yet';
        feedbackDiv.className = 'selection-feedback';
    }
}

function showMapError(message) {
    const mapDiv = document.getElementById('count-area-map');
    mapDiv.innerHTML = `
        <div class="d-flex align-items-center justify-content-center h-100">
            <div class="text-center text-muted">
                <i class="fas fa-exclamation-triangle mb-2"></i>
                <p>${message}</p>
                <small>You can still select an area using the dropdown above.</small>
            </div>
        </div>
    `;
}

function showAdminOnlyMessage(areaCode, areaName) {
    // Show an alert for admin-only areas
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-warning alert-dismissible fade show';
    alertDiv.innerHTML = `
        <strong>Area ${areaCode} - ${areaName}</strong><br>
        Only organizers can assign volunteers to this area.<br>
        To request assignment, choose <strong>"Wherever I'm needed most"</strong> and put your request in the
        <strong>Notes to Organizers</strong> field.
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    // Find the form container and insert the alert
    const formContainer = document.querySelector('.col-lg-6');
    if (formContainer) {
        // Remove any existing admin-only alerts
        const existingAlert = formContainer.querySelector('.alert-warning');
        if (existingAlert) {
            existingAlert.remove();
        }
        formContainer.insertBefore(alertDiv, formContainer.firstChild);
    }
}

// Function to highlight area from dropdown selection
function highlightAreaFromDropdown(areaCode) {
    if (areaCode === 'UNASSIGNED') {
        // Clear any map selection for "anywhere" option
        if (selectedArea && areaLayers[selectedArea]) {
            const prevStyle = getAreaStyle(
                areaLayers[selectedArea].data.current_count
            );
            areaLayers[selectedArea].polygon.setStyle(prevStyle);
        }
        selectedArea = null;
        updateSelectionFeedback('UNASSIGNED', 'Auto-assignment');
        return;
    }

    if (areaLayers[areaCode]) {
        const layer = areaLayers[areaCode];
        selectAreaOnMap(areaCode, layer.data.name, layer.polygon);
    }
}

// Export function and flag for use by other scripts
window.highlightAreaFromDropdown = highlightAreaFromDropdown;
window.isUpdatingProgrammatically = isUpdatingProgrammatically;