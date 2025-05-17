// static/js/location.js

let currentUserLocation = null;
let locationWatchId = null;
const locationErrorModalInstance = bootstrap.Modal.getOrCreateInstance(document.getElementById('location-error-modal'));
window.latestPredictionData = null; // Stores the array of fence predictions

function attemptInitialUserLocation() {
    const storedLat = localStorage.getItem('userLatitude');
    const storedLng = localStorage.getItem('userLongitude');
    const storedTimestamp = localStorage.getItem('locationTimestamp');
    const fiveMinutesAgo = new Date().getTime() - (5 * 60 * 1000);

    if (storedLat && storedLng && storedTimestamp && parseInt(storedTimestamp) > fiveMinutesAgo) {
        console.log("LOCATION.JS: Using recent location from localStorage.");
        const locationData = {
            coords: {
                latitude: parseFloat(storedLat),
                longitude: parseFloat(storedLng),
                accuracy: parseFloat(localStorage.getItem('userAccuracy') || 500)
            }
        };
        handleLocationSuccess(locationData);
        return true;
    }

    const storedError = localStorage.getItem('locationError');
    if (storedError) {
        try {
            const errorData = JSON.parse(storedError);
            if (errorData.timestamp && parseInt(errorData.timestamp) > fiveMinutesAgo) {
                console.log("LOCATION.JS: Using stored location error from localStorage.");
                handleLocationError(errorData, true); // true to indicate it's from storage
                return true;
            }
        } catch (e) { console.error("LOCATION.JS: Error parsing stored locationError:", e); }
    }

    requestUserLocation(false);
    return false;
}

