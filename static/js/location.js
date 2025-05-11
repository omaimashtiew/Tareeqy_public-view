// static/js/location.js

let currentUserLocation = null; 
let locationWatchId = null; 
const locationErrorModalInstance = bootstrap.Modal.getOrCreateInstance(document.getElementById('location-error-modal')); // Use Bootstrap's getOrCreateInstance
window.latestPredictionData = null; 

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
                handleLocationError(errorData); 
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
        handleLocationError,
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

    showToast('تم تحديد موقعك بنجاح!', 'success', 3000); // Shorter success toast

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

function handleLocationError(error) {
    console.error("LOCATION.JS: Geolocation Error Code:", error.code, "Message:", error.message);
    let displayMessage = "حدث خطأ غير معروف أثناء محاولة تحديد موقعك.";
    const errorCode = error.code ? error.code.toString() : 'UNKNOWN_ERROR_FORMAT'; 

    switch (errorCode) {
        case '1': 
            displayMessage = "تم رفض إذن الوصول للموقع. يرجى تمكينها من إعدادات المتصفح/الجهاز.";
            if (locationErrorModalInstance) locationErrorModalInstance.show(); 
            else console.error("Location error modal instance not found");
            break;
        case '2': 
            displayMessage = "معلومات الموقع غير متوفرة حاليًا. تأكد من تفعيل GPS ووجود إشارة جيدة.";
            showToast(displayMessage, 'warning', 7000);
            break;
        case '3': 
            displayMessage = "انتهت مهلة طلب الموقع. الشبكة قد تكون ضعيفة أو GPS يستغرق وقتًا أطول.";
            showToast(displayMessage, 'warning', 7000);
            break;
        case 'GEOLOCATION_NOT_SUPPORTED': 
             displayMessage = "خدمة تحديد الموقع غير مدعومة في متصفحك.";
             showToast(displayMessage, 'danger');
             break;
        default:
            showToast(displayMessage + ` (رمز الخطأ: ${errorCode})`, 'danger');
    }
    if (typeof error.code === 'number') { 
        localStorage.setItem('locationError', JSON.stringify({
            code: error.code, message: error.message, 
            timestamp: new Date().getTime().toString()
        }));
    }
}

function fetchPredictionsForLocation(location, silently = false) {
    if (!location) {
        console.warn("LOCATION.JS: Cannot fetch predictions, user location is unknown.");
        updateOpenPopupWithPrediction(); // Will show appropriate message if popup is open
        return;
    }
    if (!silently) {
        showToast('<div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2" role="status"></div>جاري جلب توقعات نقاط التفتيش...</div>', 'info', 4000);
    }

    fetch(API_URL_GET_PREDICTIONS, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        body: JSON.stringify({ latitude: location.lat, longitude: location.lng })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errData => {
                 throw new Error(errData.error || `خطأ بالخادم: ${response.status} ${response.statusText}`);
            }).catch(() => { 
                throw new Error(`خطأ بالخادم: ${response.status} ${response.statusText}`);
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.error) throw new Error(data.error);
        window.latestPredictionData = data.fences; 
        console.log("LOCATION.JS: Predictions fetched and stored:", window.latestPredictionData);
        updateOpenPopupWithPrediction(); // This will update any open popup
        // Optionally show a success toast, but might be too noisy if predictions update frequently
        // if (!silently && data.fences && data.fences.length > 0) {
        //     showToast('تم تحديث توقعات نقاط التفتيش.', 'success', 2000); 
        // }
    })
    .catch(error => {
        console.error('LOCATION.JS: Prediction fetch error:', error);
        if (!silently) showToast(`خطأ في جلب التوقعات: ${error.message}`, 'danger', 7000);
        window.latestPredictionData = null; // Clear old data on error
        updateOpenPopupWithPrediction(); // Update open popup to show error/unavailable
    });
}

