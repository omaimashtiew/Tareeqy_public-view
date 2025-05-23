// static/js/location.js

let currentUserLocation = null; // { lat: number, lng: number, accuracy: number }
let locationWatchId = null;
const locationErrorModalInstance = bootstrap.Modal.getOrCreateInstance(document.getElementById('location-error-modal'));
window.latestPredictionData = null;

const AVG_SPEED_KMH = 21;

// --- Location Constants ---
const LOCATION_OPTIONS = {
    enableHighAccuracy: true,
    timeout: 25000, // 25 seconds for each attempt within watchPosition
    maximumAge: 0    // Force fresh location
};
const RECENT_STORED_LOCATION_MAX_AGE_MS = 5 * 60 * 1000; // 5 minutes
const ACCEPTABLE_STORED_ACCURACY_METERS = 500; // Use stored if accuracy is better than this
const MIN_DESIRED_ACCURACY_METERS = 100; // A "good" accuracy level
const MAX_ACCEPTABLE_ACCURACY_METERS = 1000; // Location with accuracy worse than this gets a warning
const PREDICTION_FETCH_DISTANCE_THRESHOLD_METERS = 100; // Fetch predictions if user moves > this

let isFirstLocationUpdateFromWatch = true; // True until first successful update from watchPosition
let lastLocationUpdateTimestamp = 0;
let lastFetchedPredictionsLocation = null; // { lat, lng }

