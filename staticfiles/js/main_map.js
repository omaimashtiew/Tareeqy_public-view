// static/js/main_map.js
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded and parsed.");
    const mapDiv = document.getElementById('map');
    if (!mapDiv) {
        console.error("MAIN_MAP.JS: Map div (#map) not found. Cannot initialize map.");
        document.body.innerHTML = '<div style="padding:20px;text-align:center;color:red;font-size:1.2em;">خطأ حرج: حاوية الخريطة غير موجودة. لا يمكن تشغيل التطبيق.</div>';
        return;
    }

    initializeMap(); // From map_config.js

    if (map) {
        parseInitialFenceData(); // Assuming this function exists elsewhere and populates initialFencesData
        processAndDisplayFences(); // Assuming this function exists and uses initialFencesData

        // Attempt to get user location. This will use stored location if available & suitable,
        // then start watching for live updates. Predictions will be fetched internally by location.js.
        attemptInitialUserLocation(); // From location.js

        setupUIEventListeners(); // Assuming this function exists
        setupSearchEventListeners(); // Assuming this function exists

        if (typeof setupRoutePlannerEventListeners === 'function') {
            setupRoutePlannerEventListeners();
        } else {
            console.warn("MAIN_MAP.JS: setupRoutePlannerEventListeners is not defined.");
        }

        // Map invalidation for potential layout issues (e.g., hidden map div)
        setTimeout(() => {
            if (map) {
                map.invalidateSize();
                if (map.getSize().x === 0 || map.getSize().y === 0) {
                    console.error("MAP STILL HAS ZERO SIZE. CHECK CSS LAYOUT AND TIMING.");
                }
            }
        }, 350); // Slightly increased delay

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
                        console.log("MAIN_MAP.JS: Updating open popup with existing prediction data for fence ID:", fenceId);
                        updateOpenPopupWithSpecificPrediction(placeholder, relevantPrediction); // From location.js
                    } else if (currentUserLocation) { // currentUserLocation from location.js
                        console.log("MAIN_MAP.JS: No specific prediction for fence ID:", fenceId, ". User location known. Placeholder will show loading state.");
                        // location.js's updateOpenPopupWithSpecificPrediction handles the "loading..." state if no specific prediction.
                        // If you want to trigger a specific fetch for this *one* point, that's more complex.
                        // For now, rely on the periodic/movement-based fetch in location.js
                        updateOpenPopupWithSpecificPrediction(placeholder, null); // Show loading/unavailable state
                    } else {
                        console.log("MAIN_MAP.JS: No user location to fetch predictions for fence ID:", fenceId);
                         updateOpenPopupWithSpecificPrediction(placeholder, null); // Show "locate yourself" state
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

// Make sure parseInitialFenceData() and processAndDisplayFences() are defined
// Example stubs if they are not already in your project:
/*
let initialFencesData = []; // Should be populated by Django template or an API call

function parseInitialFenceData() {
    const fencesDataElement = document.getElementById('fences-data');
    if (fencesDataElement) {
        try {
            initialFencesData = JSON.parse(fencesDataElement.textContent);
            console.log("MAIN_MAP.JS: Parsed initial fence data:", initialFencesData.length, "fences");
        } catch (e) {
            console.error("MAIN_MAP.JS: Error parsing initial fence data:", e);
        }
    } else {
        console.warn("MAIN_MAP.JS: fences-data script tag not found.");
    }
}

function processAndDisplayFences() {
    if (!map || !initialFencesData || initialFencesData.length === 0) {
        console.warn("MAIN_MAP.JS: Map not ready or no initial fences to display.");
        return;
    }
    initialFencesData.forEach(fence => {
        // This is just an example, adapt to your actual addCheckpointMarkerToMap function
        if (typeof addCheckpointMarkerToMap === 'function') {
            addCheckpointMarkerToMap(fence);
        } else {
            console.warn("MAIN_MAP.JS: addCheckpointMarkerToMap function not found. Cannot display fence:", fence.name);
        }
    });
}
*/