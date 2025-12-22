// Map functionality for Areas Needing Leaders display
/* Updated by Claude AI on 2025-10-16 */
let leadersMap;
let leadersAreaLayers = {};

// Initialize map when page loads
document.addEventListener('DOMContentLoaded', function() {
    const mapContainer = document.getElementById('leaders-map');
    if (mapContainer) {
        loadAreasNeedingLeaders();
    }
});

function initializeLeadersMap(mapConfig) {
    // Use map configuration from area boundaries data, or fall back to default
    const center = mapConfig.center || [49.2827, -123.1207];
    const zoom = mapConfig.zoom || 10;
    const bounds = mapConfig.bounds || null;

    // Create map with dynamic center and zoom
    leadersMap = L.map('leaders-map').setView(center, zoom);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 15,
        minZoom: 8
    }).addTo(leadersMap);

    // Set map bounds if available
    if (bounds && bounds.length === 2) {
        leadersMap.setMaxBounds(bounds);
    }
}

function loadAreasNeedingLeaders() {
    // Fetch area data from API
    fetch('/api/areas_needing_leaders')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error loading areas needing leaders:', data.error);
                showLeadersMapError('Unable to load area boundaries');
                return;
            }

            // Initialize map with configuration from data
            const mapConfig = data.map_config || {};
            initializeLeadersMap(mapConfig);

            // Cache area boundary data for future refreshes
            window.cachedAreaData = data.areas;

            displayAreasNeedingLeaders(data.areas, data.areas_without_leaders);

            // Display count circle boundary if available
            if (data.count_circle) {
                displayCountCircle(data.count_circle);
            }
        })
        .catch(error => {
            console.error('Error fetching areas needing leaders:', error);
            showLeadersMapError('Unable to load map data');
        });
}

function displayAreasNeedingLeaders(allAreas, areasWithoutLeaders) {
    const areasWithoutLeadersSet = new Set(areasWithoutLeaders);

    allAreas.forEach(area => {
        const areaCode = area.letter_code;
        const coordinates = area.geometry.coordinates[0];

        // Convert coordinates to Leaflet format [lat, lng]
        const leafletCoords = coordinates.map(coord => [coord[1], coord[0]]);

        // Determine style based on leadership status
        const needsLeader = areasWithoutLeadersSet.has(areaCode);
        const style = getLeadershipStyle(needsLeader);

        // Create tooltip text
        let tooltipText = `Area ${areaCode}: ${area.name}<br>`;
        if (needsLeader) {
            tooltipText += '⚠️ Needs Leader';
        } else {
            tooltipText += '✅ Has Leader';
            // Add leader names if available
            if (window.leaderData && window.leaderData[areaCode] && window.leaderData[areaCode].length > 0) {
                const leaders = window.leaderData[areaCode];
                if (leaders.length === 1) {
                    tooltipText += `<br>Leader: ${leaders[0]}`;
                } else {
                    tooltipText += `<br>Leaders: ${leaders.join(', ')}`;
                }
            }
        }

        // Create polygon
        const polygon = L.polygon(leafletCoords, style)
            .addTo(leadersMap)
            .bindTooltip(tooltipText, {
                permanent: false,
                direction: 'center',
                className: needsLeader ? 'needs-leader-tooltip' : 'has-leader-tooltip'
            });

        // Add click handler for areas needing leaders
        if (needsLeader) {
            polygon.on('click', function(e) {
                highlightAreaNeedingLeader(areaCode, area.name, polygon);
            });
            polygon.on('mouseover', function(e) {
                polygon.setStyle({
                    ...style,
                    weight: 4,
                    opacity: 1,
                    fillOpacity: 0.8
                });
            });
            polygon.on('mouseout', function(e) {
                polygon.setStyle(style);
            });
        }

        // Store reference for later use
        leadersAreaLayers[areaCode] = {
            polygon: polygon,
            data: area,
            needsLeader: needsLeader
        };
    });

    // Update legend - use window.allAreas for consistent total count
    const totalAreas = window.allAreas ? window.allAreas.length : allAreas.length;
    updateLeadersMapLegend(areasWithoutLeaders.length, totalAreas - areasWithoutLeaders.length);
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

    L.polyline(leafletCoords, circleStyle).addTo(leadersMap);

    console.log('Count circle boundary displayed on leaders map');
}

function getLeadershipStyle(needsLeader) {
    const baseStyle = {
        weight: 2,
        opacity: 0.8,
        fillOpacity: 0.4
    };

    if (needsLeader) {
        // Red for areas needing leaders
        return { 
            ...baseStyle, 
            color: '#dc3545', 
            fillColor: '#dc3545',
            weight: 3
        };
    } else {
        // Green for areas with leaders
        return { 
            ...baseStyle, 
            color: '#28a745', 
            fillColor: '#28a745',
            fillOpacity: 0.2
        };
    }
}

