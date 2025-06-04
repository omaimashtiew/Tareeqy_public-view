// static/js/route_planner.js

function setupRoutePlannerEventListeners() {
    console.log("ROUTE_PLANNER.JS: setupRoutePlannerEventListeners called");
    
    const goButton = document.getElementById('footer-go-btn');
    const routeModalElement = document.getElementById('route-modal');
    let routeModalInstance = null;
    if (routeModalElement) {
        routeModalInstance = bootstrap.Modal.getOrCreateInstance(routeModalElement);
    }

    if (goButton && routeModalInstance) {
        goButton.addEventListener('click', () => {
            console.log("Route planner button clicked, showing modal.");
            routeModalInstance.show();
        });
    }

    const planRouteBtn = document.getElementById('plan-route-btn');
    const destinationInput = document.getElementById('destination-input');
    
    // إضافة event listener لزر Enter
    if (destinationInput) {
        destinationInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleRoutePlanning(destinationInput, routeModalInstance);
            }
        });
    }

    if (planRouteBtn) {
        planRouteBtn.addEventListener('click', () => {
            handleRoutePlanning(destinationInput, routeModalInstance);
        });
    }
}

function handleRoutePlanning(destinationInput, modalInstance) {
    const destination = destinationInput.value.trim();
    if (destination) {
        if (!currentUserLocation) {
            showToast('يجب تحديد موقعك أولاً', 'warning');
            requestUserLocation(true); // طلب تحديث الموقع
            return;
        }
        findShortestWaitInCity(destination, modalInstance);
    } else {
        showToast('يرجى إدخال وجهة.', 'warning');
    }
}

async function findShortestWaitInCity(cityName, modalInstance) {
    const toastId = 'route-planning-toast';
    showToast(
        `<div class="d-flex align-items-center">
            <div class="spinner-border spinner-border-sm me-2" role="status"></div>
            جاري البحث في ${cityName}...
        </div>`, 
        'info', 
        0, // 0 يعني لا يختفي تلقائياً
        toastId
    );

    try {
        const response = await fetch(API_URL_SHORTEST_WAIT_BY_CITY, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json', 
                'X-CSRFToken': CSRF_TOKEN 
            },
            body: JSON.stringify({
                city_name: cityName,
                latitude: currentUserLocation.lat,
                longitude: currentUserLocation.lng
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'خطأ في الخادم');
        }

        const data = await response.json();
        dismissToast(toastId);

        if (data.success) {
            if (modalInstance) modalInstance.hide();
            
            // عرض النتيجة للمستخدم
            showToast(
                `أقصر وقت انتظار في ${data.city}: ${data.formatted_wait_time} (${data.fence_name}) - وقت الوصول المتوقع: ${data.formatted_arrival_time}`,
                'success',
                7000
            );

            // عرض المسار على الخريطة
            await displayRouteToFence(data.fence_id);
        } else {
            showToast(data.error || 'لم يتم العثور على نتائج', 'warning', 4000);
        }
    } catch (error) {
        console.error('Error finding shortest wait:', error);
        dismissToast(toastId);
        showToast(`خطأ في البحث: ${error.message}`, 'danger', 5000);
    }
}

async function displayRouteToFence(fenceId) {
    const fence = window.allFences.find(f => f.id === fenceId);
    if (!fence || !map) return;

    try {
        // الحصول على المسار من OSRM
        const response = await fetch(
            `https://router.project-osrm.org/route/v1/driving/` +
            `${currentUserLocation.lng},${currentUserLocation.lat};` +
            `${fence.longitude},${fence.latitude}?overview=full&geometries=geojson`
        );
        
        const routeData = await response.json();
        
        if (routeData.code === 'Ok') {
            // إزالة أي مسار قديم
            if (window.currentRouteLayer) {
                map.removeLayer(window.currentRouteLayer);
            }
            
            // عرض المسار الجديد
            const routeGeoJSON = {
                type: 'Feature',
                properties: {},
                geometry: routeData.routes[0].geometry
            };
            
            window.currentRouteLayer = L.geoJSON(routeGeoJSON, {
                style: {
                    color: '#4285F4',
                    weight: 5,
                    opacity: 0.8
                }
            }).addTo(map);
            
            // تكبير الخريطة لتظهر المسار كاملاً
            map.fitBounds(window.currentRouteLayer.getBounds(), { padding: [50, 50] });
            
            // فتح popup للحاجز المحدد
            const marker = findMarkerByFenceId(fenceId);
            if (marker) {
                marker.openPopup();
            }
        }
    } catch (error) {
        console.error('Error displaying route:', error);
        // Fallback: فقط اذهب إلى الموقع بدون عرض المسار
        map.flyTo([fence.latitude, fence.longitude], DETAILED_ZOOM);
        const marker = findMarkerByFenceId(fenceId);
        if (marker) marker.openPopup();
    }
}

function findMarkerByFenceId(fenceId) {
    let foundMarker = null;
    map.eachLayer(layer => {
        if (layer instanceof L.Marker && layer.options.fenceData && layer.options.fenceData.id === fenceId) {
            foundMarker = layer;
        }
    });
    return foundMarker;
}