// static/js/data_handler.js

let allFencesData = []; 
let processedFences = []; 

function parseInitialFenceData() {
    try {
        allFencesData = JSON.parse(FENCES_DATA_JSON);
        if (!Array.isArray(allFencesData)) {
            console.error("DATA_HANDLER: Parsed fence data is not an array:", allFencesData);
            allFencesData = [];
        }
        console.log(`DATA_HANDLER: Successfully parsed ${allFencesData.length} fences from Django.`);
    } catch (e) {
        console.error("DATA_HANDLER: Failed to parse FENCES_DATA_JSON:", e, "\nRaw data was:", FENCES_DATA_JSON);
        allFencesData = [];
        showToast("خطأ في تحميل بيانات نقاط التفتيش الأولية.", "danger");
    }
}

function processAndDisplayFences(filterCityTerm = null) {
    Object.values(markerLayers).forEach(layer => layer.clearLayers());
    for (const id in checkpointMarkers) { delete checkpointMarkers[id]; }
    processedFences = [];

    if (!allFencesData || allFencesData.length === 0) {
        document.getElementById('recent-updates-list').innerHTML = '<p class="text-muted p-2 text-center">لا توجد بيانات نقاط تفتيش متاحة.</p>';
        return;
    }

    const recentUpdates = [];
    const activeMapMarkers = [];

    let fencesToDisplay = allFencesData;
    if (filterCityTerm && filterCityTerm.trim() !== "") {
        // This city filter is currently not active as city search is handled by main search bar.
        // If you re-enable a dedicated city filter input, this logic will apply.
        // For now, main search fetches specific results and doesn't rely on this client-side filter.
        // So, filterCityTerm will likely be null or empty when this is called by general refresh.
        console.warn("DATA_HANDLER: City filtering in processAndDisplayFences is present but currently not driven by a UI element. Main search uses API.");
        // fencesToDisplay = allFencesData.filter(fence =>
        //     fence.city && fence.city.toLowerCase().includes(filterCityTerm.toLowerCase())
        // );
    }


    allFencesData.forEach(fence => { // Changed from fencesToDisplay to allFencesData to ensure all are processed for map display
        if (!fence.latitude || !fence.longitude || (parseFloat(fence.latitude) === 0 && parseFloat(fence.longitude) === 0)) {
            console.warn("DATA_HANDLER: Skipping fence (invalid coords):", fence.name);
            return;
        }

        const status = fence.status || 'unknown';
        const iconToUse = icons[status] || icons.unknown; 

        if (!iconToUse || typeof iconToUse.options === 'undefined') {
            console.error("DATA_HANDLER: Invalid icon for status", status, "for fence:", fence.name);
            return; 
        }

        const marker = L.marker([fence.latitude, fence.longitude], {
            icon: iconToUse,
            title: fence.name,
            fenceData: fence // Store full fence data with marker for popups
        });

        marker.bindPopup(() => createFencePopupContent(fence), { // Pass full fence data
            className: 'custom-leaflet-popup',
            minWidth: 250, // Adjusted minWidth
        });
        
        const layerGroup = markerLayers[status] || markerLayers.unknown; 
        if (layerGroup) {
            marker.addTo(layerGroup);
        } else {
            console.warn("DATA_HANDLER: No layer group for status", status, "- adding marker directly to map.");
            marker.addTo(map); 
        }
        
        activeMapMarkers.push(marker);
        checkpointMarkers[fence.id] = marker; // Store marker by ID

        // Store simplified data for internal processing if needed
        processedFences.push({
            id: fence.id, name: fence.name, status: status, city: fence.city || 'غير محدد',
            latitude: fence.latitude, longitude: fence.longitude,
            message_time_iso: fence.message_time, // Keep original field name
            marker: marker
        });

        if (fence.message_time) {
            recentUpdates.push({
                id: fence.id, name: fence.name, status: status,
                time: fence.message_time, city: fence.city || ''
            });
        }
    });

    recentUpdates.sort((a, b) => new Date(b.time) - new Date(a.time));
    populateRecentUpdatesList(recentUpdates.slice(0, 7));

    if (activeMapMarkers.length > 0 && !userLocationMarker && map && map.getBounds && !map.getZoom()) {
        // Check if map has not been zoomed/panned by user yet (simple check: !map.getZoom())
        try {
            const group = L.featureGroup(activeMapMarkers);
            if (group.getLayers().length > 0) { 
                 const groupBounds = group.getBounds();
                 if (groupBounds.isValid()) { // removed: && !map.getBounds().contains(groupBounds)
                    map.fitBounds(groupBounds.pad(0.1));
                }
            }
        } catch (e) {
            console.error("Error fitting map bounds:", e);
        }
    }
    
    console.log(`DATA_HANDLER: Displayed ${processedFences.length} fences on map.`);
    applyStatusFilters(); // Apply status filters after markers are added
}


