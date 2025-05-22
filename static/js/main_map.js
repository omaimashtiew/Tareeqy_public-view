// static/js/main_map.js
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded and parsed.");
    const mapDiv = document.getElementById('map');
    if (!mapDiv) {
        console.error("MAIN_MAP.JS: Map div (#map) not found. Cannot initialize map.");
        document.body.innerHTML = '<div style="padding:20px;text-align:center;color:red;font-size:1.2em;">خطأ حرج: حاوية الخريطة غير موجودة. لا يمكن تشغيل التطبيق.</div>';
        return; 
    }

    initializeMap(); 
    
    if (map) {
        parseInitialFenceData(); 
        processAndDisplayFences(); 
        attemptInitialUserLocation(); 

        setupUIEventListeners(); 
        setupSearchEventListeners(); 
        
        // Check if setupRoutePlannerEventListeners is defined before calling
        if (typeof setupRoutePlannerEventListeners === 'function') {
            setupRoutePlannerEventListeners(); 
        } else {
            console.warn("MAIN_MAP.JS: setupRoutePlannerEventListeners is not defined. Route planning features might be affected.");
        }


        setTimeout(() => {
            if (map) {
                map.invalidateSize();
                if (map.getSize().x === 0 || map.getSize().y === 0) {
                    console.error("MAP STILL HAS ZERO SIZE. CHECK CSS LAYOUT.");
                }
            }
        }, 300);
if (currentUserLocation) {
    fetchPredictionsForLocation(currentUserLocation, true); // جلب صامت (بدون رسائل)
}
        window.addEventListener('resize', debounce(() => {
            if (map) {
                map.invalidateSize();
            }
        }, 250));

        map.on('popupopen', function(e) {
            console.log("MAIN_MAP.JS: Popup opened event triggered.");
            if (e.popup && e.popup._source && e.popup._source.options.fenceData) {
                const fenceId = e.popup._source.options.fenceData.id;
                const popupElement = e.popup.getElement();
                console.log("MAIN_MAP.JS: Popup opened for fence ID:", fenceId);

                if (!popupElement) {
                    console.warn("MAIN_MAP.JS: Popup element not found for fence ID:", fenceId);
                    return;
                }
                const placeholder = popupElement.querySelector(`.prediction-placeholder[data-fence-id="${fenceId}"]`);
                
                if (placeholder) {
                    console.log("MAIN_MAP.JS: Prediction placeholder found for fence ID:", fenceId);
                    let relevantPrediction = null;
                    if (window.latestPredictionData && Array.isArray(window.latestPredictionData)) {
                         relevantPrediction = window.latestPredictionData.find(p => String(p.id) === String(fenceId));
                    }

                    if (relevantPrediction) {
                        console.log("MAIN_MAP.JS: Updating open popup with existing prediction data for fence ID:", fenceId, "Data:", relevantPrediction);
                        updateOpenPopupWithSpecificPrediction(placeholder, relevantPrediction);
                    } else if (currentUserLocation) {
                        console.log("MAIN_MAP.JS: No specific prediction for fence ID:", fenceId, "in current batch (window.latestPredictionData). User location known. Triggering silent fetch IF NOT RECENTLY FETCHED.");
                        // To prevent rapid re-fetching, you might add a timestamp check here
                        // For now, it will always re-fetch if data for this specific fence isn't immediately available.
                        placeholder.innerHTML = `
                            <hr class="prediction-separator">
                            <div class="popup-item text-muted" style="font-size: 0.85em;">
                                <span class="popup-icon"><i class="fas fa-spinner fa-spin"></i></span>
                                <span>جاري تحديث التوقعات...</span>
                            </div>`;
                        fetchPredictionsForLocation(currentUserLocation, true); // true for silent fetch
                    } else {
                        console.log("MAIN_MAP.JS: No user location to fetch predictions for fence ID:", fenceId);
                        placeholder.innerHTML = `
                            <hr class="prediction-separator">
                            <div class="popup-item text-muted" style="font-size: 0.85em;">
                                <span class="popup-icon"><i class="fas fa-map-marker-alt"></i></span>
                                <span>حدد موقعك للحصول على التوقعات.</span>
                            </div>`;
                    }
                } else {
                    console.warn("MAIN_MAP.JS: Prediction placeholder NOT found in open popup for fence ID:", fenceId);
                }
            } else {
                 console.warn("MAIN_MAP.JS: Popup opened, but no valid popup, source, or fenceData found.");
            }
        });

    } else {
        console.error("MAIN_MAP.JS: Leaflet map object was NOT initialized!");
    }
    console.log("Tareeqy Map Application Initialized attempt complete.");
});

function debounce(func, delay) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), delay);
    };
}