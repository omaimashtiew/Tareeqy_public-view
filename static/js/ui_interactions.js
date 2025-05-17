// static/js/ui_interactions.js

const sidebar = document.getElementById('sidebar');
const contentWrapper = document.getElementById('content-wrapper'); 
const statusLegend = document.getElementById('status-legend');
let activeStatusFilters = ['open', 'sever_traffic_jam', 'closed', 'unknown']; 

function setupUIEventListeners() {
    const toggleSidebarBtn = document.getElementById('footer-toggle-sidebar-btn');
    const closeSidebarBtn = document.getElementById('close-sidebar-btn'); // Mobile only

    if (toggleSidebarBtn) {
        toggleSidebarBtn.addEventListener('click', toggleSidebar);
    }
    if (closeSidebarBtn && window.innerWidth < 992) { // Only attach for mobile view initially
        closeSidebarBtn.addEventListener('click', toggleSidebar);
    }

    const zoomInBtn = document.getElementById('zoom-in-btn');
    const zoomOutBtn = document.getElementById('zoom-out-btn');
    if (zoomInBtn) zoomInBtn.addEventListener('click', () => map.zoomIn());
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => map.zoomOut());

    const locateUserBtn = document.getElementById('locate-user-btn');
    const retryLocationModalBtn = document.getElementById('retry-location-modal-btn');
    if (locateUserBtn) locateUserBtn.addEventListener('click', () => requestUserLocation(true)); 
    if (retryLocationModalBtn) {
        retryLocationModalBtn.addEventListener('click', () => {
            const errorModal = document.getElementById('location-error-modal');
            if (errorModal) {
                const modalInstance = bootstrap.Modal.getInstance(errorModal);
                if (modalInstance) modalInstance.hide();
            }
            requestUserLocation(true); 
        });
    }
    
    document.querySelectorAll('.filter-section .form-check-input').forEach(checkbox => {
        checkbox.addEventListener('change', handleStatusFilterChange);
    });

    const updateBtn = document.getElementById('footer-update-btn');
    if (updateBtn) {
        updateBtn.addEventListener('click', refreshMapData);
    }
    
    handleResizeOrLoad(); 
    window.addEventListener('resize', debounce(handleResizeOrLoad, 150)); // Debounce resize

    // Initial state for desktop: sidebar should be collapsed (CSS handles this by default width)
    // No explicit JS needed to remove 'active' on load for desktop if CSS defaults to collapsed.
}

function toggleSidebar() {
    if (!sidebar || !contentWrapper) return;
    
    const isActive = sidebar.classList.toggle('active');

    // For desktop, add/remove a class to contentWrapper for CSS to adjust floating elements
    if (window.innerWidth >= 992) {
        if (isActive) {
            contentWrapper.classList.add('sidebar-active');
        } else {
            contentWrapper.classList.remove('sidebar-active');
        }
    }
    
    setTimeout(() => {
        if (map) map.invalidateSize({ animate: true });
    }, 310); 
}


function handleStatusFilterChange() {
    activeStatusFilters = Array.from(document.querySelectorAll('.filter-section .form-check-input:checked'))
                               .map(cb => cb.value);
    applyStatusFilters();
}

function applyStatusFilters() {
    if (!map || !window.processedFences) { 
        console.warn("UI_INTERACTIONS: Map or processedFences not ready for filtering.");
        return;
    }
    window.processedFences.forEach(fence => {
        const marker = fence.marker; 
        if (!marker) return;

        const fenceStatus = fence.status || 'unknown'; 
        const layerGroup = window.markerLayers[fenceStatus] || window.markerLayers.unknown;

        if (activeStatusFilters.includes(fenceStatus)) {
            if (layerGroup && !map.hasLayer(marker)) { 
                marker.addTo(layerGroup); 
                if (!map.hasLayer(layerGroup)) { 
                    map.addLayer(layerGroup);
                }
            } else if (!layerGroup && !map.hasLayer(marker)) { 
                 marker.addTo(map);
            }
        } else { 
            if (map.hasLayer(marker)) {
                marker.remove(); 
            }
        }
    });
}

function refreshMapData() {
    if (typeof showToast !== 'function') { 
        console.warn("showToast function not available for refreshMapData status.");
    } else {
        showToast('<div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2" role="status"></div>جاري تحديث البيانات...</div>', 'info', 3000);
    }
    
    if (typeof parseInitialFenceData === 'function' && typeof processAndDisplayFences === 'function') {
        parseInitialFenceData(); 
        processAndDisplayFences(); 
    } else {
        console.error("UI_INTERACTIONS: parseInitialFenceData or processAndDisplayFences not found.");
    }
    
    if (window.currentUserLocation && typeof fetchPredictionsForLocation === 'function') {
        fetchPredictionsForLocation(window.currentUserLocation, true); 
    }
    if (typeof showToast === 'function') showToast('تم تحديث بيانات الخريطة.', 'success');
}

function showToast(message, type = 'info', duration = 5000) {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        // console.error("Toast container not found!"); // Can be noisy if toast is optional
        return;
    }

    const toastId = 'toast-' + Date.now();
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
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
}

function handleResizeOrLoad() {
    if (!map) return;

    // iOS viewport height fix
    const setVh = () => {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    };
    setVh(); // Set on initial load
    // No need to re-add listener if it's already on window by setupUIEventListeners calling this once.
    // But if called standalone, this ensures it's set up if not already:
    if (!window.vhResizeListenerAttached) {
        window.addEventListener('resize', setVh);
        window.vhResizeListenerAttached = true;
    }


    // Ensure sidebar state and floating elements are correct on load/resize
    if (window.innerWidth >= 992) { // Desktop
        // If sidebar is active, ensure contentWrapper has the class too.
        if (sidebar && sidebar.classList.contains('active')) {
            if(contentWrapper) contentWrapper.classList.add('sidebar-active');
        } else {
            if(contentWrapper) contentWrapper.classList.remove('sidebar-active');
        }
        // Hide mobile-specific close button
        const closeSidebarBtn = document.getElementById('close-sidebar-btn');
        if(closeSidebarBtn) closeSidebarBtn.style.display = 'none';

    } else { // Mobile
        if(contentWrapper) contentWrapper.classList.remove('sidebar-active'); // Not needed for mobile overlay
         // Show mobile-specific close button
        const closeSidebarBtn = document.getElementById('close-sidebar-btn');
        if(closeSidebarBtn) closeSidebarBtn.style.display = 'block';
    }
     if (map) map.invalidateSize(); // Always good to call after potential layout changes
}

// Debounce utility
function debounce(func, delay) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), delay);
    };
}