function createFencePopupContent(fenceData) {
    // fenceData here is the full data object for the fence, including status, message_time, etc.
    const status = fenceData.status || 'unknown';
    const details = statusDetails[status] || statusDetails.unknown; 
    const updatedTime = formatDateTime(fenceData.message_time || fenceData.status_time_iso); // Use message_time from initial load

    let content = `
        <div class="popup-header" style="background-color: ${details.headerColor};">
            ${fenceData.name || 'نقطة تفتيش غير مسماة'}
        </div>
        <div class="popup-content-body">
            <div class="popup-item">
                <span class="popup-icon"><i class="fas ${details.icon}"></i></span>
                <span>الحالة: <strong>${details.label}</strong></span>
            </div>
            <div class="popup-item">
                <span class="popup-icon"><i class="fas fa-clock"></i></span>
                <span>آخر تحديث: ${updatedTime}</span>
            </div>
            <!-- Placeholder for AI prediction (e.g., wait time) -->
            <div class="prediction-placeholder" data-fence-id="${fenceData.id}">
                <!-- Prediction content will be injected here by location.js -->
                 <hr class="prediction-separator">
                 <div class="popup-item text-muted" style="font-size: 0.85em;">
                    <span class="popup-icon"><i class="fas fa-spinner fa-spin"></i></span>
                    <span>جاري تحميل التوقعات...</span>
                </div>
            </div>
        </div>`;
    return content;
}

function populateRecentUpdatesList(updates) {
    const container = document.getElementById('recent-updates-list');
    if (!container) return;

    if (!updates || updates.length === 0) {
        container.innerHTML = '<p class="text-muted p-2 text-center">لا توجد تحديثات حديثة.</p>';
        return;
    }

    let html = '';
    updates.forEach(update => {
        const status = update.status || 'unknown';
        const details = statusDetails[status] || statusDetails.unknown;
        html += `
            <div class="update-item">
                <div class="update-name">${update.name}</div>
                <div class="update-status" style="color: ${details.color};">
                    <i class="fas ${details.icon} me-1"></i> ${details.label}
                </div>
                <div class="update-time">
                    <i class="fas fa-clock me-1"></i> ${formatDateTime(update.time)}
                </div>
            </div>`;
    });
    container.innerHTML = html;
}

function formatDateTime(isoString) {
    if (!isoString) return "غير متوفر";
    try {
        const date = new Date(isoString);
        if (isNaN(date.getTime())) return "تاريخ غير صالح";
        return date.toLocaleString('ar-EG', { // Using ar-EG for Arabic numerals and common format
            month: 'short', day: 'numeric',
            hour: 'numeric', minute: '2-digit', hour12: true
        }).replace('، ', ' - '); // Replace comma if present
    } catch (e) { return "تاريخ غير صالح"; }
}

function formatTimeOnly(isoString) {
    if (!isoString) return "غير متوفر";
    try {
        const date = new Date(isoString);
        if (isNaN(date.getTime())) return "وقت غير صالح";
        return date.toLocaleTimeString('ar-EG', { // Using ar-EG
            hour: 'numeric', minute: '2-digit', hour12: true
        });
    } catch (e) { return "وقت غير صالح"; }
}

// Not strictly necessary for current flow but can be useful for direct access
function getFenceDataById(fenceId) { 
    return allFencesData.find(f => f.id.toString() === fenceId.toString());
}
window.allFences = JSON.parse(FENCES_DATA_JSON);