// --- Toast Helper Stubs (Adapt to your actual implementation) ---
// Ensure these are globally available or move them to a shared utility file.
// This is a very basic example using Bootstrap's toast component.
// You'll need a container in your HTML like:
// <div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index: 1100"></div>
function showToast(message, type = 'info', duration = 5000, toastId = null) {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        console.warn('Toast container not found. Message:', message);
        alert(`${type.toUpperCase()}: ${message}`); // Fallback
        return;
    }

    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white bg-${type} border-0`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');
    if (toastId) toastEl.id = toastId;

    const autohide = duration > 0;
    if (autohide) {
        toastEl.setAttribute('data-bs-delay', duration);
        toastEl.setAttribute('data-bs-autohide', 'true');
    } else {
        toastEl.setAttribute('data-bs-autohide', 'false');
    }

    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    toastContainer.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

function dismissToast(toastId) {
    const toastElement = document.getElementById(toastId);
    if (toastElement) {
        const toastInstance = bootstrap.Toast.getInstance(toastElement);
        if (toastInstance) {
            toastInstance.hide();
        } else {
            toastElement.remove(); // Fallback if instance not found but element exists
        }
    }
}
// --- End Toast Helper Stubs ---


function calculateTravelTime(distanceKm) {
    const hours = distanceKm / AVG_SPEED_KMH;
    const minutes = Math.round(hours * 60);
    return minutes;
}

function formatWaitTime(minutes) {
    if (typeof minutes !== 'number' || isNaN(minutes)) return 'غير متوفر';
    minutes = Math.round(minutes);
    if (minutes < 1) return 'أقل من دقيقة';
    if (minutes < 60) return `${minutes} دقيقة`;
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    const hoursText = hours === 1 ? `ساعة` : `${hours} ساعات`;
    if (remainingMinutes === 0) return hoursText;
    return `${hoursText} و ${remainingMinutes} دقيقة`;
}

function attemptInitialUserLocation() {
    console.log("LOCATION.JS: Attempting to determine initial user location...");
    const storedLat = localStorage.getItem('userLatitude');
    const storedLng = localStorage.getItem('userLongitude');
    const storedTimestampStr = localStorage.getItem('locationTimestamp');
    const storedAccuracyStr = localStorage.getItem('userAccuracy');

    if (storedLat && storedLng && storedTimestampStr) {
        const storedTimestamp = parseInt(storedTimestampStr, 10);
        const locationAge = Date.now() - storedTimestamp;

        if (locationAge < RECENT_STORED_LOCATION_MAX_AGE_MS) {
            const storedAccuracy = storedAccuracyStr ? parseFloat(storedAccuracyStr) : (ACCEPTABLE_STORED_ACCURACY_METERS + 1);
            if (storedAccuracy <= ACCEPTABLE_STORED_ACCURACY_METERS) {
                console.log(`LOCATION.JS: Using recent and acceptable stored location (Accuracy: ${storedAccuracy}m).`);
                const locationData = {
                    coords: {
                        latitude: parseFloat(storedLat),
                        longitude: parseFloat(storedLng),
                        accuracy: storedAccuracy
                    },
                    timestamp: storedTimestamp,
                    isFromStorage: true
                };
                // Temporarily apply stored location, watch will refine it
                handleLocationSuccess(locationData);
                // Start watching for a more accurate or current location
                startWatchingLocation(false); // false: not a manual retry
                return true; // Indicated a stored location was applied
            } else {
                console.log(`LOCATION.JS: Stored location recent, but accuracy (${storedAccuracy}m) not good enough.`);
            }
        } else {
            console.log("LOCATION.JS: Stored location is too old.");
        }
    } else {
        console.log("LOCATION.JS: No complete stored location found.");
    }

    // Check for recent blocking errors (like PERMISSION_DENIED)
    const storedErrorStr = localStorage.getItem('locationError');
    if (storedErrorStr) {
        try {
            const errorData = JSON.parse(storedErrorStr);
            if (errorData.timestamp && (Date.now() - parseInt(errorData.timestamp, 10)) < RECENT_STORED_LOCATION_MAX_AGE_MS) {
                if (String(errorData.code) === '1' || String(errorData.code) === 'PERMISSION_DENIED') {
                    console.log("LOCATION.JS: Recent PERMISSION_DENIED error stored. Not attempting new request automatically.");
                    handleLocationError({ code: errorData.code, message: errorData.message }, true, true); // isFromStorage, isBlocking
                    return false; // Did not get location, and won't try now.
                }
            }
        } catch (e) { console.error("LOCATION.JS: Error parsing stored locationError:", e); localStorage.removeItem('locationError');}
    }
    
    // If no suitable stored location and no recent blocking error, start watching.
    isFirstLocationUpdateFromWatch = true; // Reset for the new watch session
    startWatchingLocation(false);
    return false; // Location request initiated (watch started), but not yet successful/available from watch.
}

function requestUserLocation(isManualRetry = false) {
    if (isManualRetry) {
        console.log("LOCATION.JS: Manual location retry requested.");
        isFirstLocationUpdateFromWatch = true; // Reset for map flyTo behavior on next success
        localStorage.removeItem('locationError'); // Clear previous error on manual retry
    }
    startWatchingLocation(isManualRetry);
}

function startWatchingLocation(isManualRetry = false) {
    if (!navigator.geolocation) {
        showToast('خدمة تحديد الموقع غير مدعومة في متصفحك.', 'danger', 0);
        handleLocationError({ code: 'NOT_SUPPORTED', message: 'Geolocation not supported' });
        return;
    }

    dismissToast('locating-toast'); // Dismiss any previous
    const toastMessage = isManualRetry
        ? '<div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2" role="status"></div>جاري إعادة محاولة تحديد موقعك...</div>'
        : '<div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2" role="status"></div>جاري تحديد موقعك الحالي...</div>';
    showToast(toastMessage, 'info', 0, 'locating-toast'); // 0 duration = indefinite until dismissed

    if (locationWatchId !== null) {
        navigator.geolocation.clearWatch(locationWatchId);
        console.log("LOCATION.JS: Cleared previous location watch.");
    }

    console.log("LOCATION.JS: Starting to watch position...");
    locationWatchId = navigator.geolocation.watchPosition(
        handleLocationSuccess, // Success callback
        (error) => handleLocationError(error, false), // Error callback (not from storage)
        LOCATION_OPTIONS
    );
}

function stopWatchingLocation() {
    if (locationWatchId !== null) {
        navigator.geolocation.clearWatch(locationWatchId);
        locationWatchId = null;
        console.log("LOCATION.JS: Stopped watching position.");
    }
}

function handleLocationSuccess(position) {
    const now = Date.now();
    // Throttle updates if they come too frequently from watchPosition with no change
    if (!position.isFromStorage && position.timestamp && position.timestamp === lastLocationUpdateTimestamp && (now - lastLocationUpdateTimestamp) < 1000) {
        return; // Ignore redundant updates
    }
    lastLocationUpdateTimestamp = position.timestamp || now;

    const newLoc = {
        lat: position.coords.latitude,
        lng: position.coords.longitude
    };
    const accuracy = position.coords.accuracy;

    // If new location is significantly less accurate than current, and user hasn't moved much, be cautious
    if (currentUserLocation && !isFirstLocationUpdateFromWatch && !position.isFromStorage &&
        accuracy > (currentUserLocation.accuracy * 1.5) && accuracy > MIN_DESIRED_ACCURACY_METERS) {
        if (map && map.distance(newLoc, currentUserLocation) < accuracy / 2) {
            console.warn(`LOCATION.JS: New location accuracy (${accuracy}m) significantly worse. Retaining previous better location for centering.`);
            updateUserMarkerAndAccuracyCircle(newLoc, accuracy, true); // Update visuals only
            return;
        }
    }
    
    currentUserLocation = { ...newLoc, accuracy: accuracy };

    console.log(`LOCATION.JS: Location ${position.isFromStorage ? 'loaded from storage' : (isFirstLocationUpdateFromWatch ? 'initial fix' : 'update')}: `, currentUserLocation);

    localStorage.setItem('userLatitude', currentUserLocation.lat.toString());
    localStorage.setItem('userLongitude', currentUserLocation.lng.toString());
    localStorage.setItem('userAccuracy', accuracy.toString());
    localStorage.setItem('locationTimestamp', now.toString());
    localStorage.removeItem('locationError');

    dismissToast('locating-toast');

    updateUserMarkerAndAccuracyCircle(currentUserLocation, accuracy);

    if (!map) {
        console.error("LOCATION.JS (handleLocationSuccess): Map object not available for UI updates.");
        return; // Cannot proceed with map-related UI updates
    }

    if (isFirstLocationUpdateFromWatch && !position.isFromStorage) {
        showToast(`تم تحديد موقعك (دقة ${accuracy.toFixed(0)} م).`, 'success', 4000);
        map.flyTo(currentUserLocation, DETAILED_ZOOM, { animate: true, duration: 1.0 });
        setTimeout(() => {
            if (userLocationMarker && map.hasLayer(userLocationMarker) && !userLocationMarker.isPopupOpen()) {
                if (accuracy < MAX_ACCEPTABLE_ACCURACY_METERS) userLocationMarker.openPopup();
            }
        }, 1100);
        isFirstLocationUpdateFromWatch = false;
    } else if (!position.isFromStorage && accuracy > MAX_ACCEPTABLE_ACCURACY_METERS) {
        showToast(`دقة الموقع منخفضة (${accuracy.toFixed(0)} م). حاول التحرك لمكان مفتوح.`, 'warning', 5000);
    }
    
    // Fetch predictions if user moved significantly or if it's the first good fix
    let shouldFetch = false;
    if (!lastFetchedPredictionsLocation) {
        shouldFetch = true;
    } else if (map) {
        const distanceMoved = map.distance(currentUserLocation, lastFetchedPredictionsLocation);
        if (distanceMoved > PREDICTION_FETCH_DISTANCE_THRESHOLD_METERS) {
            shouldFetch = true;
        }
    }

    if (shouldFetch) {
        console.log("LOCATION.JS: Fetching predictions due to movement or initial fix.");
        fetchPredictionsForLocation(currentUserLocation, position.isFromStorage || !isFirstLocationUpdateFromWatch); // Silent if from storage or not first watch update
        lastFetchedPredictionsLocation = { lat: currentUserLocation.lat, lng: currentUserLocation.lng };
    } else if (position.isFromStorage){ // Always fetch for stored location if not fetched before
         fetchPredictionsForLocation(currentUserLocation, true);
         lastFetchedPredictionsLocation = { lat: currentUserLocation.lat, lng: currentUserLocation.lng };
    }
}

function updateUserMarkerAndAccuracyCircle(location, accuracy, onlyUpdateVisuals = false) {
    if (!map) return; // Cannot update marker if map not ready

    if (userLocationMarker) {
        userLocationMarker.setLatLng(location);
        userLocationMarker.setPopupContent(`موقعك الحالي (دقة ~${accuracy.toFixed(0)} متر)`);
    } else {
        userLocationMarker = L.marker(location, { icon: icons.userLocation, zIndexOffset: 1000 })
            .addTo(map)
            .bindPopup(`موقعك الحالي (دقة ~${accuracy.toFixed(0)} متر)`);
    }

    if (accuracyCircle) {
        accuracyCircle.setLatLng(location).setRadius(accuracy);
        if (accuracy >= MAX_ACCURACY_RADIUS_METERS || accuracy <= 0) {
            if (map.hasLayer(accuracyCircle)) map.removeLayer(accuracyCircle);
        } else {
            if (!map.hasLayer(accuracyCircle)) accuracyCircle.addTo(map);
        }
    } else {
        if (accuracy > 0 && accuracy < MAX_ACCURACY_RADIUS_METERS) {
            accuracyCircle = L.circle(location, accuracy, {
                color: 'var(--primary-color)', fillColor: 'var(--primary-color)',
                fillOpacity: 0.15, weight: 2, interactive: false
            }).addTo(map);
        }
    }

    // If only updating visuals, we don't fly or change primary 'currentUserLocation'
    // That logic is in handleLocationSuccess
}

function handleLocationError(error, isFromStorage = false, isBlockingError = false) {
    const errorCode = String(error.code || (error.message && error.message.includes('User denied') ? 'PERMISSION_DENIED' : 'UNKNOWN'));
    console.error(`LOCATION.JS: Geolocation Error (isFromStorage: ${isFromStorage}, isBlocking: ${isBlockingError}). Code: ${errorCode}, Message: ${error.message}`);
    
    dismissToast('locating-toast');
    let displayMessage = "حدث خطأ غير معروف أثناء محاولة تحديد موقعك.";

    if (!isFromStorage || (isFromStorage && !isBlockingError)) {
        switch (errorCode) {
            case '1': case 'PERMISSION_DENIED':
                displayMessage = "تم رفض إذن الوصول للموقع. يرجى تمكينها من إعدادات المتصفح/الجهاز.";
                if (!isFromStorage && locationErrorModalInstance) locationErrorModalInstance.show();
                else if (!isFromStorage) showToast(displayMessage, 'danger', 0); // Persistent toast
                stopWatchingLocation(); // Critical: stop trying if permission denied
                break;
            case '2': case 'POSITION_UNAVAILABLE':
                displayMessage = "معلومات الموقع غير متوفرة حاليًا. تأكد من تفعيل GPS ووجود إشارة جيدة.";
                if (!isFromStorage) showToast(displayMessage, 'warning', 7000);
                // Keep watching, it might become available
                break;
            case '3': case 'TIMEOUT':
                displayMessage = "انتهت مهلة طلب الموقع. الشبكة ضعيفة أو GPS يستغرق وقتًا أطول.";
                if (!isFromStorage) showToast(displayMessage, 'warning', 7000);
                // Keep watching
                break;
            case 'NOT_SUPPORTED':
                displayMessage = "خدمة تحديد الموقع غير مدعومة في متصفحك.";
                if (!isFromStorage) showToast(displayMessage, 'danger', 0);
                stopWatchingLocation();
                break;
            default:
                if (!isFromStorage) showToast(displayMessage + ` (رمز: ${errorCode})`, 'danger', 7000);
        }
    }

    if (!isFromStorage && error.code) { // Only store new errors from API
        localStorage.setItem('locationError', JSON.stringify({
            code: error.code, message: error.message, timestamp: Date.now().toString()
        }));
        // Do NOT clear currentUserLocation here if watchPosition is active and error is transient.
        // Let watchPosition try again. Only clear if error is fatal (PERMISSION_DENIED, NOT_SUPPORTED)
    }

    if (errorCode === '1' || errorCode === 'PERMISSION_DENIED' || errorCode === 'NOT_SUPPORTED') {
        currentUserLocation = null; // Definitely no location possible
        lastFetchedPredictionsLocation = null;
        if (userLocationMarker && map && map.hasLayer(userLocationMarker)) map.removeLayer(userLocationMarker);
        if (accuracyCircle && map && map.hasLayer(accuracyCircle)) map.removeLayer(accuracyCircle);
        userLocationMarker = null;
        accuracyCircle = null;
    }
    updateOpenPopupWithPrediction();
}

function fetchPredictionsForLocation(location, silently = false) {
    if (!location || !location.lat || !location.lng) {
        console.warn("LOCATION.JS (fetchPredictionsForLocation): Invalid or unknown location.", location);
        if (window.latestPredictionData !== null) {
            window.latestPredictionData = null;
            updateOpenPopupWithPrediction();
        }
        return;
    }
    if (!silently) {
        // showToast('جاري تحديث التوقعات...', 'info', 2000, 'prediction-toast');
    }
    console.log("LOCATION.JS: Fetching predictions for:", location);

    // Ensure API_URL_GET_PREDICTIONS and CSRF_TOKEN are globally available
    fetch(API_URL_GET_PREDICTIONS, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        body: JSON.stringify({ latitude: location.lat, longitude: location.lng })
    })
    .then(response => {
        dismissToast('prediction-toast');
        if (!response.ok) {
            return response.json().then(errData => {
                 throw new Error(errData.error || `خطأ بالخادم: ${response.status}`);
            }).catch(() => { throw new Error(`خطأ بالخادم: ${response.status}`); });
        }
        return response.json();
    })
    .then(data => {
        if (data.error) throw new Error(data.error);
        window.latestPredictionData = data.fences || [];
        console.log("LOCATION.JS: Predictions received (count: " + window.latestPredictionData.length + ")");
        updateOpenPopupWithPrediction();
        // if (!silently && data.fences && data.fences.length > 0) {
        //     showToast('تم تحديث توقعات نقاط التفتيش.', 'success', 2500);
        // }
    })
    .catch(error => {
        dismissToast('prediction-toast');
        console.error('LOCATION.JS: Prediction fetch error:', error);
        if (!silently) showToast(`خطأ في جلب التوقعات: ${error.message}`, 'danger', 5000);
        if (window.latestPredictionData !== null) {
            window.latestPredictionData = null;
            updateOpenPopupWithPrediction();
        }
    });
}

function updateOpenPopupWithPrediction() {
    if (!map) return;
    const isDataArray = Array.isArray(window.latestPredictionData);

    map.eachLayer(function (layer) {
        if (layer instanceof L.Marker && layer.isPopupOpen() && layer.options.fenceData) {
            const fenceId = layer.options.fenceData.id;
            const popupEl = layer.getPopup().getElement();
            if (!popupEl) return;
            const placeholder = popupEl.querySelector(`.prediction-placeholder[data-fence-id="${fenceId}"]`);
            if (!placeholder) return;

            let prediction = null;
            if (isDataArray) {
                prediction = window.latestPredictionData.find(p => String(p.id) === String(fenceId));
            }
            updateOpenPopupWithSpecificPrediction(placeholder, prediction);
        }
    });
}

function updateOpenPopupWithSpecificPrediction(placeholderElement, predictionData) {
    if (!placeholderElement) return;
    let html = '';
    if (predictionData) {
        if (predictionData.prediction_success && typeof predictionData.predicted_wait_minutes === 'number') {
            const waitTime = Math.round(predictionData.predicted_wait_minutes);
            const formattedWait = formatWaitTime(waitTime);
            let combinedTimeHTML = '';
            if (currentUserLocation && typeof predictionData.distance_km === 'number' && predictionData.distance_km >= 0) {
                const travelTime = calculateTravelTime(predictionData.distance_km);
                const totalTime = waitTime + travelTime;
                const formattedTotal = formatWaitTime(totalTime);
                const arrival = new Date(Date.now() + totalTime * 60000);
                let hrs = arrival.getHours();
                const mins = arrival.getMinutes();
                const ampm = hrs >= 12 ? 'مساءً' : 'صباحًا';
                hrs = hrs % 12; hrs = hrs ? hrs : 12;
                const formattedArrival = `${hrs}:${mins < 10 ? '0'+mins : mins} ${ampm}`;
                combinedTimeHTML = `
                    <hr class="prediction-separator">
                    <div class="popup-item prediction-info">
                        <span class="popup-icon"><i class="fas fa-hourglass-half"></i></span>
                        <span>الوقت الإجمالي المتوقع: <strong>${formattedTotal}</strong></span>
                    </div>
                    <div class="popup-item arrival-time-info">
                        <span class="popup-icon"><i class="fas fa-clock"></i></span>
                        <span>وقت الوصول التقديري: <strong>${formattedArrival}</strong></span>
                    </div>`;
            } else {
                combinedTimeHTML = `
                    <hr class="prediction-separator">
                    <div class="popup-item prediction-info">
                        <span class="popup-icon"><i class="fas fa-hourglass-half"></i></span>
                        <span>وقت الانتظار المتوقع: <strong>${formattedWait}</strong></span>
                    </div>`;
            }
            html = combinedTimeHTML;
            if (predictionData.prediction_debug_info) {
                html += `<div class="popup-item text-muted small" style="font-size:0.75em; text-align:right; color: #888; margin-top:3px;">${predictionData.prediction_debug_info}</div>`;
            }
        } else if (predictionData.prediction_error) {
            html = `<hr class="prediction-separator"><div class="popup-item prediction-error"><span class="popup-icon"><i class="fas fa-exclamation-circle"></i></span><span>التوقع: ${predictionData.prediction_error}</span></div>`;
        } else {
            html = `<hr class="prediction-separator"><div class="popup-item text-muted"><span class="popup-icon"><i class="fas fa-info-circle"></i></span><span>لا توجد توقعات تفصيلية لهذه النقطة حالياً.</span></div>`;
        }
    } else {
        if (currentUserLocation) {
            html = `<hr class="prediction-separator"><div class="popup-item text-muted"><span class="popup-icon"><i class="fas fa-sync fa-spin"></i></span><span>جاري البحث عن توقعات لهذه النقطة...</span></div>`;
        } else {
            html = `<hr class="prediction-separator"><div class="popup-item text-muted"><span class="popup-icon"><i class="fas fa-map-marker-alt"></i></span><span>حدد موقعك للحصول على التوقعات.</span></div>`;
        }
    }
    placeholderElement.innerHTML = html;
}