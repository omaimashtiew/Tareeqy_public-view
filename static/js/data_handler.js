// static/js/data_handler.js
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
        fencesToDisplay = allFencesData.filter(fence =>
            fence.city && fence.city.toLowerCase().includes(filterCityTerm.toLowerCase())
        );
    }

    fencesToDisplay.forEach(fence => {
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
            fenceData: fence 
        });

        marker.bindPopup(() => createFencePopupContent(fence), {
            className: 'custom-leaflet-popup',
            minWidth: 240,
        });
        
        const layerGroup = markerLayers[status] || markerLayers.unknown; 
        if (layerGroup) {
            marker.addTo(layerGroup);
        } else {
            console.warn("DATA_HANDLER: No layer group for status", status, "- adding marker directly to map.");
            marker.addTo(map); 
        }
        
        activeMapMarkers.push(marker);
        checkpointMarkers[fence.id] = marker;

        processedFences.push({
            id: fence.id, name: fence.name, status: status, city: fence.city || 'غير محدد',
            latitude: fence.latitude, longitude: fence.longitude,
            message_time_iso: fence.message_time, marker: marker
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

    if (activeMapMarkers.length > 0 && !userLocationMarker && map && map.getBounds) {
        try {
            const group = L.featureGroup(activeMapMarkers);
            if (group.getLayers().length > 0) { 
                 const groupBounds = group.getBounds();
                 if (groupBounds.isValid() && !map.getBounds().contains(groupBounds)) {
                    map.fitBounds(groupBounds.pad(0.1));
                }
            }
        } catch (e) {
            console.error("Error fitting map bounds:", e);
        }
    }
    
    console.log(`DATA_HANDLER: Displayed ${processedFences.length} fences on map (after any city filter).`);
    applyStatusFilters();
}

function createFencePopupContent(fenceData) {
    const status = fenceData.status || 'unknown';
    const details = statusDetails[status] || statusDetails.unknown; 
    const updatedTime = formatDateTime(fenceData.message_time || fenceData.status_time_iso);

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
            <div class="prediction-placeholder" data-fence-id="${fenceData.id}">
                <!-- Prediction content will be injected here -->
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
        return date.toLocaleString('ar-EG', {
            month: 'short', day: 'numeric',
            hour: 'numeric', minute: '2-digit', hour12: true
        }).replace('، ', ' - ');
    } catch (e) { return "تاريخ غير صالح"; }
}
function formatTimeOnly(isoString) {
    if (!isoString) return "غير متوفر";
    try {
        const date = new Date(isoString);
        if (isNaN(date.getTime())) return "وقت غير صالح";
        return date.toLocaleTimeString('ar-EG', {
            hour: 'numeric', minute: '2-digit', hour12: true
        });
    } catch (e) { return "وقت غير صالح"; }
}



function getFenceDataById(fenceId) { // Not currently used but could be useful
    return allFencesData.find(f => f.id.toString() === fenceId.toString());
}