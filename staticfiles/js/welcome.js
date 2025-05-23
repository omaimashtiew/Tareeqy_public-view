// static/js/welcome.js
document.addEventListener('DOMContentLoaded', function() {
    const startBtn = document.getElementById('start-btn');

    if (!startBtn) {
        console.error("WELCOME.JS: Start button (#start-btn) not found!");
        return;
    }

    // Check if MAP_PAGE_URL was correctly passed from the template
    if (typeof MAP_PAGE_URL === 'undefined' || !MAP_PAGE_URL) {
        console.error("WELCOME.JS: MAP_PAGE_URL is not defined or empty! Check welcome.html template.");
        // Provide a fallback or show an error to the user
        startBtn.textContent = "خطأ في الإعداد";
        startBtn.disabled = true;
        return;
    }
    console.log("WELCOME.JS: MAP_PAGE_URL is:", MAP_PAGE_URL);


    startBtn.addEventListener('click', function() {
        startBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> جاري التحميل...';
        startBtn.disabled = true;
        
        localStorage.removeItem('userLatitude');
        localStorage.removeItem('userLongitude');
        localStorage.removeItem('userAccuracy');
        localStorage.removeItem('locationTimestamp');
        localStorage.removeItem('locationError');

        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    console.log("WELCOME.JS: Location permission granted.");
                    localStorage.setItem('userLatitude', position.coords.latitude.toString());
                    localStorage.setItem('userLongitude', position.coords.longitude.toString());
                    localStorage.setItem('userAccuracy', position.coords.accuracy.toString());
                    localStorage.setItem('locationTimestamp', new Date().getTime().toString());
                    
                    console.log("WELCOME.JS: Navigating to map page:", MAP_PAGE_URL);
                    window.location.href = MAP_PAGE_URL; 
                },
                function(error) {
                    console.error("WELCOME.JS: Location error:", error.code, error.message);
                    localStorage.setItem('locationError', JSON.stringify({
                        code: error.code,
                        message: error.message,
                        timestamp: new Date().getTime().toString()
                    }));
                    console.log("WELCOME.JS: Navigating to map page (despite location error):", MAP_PAGE_URL);
                    window.location.href = MAP_PAGE_URL; 
                },
                {
                    enableHighAccuracy: true,
                    timeout: 15000, 
                    maximumAge: 0 
                }
            );
        } else {
            console.error("WELCOME.JS: Geolocation is not supported.");
            localStorage.setItem('locationError', JSON.stringify({
                code: 'GEOLOCATION_NOT_SUPPORTED',
                message: 'خدمة تحديد الموقع غير مدعومة في متصفحك.',
                timestamp: new Date().getTime().toString()
            }));
            console.log("WELCOME.JS: Navigating to map page (geolocation not supported):", MAP_PAGE_URL);
            window.location.href = MAP_PAGE_URL; 
        }
    });
}); 