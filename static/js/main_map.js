// static/js/main_map.js

document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded and parsed.");
    const mapDiv = document.getElementById('map');
    if (!mapDiv) {
        console.error("MAIN_MAP.JS: Map div (#map) not found. Cannot initialize map.");
        document.body.innerHTML = '<div style="padding:20px;text-align:center;color:red;font-size:1.2em;">خطأ حرج: حاوية الخريطة غير موجودة. لا يمكن تشغيل التطبيق.</div>';
        return; 
    }
    // console.log("Map div found. Initial clientHeight:", mapDiv.clientHeight, "clientWidth:", mapDiv.clientWidth);

    initializeMap(); 
    
    if (map) {
        // console.log("MAIN_MAP.JS: Leaflet map object IS available.");
        parseInitialFenceData(); 
        processAndDisplayFences(); 
        attemptInitialUserLocation(); 

        setupUIEventListeners(); 
        setupSearchEventListeners(); 
        setupRoutePlannerEventListeners(); 

        setTimeout(() => {
            if (map) {
                // const mapContainer = map.getContainer();
                // console.log("MAIN_MAP.JS: Calling initial map.invalidateSize(). Map container clientHeight:", mapContainer.clientHeight);
                map.invalidateSize();
                // console.log("MAIN_MAP.JS: Map size after invalidateSize():", map.getSize());
                if (map.getSize().x === 0 || map.getSize().y === 0) {
                    console.error("MAP STILL HAS ZERO SIZE. CHECK CSS LAYOUT.");
                }
            }
        }, 300);

        window.addEventListener('resize', debounce(() => {
            if (map) {
                // console.log("MAIN_MAP.JS: Window resized, calling map.invalidateSize()");
                map.invalidateSize();
            }
        }, 250));

        map.on('popupopen', function(e) {
            console.log("MAIN_MAP.JS: Popup opened for a marker.");
            if (e.popup && e.popup._source && e.popup._source.options.fenceData) {
                const fenceId = e.popup._source.options.fenceData.id;
                const popupElement = e.popup.getElement();
                if (!popupElement) return;
                const placeholder = popupElement.querySelector(`.prediction-placeholder[data-fence-id="${fenceId}"]`);
                
                if (placeholder) {
                    const existingPredictionForThisFence = window.latestPredictionData 
                        ? window.latestPredictionData.find(p => p.id === fenceId) 
                        : null;

                    if (existingPredictionForThisFence) {
                        console.log("MAIN_MAP.JS: Updating open popup with existing prediction data for fence ID:", fenceId);
                        updateOpenPopupWithSpecificPrediction(placeholder, existingPredictionForThisFence);
                    } else if (currentUserLocation) {
                        console.log("MAIN_MAP.JS: No specific prediction for fence ID:", fenceId, "in current batch. User location known. Triggering silent fetch.");
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
                    console.warn("MAIN_MAP.JS: Prediction placeholder not found in open popup for fence ID:", fenceId);
                }
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
