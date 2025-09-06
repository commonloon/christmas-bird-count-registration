// Map functionality for Vancouver CBC Registration
let map;
let areaLayers = {};
let selectedArea = null;

// Initialize map when page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
    loadAreaData();
});

function initializeMap() {
    // Create map centered on Vancouver
    map = L.map('count-area-map').setView([49.2827, -123.1207], 10);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 15,
        minZoom: 8
    }).addTo(map);

    // Set map bounds to Vancouver area
    const vancouverBounds = [
        [49.00, -123.30], // Southwest
        [49.40, -122.80]  // Northeast
    ];
    map.setMaxBounds(vancouverBounds);
}

function loadAreaData() {
    // Fetch area data from API
    fetch('/api/areas')
        .then(response => response.json())
        .then(areas => {
            if (areas.error) {
                console.error('Error loading area data:', areas.error);
                showMapError('Unable to load area boundaries');
                return;
            }

            displayAreas(areas);
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

        // Determine style based on availability
        const style = getAreaStyle(area.availability, area.current_count);

        // Create polygon
        const polygon = L.polygon(leafletCoords, style)
            .addTo(map)
            .bindTooltip(`Area ${areaCode}: ${area.name}<br>Current volunteers: ${area.current_count}`, {
                permanent: false,
                direction: 'center'
            });

        // Add click handler
        polygon.on('click', function(e) {
            selectAreaOnMap(areaCode, area.name, polygon);
        });

        // Store reference for later use
        areaLayers[areaCode] = {
            polygon: polygon,
            data: area
        };
    });
}

function getAreaStyle(availability, count) {
    const baseStyle = {
        weight: 2,
        opacity: 0.8,
        fillOpacity: 0.3
    };

    switch(availability) {
        case 'high':
            return { ...baseStyle, color: '#28a745', fillColor: '#28a745' };
        case 'medium':
            return { ...baseStyle, color: '#ffc107', fillColor: '#ffc107' };
        case 'low':
            return { ...baseStyle, color: '#dc3545', fillColor: '#dc3545' };
        default:
            return { ...baseStyle, color: '#6c757d', fillColor: '#6c757d' };
    }
}

function selectAreaOnMap(areaCode, areaName, polygon) {
    // Clear previous selection
    if (selectedArea && areaLayers[selectedArea]) {
        const prevStyle = getAreaStyle(
            areaLayers[selectedArea].data.availability,
            areaLayers[selectedArea].data.current_count
        );
        areaLayers[selectedArea].polygon.setStyle(prevStyle);
    }

    // Highlight selected area
    polygon.setStyle({
        weight: 4,
        opacity: 1,
        color: '#007bff',
        fillColor: '#007bff',
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
        dropdown.value = areaCode;

        // Trigger change event for any listeners
        dropdown.dispatchEvent(new Event('change'));
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

    if (areaCode === 'ANYWHERE') {
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

// Function to highlight area from dropdown selection
function highlightAreaFromDropdown(areaCode) {
    if (areaCode === 'ANYWHERE') {
        // Clear any map selection for "anywhere" option
        if (selectedArea && areaLayers[selectedArea]) {
            const prevStyle = getAreaStyle(
                areaLayers[selectedArea].data.availability,
                areaLayers[selectedArea].data.current_count
            );
            areaLayers[selectedArea].polygon.setStyle(prevStyle);
        }
        selectedArea = null;
        updateSelectionFeedback('ANYWHERE', 'Auto-assignment');
        return;
    }

    if (areaLayers[areaCode]) {
        const layer = areaLayers[areaCode];
        selectAreaOnMap(areaCode, layer.data.name, layer.polygon);
    }
}

// Export function for use by other scripts
window.highlightAreaFromDropdown = highlightAreaFromDropdown;