function requestUserLocation(isManualRetry = false) {
    if (!navigator.geolocation) {
        showToast('خدمة تحديد الموقع غير مدعومة في متصفحك.', 'danger');
        handleLocationError({ code: 'NOT_SUPPORTED', message: 'Geolocation not supported' });
        return;
    }

    const toastMessage = isManualRetry
        ? '<div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2" role="status"></div>جاري إعادة محاولة تحديد موقعك...</div>'
        : '<div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2" role="status"></div>جاري تحديد موقعك الحالي...</div>';
    const toastType = isManualRetry ? 'primary' : 'info';

    showToast(toastMessage, toastType, isManualRetry ? 10000 : 7000);

    if (locationWatchId !== null) navigator.geolocation.clearWatch(locationWatchId);

    navigator.geolocation.getCurrentPosition(
        handleLocationSuccess,
        (error) => handleLocationError(error, false), // Pass false for isFromStorage
        { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
    );
}

function handleLocationSuccess(position) {
    currentUserLocation = {
        lat: position.coords.latitude,
        lng: position.coords.longitude
    };
    const accuracy = position.coords.accuracy;

    console.log("LOCATION.JS: Location found:", currentUserLocation, "Accuracy:", accuracy);
    localStorage.setItem('userLatitude', currentUserLocation.lat.toString());
    localStorage.setItem('userLongitude', currentUserLocation.lng.toString());
    localStorage.setItem('userAccuracy', accuracy.toString());
    localStorage.setItem('locationTimestamp', new Date().getTime().toString());
    localStorage.removeItem('locationError');

    showToast('تم تحديد موقعك بنجاح!', 'success', 3000);

    if (userLocationMarker) userLocationMarker.remove();
    if (accuracyCircle) accuracyCircle.remove();

    userLocationMarker = L.marker(currentUserLocation, { icon: icons.userLocation, zIndexOffset: 1000 })
        .addTo(map)
        .bindPopup(`موقعك الحالي (دقة ~${accuracy.toFixed(0)} متر)`);

    if (accuracy < MAX_ACCURACY_RADIUS_METERS) {
        accuracyCircle = L.circle(currentUserLocation, accuracy, {
            color: 'var(--primary-color)', fillColor: 'var(--primary-color)',
            fillOpacity: 0.15, weight: 2, interactive: false
        }).addTo(map);
    }

    map.flyTo(currentUserLocation, DETAILED_ZOOM, { animate: true, duration: 1.0 });
    setTimeout(() => {
      if (userLocationMarker && map.hasLayer(userLocationMarker)) userLocationMarker.openPopup();
    }, 1100);

    fetchPredictionsForLocation(currentUserLocation, false);
}

function handleLocationError(error, isFromStorage = false) {
    console.error("LOCATION.JS: Geolocation Error Code:", error.code, "Message:", error.message);
    let displayMessage = "حدث خطأ غير معروف أثناء محاولة تحديد موقعك.";
    const errorCode = error.code ? error.code.toString() : (error.message || 'UNKNOWN_ERROR_FORMAT');

    switch (errorCode) {
        case '1':
        case 'PERMISSION_DENIED':
            displayMessage = "تم رفض إذن الوصول للموقع. يرجى تمكينها من إعدادات المتصفح/الجهاز.";
            if (!isFromStorage && locationErrorModalInstance) locationErrorModalInstance.show();
            else if (!isFromStorage) console.warn("Location error modal instance not found, but should show.");
            break;
        case '2':
        case 'POSITION_UNAVAILABLE':
            displayMessage = "معلومات الموقع غير متوفرة حاليًا. تأكد من تفعيل GPS ووجود إشارة جيدة.";
            if (!isFromStorage) showToast(displayMessage, 'warning', 7000);
            break;
        case '3':
        case 'TIMEOUT':
            displayMessage = "انتهت مهلة طلب الموقع. الشبكة قد تكون ضعيفة أو GPS يستغرق وقتًا أطول.";
            if (!isFromStorage) showToast(displayMessage, 'warning', 7000);
            break;
        case 'NOT_SUPPORTED':
             displayMessage = "خدمة تحديد الموقع غير مدعومة في متصفحك.";
             if (!isFromStorage) showToast(displayMessage, 'danger');
             break;
        default:
            if (!isFromStorage) showToast(displayMessage + ` (رمز الخطأ: ${errorCode})`, 'danger');
    }

    if (!isFromStorage && typeof error.code === 'number') {
        localStorage.setItem('locationError', JSON.stringify({
            code: error.code, message: error.message,
            timestamp: new Date().getTime().toString()
        }));
    }
    currentUserLocation = null;
    updateOpenPopupWithPrediction();
}


function fetchPredictionsForLocation(location, silently = false) {
    if (!location) {
        console.warn("LOCATION.JS (fetchPredictionsForLocation): Cannot fetch predictions, user location is unknown.");
        window.latestPredictionData = null;
        updateOpenPopupWithPrediction();
        return;
    }
    if (!silently) {
        showToast('<div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2" role="status"></div>جاري جلب توقعات نقاط التفتيش...</div>', 'info', 4000);
    }
    console.log("LOCATION.JS (fetchPredictionsForLocation): Fetching predictions for location:", location);

    fetch(API_URL_GET_PREDICTIONS, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        body: JSON.stringify({ latitude: location.lat, longitude: location.lng })
    })
    .then(response => {
        console.log("LOCATION.JS (fetchPredictionsForLocation): API Response status:", response.status);
        if (!response.ok) {
            return response.json().then(errData => { // Try to parse JSON error from backend
                 throw new Error(errData.error || `خطأ بالخادم: ${response.status} ${response.statusText}`);
            }).catch(() => { // Fallback if error response is not JSON
                throw new Error(`خطأ بالخادم: ${response.status} ${response.statusText}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log("LOCATION.JS (fetchPredictionsForLocation): API Response data (raw):", JSON.stringify(data)); // Log the whole response as string
        if (data.error) {
            console.error("LOCATION.JS (fetchPredictionsForLocation): API returned an error in data object:", data.error);
            throw new Error(data.error);
        }
        window.latestPredictionData = data.fences; // This should be an array
        console.log("LOCATION.JS (fetchPredictionsForLocation): Stored window.latestPredictionData (type: " + typeof window.latestPredictionData + ", isArray: " + Array.isArray(window.latestPredictionData) + "):", window.latestPredictionData);
        updateOpenPopupWithPrediction();
        if (!silently && data.fences && data.fences.length > 0) {
            // showToast('تم تحديث توقعات نقاط التفتيش.', 'success', 2500);
        } else if (!silently && (!data.fences || data.fences.length === 0)) {
            // showToast('لا توجد توقعات لنقاط قريبة.', 'info', 3000);
        }
    })
    .catch(error => {
        console.error('LOCATION.JS (fetchPredictionsForLocation): Prediction fetch error:', error);
        if (!silently) showToast(`خطأ في جلب التوقعات: ${error.message}`, 'danger', 7000);
        window.latestPredictionData = null; // Clear old data on error
        updateOpenPopupWithPrediction(); // Update open popup to show error/unavailable
    });
}

function updateOpenPopupWithPrediction() {
    if (!map) {
        console.warn("LOCATION.JS (updateOpenPopupWithPrediction): Map object not available.");
        return;
    }
    const latestDataCount = window.latestPredictionData ? window.latestPredictionData.length : 'null or empty';
    const isLatestDataArray = Array.isArray(window.latestPredictionData);
    console.log(`LOCATION.JS (updateOpenPopupWithPrediction): Called. latestPredictionData count: ${latestDataCount}, isArray: ${isLatestDataArray}`);

    map.eachLayer(function (layer) {
        if (layer instanceof L.Marker && layer.isPopupOpen() && layer.options.fenceData) {
            const fenceIdFromMarker = layer.options.fenceData.id; 
            console.log(`LOCATION.JS (updateOpenPopupWithPrediction): Found open popup for fence ID from marker: ${fenceIdFromMarker} (type: ${typeof fenceIdFromMarker})`);
            
            const popupElement = layer.getPopup().getElement();
            if (!popupElement) {
                console.warn(`LOCATION.JS (updateOpenPopupWithPrediction): Popup element not found for fence ID: ${fenceIdFromMarker}`);
                return;
            }

            const placeholder = popupElement.querySelector(`.prediction-placeholder[data-fence-id="${fenceIdFromMarker}"]`);
            if (!placeholder) {
                 console.warn(`LOCATION.JS (updateOpenPopupWithPrediction): Prediction placeholder not found in open popup for fence ID: ${fenceIdFromMarker}`);
                 return;
            }

            let relevantPrediction = null;
            if (window.latestPredictionData && Array.isArray(window.latestPredictionData) && window.latestPredictionData.length > 0) {
                relevantPrediction = window.latestPredictionData.find(p => {
                    // console.log(`Comparing API prediction ID: ${p.id} (type: ${typeof p.id}) with Marker fence ID: ${fenceIdFromMarker} (type: ${typeof fenceIdFromMarker})`);
                    return String(p.id) === String(fenceIdFromMarker);
                });
            } else {
                console.log("LOCATION.JS (updateOpenPopupWithPrediction): window.latestPredictionData is null, empty, or not an array.");
            }
            
            console.log(`LOCATION.JS (updateOpenPopupWithPrediction): Relevant prediction for fence ID ${fenceIdFromMarker}:`, JSON.stringify(relevantPrediction, null, 2));
            updateOpenPopupWithSpecificPrediction(placeholder, relevantPrediction);
        }
    });
}

function updateOpenPopupWithSpecificPrediction(placeholderElement, predictionData) {
    if (!placeholderElement) {
        console.error("LOCATION.JS (updateOpenPopupWithSpecificPrediction): placeholderElement is null!");
        return;
    }
    console.log("LOCATION.JS (updateOpenPopupWithSpecificPrediction): Updating placeholder. Prediction Data Received for this specific fence:", JSON.stringify(predictionData, null, 2));

    let predictionHTML = '';
    if (predictionData) { // predictionData is the 'relevantPrediction' object for the specific fence
        console.log("LOCATION.JS (updateOpenPopupWithSpecificPrediction): predictionData for this fence is TRUTHY.");
        // Check for prediction_success and predicted_wait_minutes specifically
        if (predictionData.prediction_success === true && typeof predictionData.predicted_wait_minutes === 'number' && !isNaN(predictionData.predicted_wait_minutes)) {
            console.log("LOCATION.JS (updateOpenPopupWithSpecificPrediction): Condition for successful prediction MET. Wait minutes:", predictionData.predicted_wait_minutes);
            const waitTime = Math.round(predictionData.predicted_wait_minutes);
            predictionHTML = `
                <hr class="prediction-separator">
                <div class="popup-item prediction-info">
                    <span class="popup-icon"><i class="fas fa-hourglass-half"></i></span>
                    <span>وقت الانتظار المتوقع: <strong>${waitTime} دقيقة</strong></span>
                </div>`;
            if (predictionData.prediction_debug_info) { // Optional: for debugging purposes
                predictionHTML += `<div class="popup-item text-muted small" style="font-size:0.75em; opacity:0.7;">${predictionData.prediction_debug_info}</div>`;
            }
        } else if (predictionData.prediction_error) {
            console.log("LOCATION.JS (updateOpenPopupWithSpecificPrediction): Condition for prediction_error MET. Error:", predictionData.prediction_error);
            predictionHTML = `
                <hr class="prediction-separator">
                <div class="popup-item prediction-error">
                    <span class="popup-icon"><i class="fas fa-exclamation-circle"></i></span>
                    <span>التوقع: ${predictionData.prediction_error}</span>
                </div>`;
        } else { // Fallback if prediction_success is false but no error, or data format issue.
            console.log("LOCATION.JS (updateOpenPopupWithSpecificPrediction): Condition for 'no detailed prediction' or format issue MET. Success flag:", predictionData.prediction_success, "Wait minutes type:", typeof predictionData.predicted_wait_minutes, "Value:", predictionData.predicted_wait_minutes);
            predictionHTML = `
                <hr class="prediction-separator">
                <div class="popup-item text-muted" style="font-size: 0.85em;">
                    <span class="popup-icon"><i class="fas fa-info-circle"></i></span>
                    <span>لا توجد توقعات تفصيلية لهذه النقطة حالياً.</span>
                </div>`;
        }
    } else { // predictionData is null or undefined (meaning no relevant prediction was found for THIS specific fence)
         console.log("LOCATION.JS (updateOpenPopupWithSpecificPrediction): predictionData for this specific fence is FALSY. currentUserLocation:", currentUserLocation);
         if (currentUserLocation) {
            predictionHTML = `
                <hr class="prediction-separator">
                <div class="popup-item text-muted" style="font-size: 0.85em;">
                    <span class="popup-icon"><i class="fas fa-info-circle"></i></span>
                    <span>لا تتوفر توقعات لهذه النقطة حاليًا (قد تكون بعيدة جدًا أو خطأ في البيانات).</span>
                </div>`;
         } else {
            predictionHTML = `
                <hr class="prediction-separator">
                <div class="popup-item text-muted" style="font-size: 0.85em;">
                    <span class="popup-icon"><i class="fas fa-map-marker-alt"></i></span>
                    <span>حدد موقعك للحصول على التوقعات.</span>
                </div>`;
         }
    }
    placeholderElement.innerHTML = predictionHTML;
    console.log("LOCATION.JS (updateOpenPopupWithSpecificPrediction): Placeholder HTML set for the popup.");
}