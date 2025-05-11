// static/js/ui_interactions.js
// Handles general UI interactions like sidebar, filters, zoom, toasts.

const sidebar = document.getElementById('sidebar');
const contentWrapper = document.getElementById('content-wrapper'); // For desktop layout adjustments
const statusLegend = document.getElementById('status-legend');

let activeStatusFilters = ['open', 'sever_traffic_jam', 'closed']; // Default filters

function setupUIEventListeners() {
    // Sidebar toggle
    document.getElementById('footer-toggle-sidebar-btn').addEventListener('click', toggleSidebar);
    document.getElementById('close-sidebar-btn').addEventListener('click', toggleSidebar);

    // Zoom controls
    document.getElementById('zoom-in-btn').addEventListener('click', () => map.zoomIn());
    document.getElementById('zoom-out-btn').addEventListener('click', () => map.zoomOut());

    // Locate user button
    document.getElementById('locate-user-btn').addEventListener('click', () => requestUserLocation(true)); // true for manual retry
    document.getElementById('retry-location-modal-btn').addEventListener('click', () => {
        bootstrap.Modal.getInstance(document.getElementById('location-error-modal')).hide();
        requestUserLocation(true); // true for manual retry
    });

    // Status filter checkboxes
    document.querySelectorAll('.filter-section .form-check-input').forEach(checkbox => {
        checkbox.addEventListener('change', handleStatusFilterChange);
    });

    // Update data button
    document.getElementById('footer-update-btn').addEventListener('click', refreshMapData);
    
    // Initial setup for responsive elements
    handleResizeOrLoad(); 
    window.addEventListener('resize', handleResizeOrLoad);
}

function toggleSidebar() {
    sidebar.classList.toggle('active');
    
    // Adjust content for desktop if sidebar changes state
    if (window.innerWidth >= 992) { // Desktop
        // The CSS should handle fixed sidebar width and map taking remaining space with flexbox.
        // If not, you might add/remove a class to contentWrapper or map here.
        // e.g., contentWrapper.classList.toggle('sidebar-open-desktop');
    }
    
    // Crucial: Invalidate map size after sidebar animation completes or immediately
    setTimeout(() => {
        if (map) map.invalidateSize({ animate: true });
    }, 350); // Match CSS transition duration
}

function handleStatusFilterChange() {
    activeStatusFilters = Array.from(document.querySelectorAll('.filter-section .form-check-input:checked'))
                               .map(cb => cb.value);
    applyStatusFilters();
}

function applyStatusFilters() {
    if (!map || !processedFences) return; // Ensure map and data are ready

    processedFences.forEach(fence => {
        const marker = fence.marker; // Reference stored during processAndDisplayFences
        if (!marker) return;

        const fenceStatus = fence.status || 'unknown';
        if (activeStatusFilters.includes(fenceStatus)) {
            if (!map.hasLayer(marker)) {
                // Re-add to its original layer group, then ensure layer group is on map
                const layerGroup = markerLayers[fenceStatus] || markerLayers.unknown;
                if (layerGroup) {
                    marker.addTo(layerGroup); // Marker is added to its group
                    if (!map.hasLayer(layerGroup)) map.addLayer(layerGroup); // Ensure group is on map
                } else {
                     marker.addTo(map); // Fallback if layer group logic is complex
                }
            }
        } else {
            if (map.hasLayer(marker)) {
                marker.remove(); // Removes from whatever layer it's on (map or group)
            }
        }
    });
    console.log("Applied filters:", activeStatusFilters);
}


function refreshMapData() {
    showToast('<div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2" role="status"></div>جاري تحديث البيانات...</div>', 'info', 3000);
    
    // Simulate fetching new data. In a real app, you'd make an API call.
    // For now, re-parse and re-process existing data.
    // To truly refresh, you'd need:
    // fetch('/api/get_fences_data/')
    //   .then(response => response.json())
    //   .then(newData => {
    //     FENCES_DATA_JSON = JSON.stringify(newData); // Update the global constant (if possible, or reassign a let variable)
    //     parseInitialFenceData();
    //     processAndDisplayFences(cityFilterInput.value.trim()); // Apply current city filter
    //     if (currentUserLocation) fetchPredictionsForLocation(currentUserLocation);
    //     showToast('تم تحديث بيانات نقاط التفتيش.', 'success');
    //   })
    //   .catch(error => {
    //     console.error("Error refreshing data:", error);
    //     showToast('فشل تحديث البيانات.', 'danger');
    //   });

    // Current simulation:
    setTimeout(() => {
        parseInitialFenceData(); // Re-parse from the potentially unchanged FENCES_DATA_JSON
        processAndDisplayFences(document.getElementById('city-filter-input').value.trim()); // Re-filter with current city
        if (currentUserLocation) {
            fetchPredictionsForLocation(currentUserLocation); // Refresh predictions too
        }
        showToast('تم تحديث البيانات (محاكاة).', 'success');
    }, 1000);
}

// Utility for showing toasts (can be global or part of UI module)
function showToast(message, type = 'info', duration = 5000) {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        console.error("Toast container not found!");
        return;
    }

    const toastId = 'toast-' + Date.now(); // Unique ID for the toast
    const toastHTML = `
        <div id="${toastId}" class="toast align-items-center text-bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="${duration}">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="إغلاق"></button>
            </div>
        </div>`;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    
    const toastElement = document.getElementById(toastId);
    if (toastElement) {
        const bootstrapToast = new bootstrap.Toast(toastElement);
        bootstrapToast.show();
        // Optional: Remove from DOM after hidden, if Bootstrap doesn't do it.
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
}


// Handle responsive positioning of elements like status legend
function handleResizeOrLoad() {
    if (!statusLegend || !map) return;

    if (window.innerWidth < 992) { // Mobile/Tablet
        statusLegend.style.right = '15px';
        statusLegend.style.left = 'auto';
    } else { // Desktop
        if (sidebar.classList.contains('active')) {
            // Sidebar is open, position legend next to it
            statusLegend.style.right = `calc(var(--sidebar-width-desktop) + 20px)`;
            statusLegend.style.left = 'auto';
        } else {
            // Sidebar is closed (or not 'active' on desktop means it's not shown as overlay)
            // Position relative to viewport edge if sidebar isn't a factor here
            statusLegend.style.right = '20px';
            statusLegend.style.left = 'auto';
        }
    }
}