// This function updates ANY open popup based on window.latestPredictionData
function updateOpenPopupWithPrediction() {
    if (!map) return;
    map.eachLayer(function (layer) {
        if (layer instanceof L.Marker && layer.isPopupOpen() && layer.options.fenceData) {
            const fenceId = layer.options.fenceData.id;
            const popupElement = layer.getPopup().getElement();
            if (!popupElement) return;

            const placeholder = popupElement.querySelector(`.prediction-placeholder[data-fence-id="${fenceId}"]`);
            if (!placeholder) {
                 console.warn("LOCATION.JS: Prediction placeholder not found in open popup for fence ID:", fenceId);
                 return;
            }
            
            const relevantPrediction = window.latestPredictionData 
                ? window.latestPredictionData.find(p => p.id === fenceId) 
                : null; // If latestPredictionData is null (e.g., after an error), relevantPrediction will be null

            updateOpenPopupWithSpecificPrediction(placeholder, relevantPrediction);
        }
    });
}

// Helper function to populate a specific placeholder with specific prediction data
function updateOpenPopupWithSpecificPrediction(placeholderElement, predictionData) {
    if (!placeholderElement) return;

    let predictionHTML = '';
    if (predictionData) { // We have some prediction object for this fence
        console.log("LOCATION.JS: Rendering specific prediction for placeholder:", predictionData);
        if (predictionData.prediction_success && predictionData.predicted_jam_probability_percent !== null) {
            predictionHTML = `
                <hr class="prediction-separator">
                <div class="popup-item prediction-info">
                    <span class="popup-icon"><i class="fas fa-hourglass-half"></i></span>
                    <span>وقت الوصول المقدر: ~${formatTimeOnly(predictionData.prediction_arrival_time_iso)}</span>
                </div>
                <div class="popup-item prediction-info">
                    <span class="popup-icon"><i class="fas fa-percentage"></i></span>
                    <span>احتمالية الازدحام: <strong>${predictionData.predicted_jam_probability_percent}%</strong></span>
                </div>`;
        } else if (predictionData.prediction_error) {
            predictionHTML = `
                <hr class="prediction-separator">
                <div class="popup-item prediction-error">
                    <span class="popup-icon"><i class="fas fa-exclamation-circle"></i></span>
                    <span>التوقع: ${predictionData.prediction_error}</span>
                </div>`;
        } else { // Prediction was 'successful' but no specific data (e.g., AI decided not applicable)
            predictionHTML = `
                <hr class="prediction-separator">
                <div class="popup-item text-muted" style="font-size: 0.85em;">
                    <span class="popup-icon"><i class="fas fa-info-circle"></i></span>
                    <span>لا توجد توقعات تفصيلية لهذه النقطة حالياً.</span>
                </div>`;
        }
    } else { // No prediction object found for this fence in the latest batch, or latestPredictionData is null
         console.log("LOCATION.JS: No specific prediction data for this placeholder, showing appropriate message.");
         if (currentUserLocation) { // We tried, but no data for *this* fence
            predictionHTML = `
                <hr class="prediction-separator">
                <div class="popup-item text-muted" style="font-size: 0.85em;">
                    <span class="popup-icon"><i class="fas fa-info-circle"></i></span>
                    <span>لا تتوفر توقعات لهذه النقطة حاليًا.</span>
                </div>`;
         } else { // We don't even have user location to make a request
            predictionHTML = `
                <hr class="prediction-separator">
                <div class="popup-item text-muted" style="font-size: 0.85em;">
                    <span class="popup-icon"><i class="fas fa-map-marker-alt"></i></span>
                    <span>حدد موقعك للحصول على التوقعات.</span>
                </div>`;
         }
    }
    placeholderElement.innerHTML = predictionHTML;
}


// This function is mostly for a direct error during fetch, not if a specific fence just lacks data.
// It's less used now that updateOpenPopupWithSpecificPrediction handles null predictionData.
// function clearPredictionInOpenPopup(message = "تعذر تحميل بيانات التوقع.") { ... }