function highlightAreaNeedingLeader(areaCode, areaName, polygon) {
    // Show area details or focus
    polygon.setStyle({
        weight: 5,
        opacity: 1,
        color: '#007bff',
        fillColor: '#007bff',
        fillOpacity: 0.7
    });

    // Center map on selected area
    leadersMap.fitBounds(polygon.getBounds(), { padding: [20, 20] });

    // Show area info
    showAreaInfo(areaCode, areaName);
    
    // Reset style after a delay
    setTimeout(() => {
        polygon.setStyle(getLeadershipStyle(true));
    }, 2000);
}

function showAreaInfo(areaCode, areaName) {
    // Update or create info panel
    let infoDiv = document.getElementById('area-info-panel');
    
    if (!infoDiv) {
        infoDiv = document.createElement('div');
        infoDiv.id = 'area-info-panel';
        infoDiv.className = 'alert alert-info mt-2';
        
        const mapDiv = document.getElementById('leaders-map');
        mapDiv.parentNode.insertBefore(infoDiv, mapDiv.nextSibling);
    }
    
    infoDiv.innerHTML = `
        <strong>Area ${areaCode} - ${areaName}</strong><br>
        <small>⚠️ This area currently needs a leader. Consider recruiting someone for this area!</small>
    `;
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        if (infoDiv) {
            infoDiv.remove();
        }
    }, 5000);
}

function updateLeadersMapLegend(needingLeaders, withLeaders) {
    let legendDiv = document.getElementById('leaders-map-legend');
    
    if (!legendDiv) {
        legendDiv = document.createElement('div');
        legendDiv.id = 'leaders-map-legend';
        legendDiv.className = 'map-legend mt-2';
        
        const mapDiv = document.getElementById('leaders-map');
        mapDiv.parentNode.insertBefore(legendDiv, mapDiv.nextSibling);
    }
    
    legendDiv.innerHTML = `
        <div class="row">
            <div class="col-md-6">
                <span class="legend-item">
                    <span class="legend-color" style="background-color: #dc3545;"></span>
                    Areas Needing Leaders (${needingLeaders})
                </span>
            </div>
            <div class="col-md-6">
                <span class="legend-item">
                    <span class="legend-color" style="background-color: #28a745;"></span>
                    Areas with Leaders (${withLeaders})
                </span>
            </div>
        </div>
    `;
}

function showLeadersMapError(message) {
    const mapDiv = document.getElementById('leaders-map');
    mapDiv.innerHTML = `
        <div class="d-flex align-items-center justify-content-center h-100">
            <div class="text-center text-muted">
                <i class="fas fa-exclamation-triangle mb-2"></i>
                <p>${message}</p>
                <small>Area data is still available in the lists below.</small>
            </div>
        </div>
    `;
}

// Clear existing map layers for refresh
function clearMapLayers() {
    if (leadersAreaLayers) {
        Object.values(leadersAreaLayers).forEach(layer => {
            if (layer.polygon) {
                leadersMap.removeLayer(layer.polygon);
            }
        });
        leadersAreaLayers = {};
    }
}

// Calculate areas needing leaders from current window.leaderData
function calculateAreasNeedingLeaders() {
    // Use areas list provided by template
    const allAreas = window.allAreas;
    if (!allAreas || allAreas.length === 0) {
        console.error('Areas not configured properly in areas.py');
        return [];
    }

    const areasWithLeaders = new Set();
    
    // Check which areas have leaders based on current window.leaderData
    if (window.leaderData) {
        Object.keys(window.leaderData).forEach(areaCode => {
            if (window.leaderData[areaCode] && window.leaderData[areaCode].length > 0) {
                areasWithLeaders.add(areaCode);
            }
        });
    }
    
    return allAreas.filter(area => !areasWithLeaders.has(area));
}

// Refresh the leaders map with current data (called after AJAX operations)
function refreshLeadersMap() {
    if (!leadersMap || !leadersAreaLayers) {
        // Map not initialized yet
        return;
    }
    
    // Clear existing layers
    clearMapLayers();
    
    // Calculate current areas needing leaders
    const areasNeedingLeaders = calculateAreasNeedingLeaders();
    
    // Get area boundary data from the first load (stored in layer data)
    const allAreaData = [];
    
    // We need to reconstruct area data from what we know
    // Since we don't want to make another API call, we'll fetch it once and store it
    if (window.cachedAreaData) {
        displayAreasNeedingLeaders(window.cachedAreaData, areasNeedingLeaders);
    } else {
        // If no cached data, reload from API once and cache it
        fetch('/api/areas_needing_leaders')
            .then(response => response.json())
            .then(data => {
                if (!data.error && data.areas) {
                    // Cache the area boundary data for future refreshes
                    window.cachedAreaData = data.areas;
                    displayAreasNeedingLeaders(data.areas, areasNeedingLeaders);
                }
            })
            .catch(error => {
                console.error('Error refreshing map:', error);
            });
    }
}

// Make refresh function available globally
window.refreshLeadersMap = refreshLeadersMap;