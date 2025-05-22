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
    if (planRouteBtn) {
        planRouteBtn.addEventListener('click', () => {
            const destinationInput = document.getElementById('destination-input');
            if (destinationInput) {
                const destination = destinationInput.value.trim();
                if (destination) {
                    findShortestWaitInCity(destination, routeModalInstance);
                } else {
                    showToast('يرجى إدخال وجهة.', 'warning');
                }
            }
        });
    }
}

function findShortestWaitInCity(cityName, modalInstance) {
    showToast(`<div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2" role="status"></div>جاري البحث في ${cityName}...</div>`, 'info', 5000);

    fetch(API_URL_SHORTEST_WAIT_BY_CITY, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json', 
            'X-CSRFToken': CSRF_TOKEN 
        },
        body: JSON.stringify({ city_name: cityName })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { 
                throw new Error(err.error || 'خطأ في الخادم'); 
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            if (modalInstance) modalInstance.hide();
            
            // عرض النتيجة للمستخدم
            showToast(
                `أقصر وقت انتظار في ${data.city}: ${data.formatted_wait_time} (${data.fence_name}) - وقت الوصول المتوقع: ${data.formatted_arrival_time}`,
                'success',
                7000
            );

            // البحث عن الحاجز على الخريطة وفتح popup له
            const fence = window.allFences.find(f => f.id === data.fence_id);
            if (fence) {
                map.flyTo([fence.latitude, fence.longitude], DETAILED_ZOOM);
                
                // فتح popup للحاجز المحدد
                const marker = findMarkerByFenceId(data.fence_id);
                if (marker) {
                    marker.openPopup();
                }
            }
        } else {
            showToast(data.error || 'لم يتم العثور على نتائج', 'warning');
        }
    })
    .catch(error => {
        console.error('Error finding shortest wait:', error);
        showToast(`خطأ في البحث: ${error.message}`, 'danger');
    });
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

// تأكد من تعريف window.allFences عند تحميل البيانات
// يمكنك إضافته في ملف data_handler.js أو main_map.js عند تحميل البيانات