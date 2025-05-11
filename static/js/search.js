// static/js/search.js
// Handles main search bar (checkpoint name or city) and status/city filters in sidebar.

const mainSearchInput = document.getElementById('search-input');
const mainSearchResultsContainer = document.querySelector('.search-results');
// const cityFilterInputElement = document.getElementById('city-filter-input'); // Removed, main search handles city

function setupSearchEventListeners() {
    if (mainSearchInput) {
        mainSearchInput.addEventListener('input', debounce(handleMainSearchInput, 300));
        mainSearchInput.addEventListener('focus', () => {
            if (mainSearchInput.value.trim().length > 0) {
                handleMainSearchInput(); // Trigger search on focus if there's text
            }
        });
        document.getElementById('search-btn').addEventListener('click', () => {
             mainSearchInput.focus(); // Focus input
             handleMainSearchInput(); // And trigger search immediately
        });
    }

    // Global click listener to hide search results when clicking outside
    document.addEventListener('click', function(event) {
        const isClickInsideSearch = mainSearchInput.contains(event.target) ||
                                   mainSearchResultsContainer.contains(event.target) ||
                                   document.getElementById('search-btn').contains(event.target);
        if (!isClickInsideSearch) {
            mainSearchResultsContainer.style.display = 'none';
        }
    });
}

function handleMainSearchInput() {
    const searchTerm = mainSearchInput.value.trim();
    if (searchTerm.length < 2 && searchTerm.length !== 0) { // Allow clearing, but search only if >= 2 chars
        clearMainSearchResults();
        mainSearchResultsContainer.style.display = 'none';
        // If term is empty, reset map to show all (or apply current status filters)
        if (searchTerm.length === 0) {
            processAndDisplayFences(); // This will apply current status filters to all fences
        }
        return;
    }
    if (searchTerm.length === 0) { // Explicitly handle empty input to show all
         clearMainSearchResults();
         mainSearchResultsContainer.style.display = 'none';
         processAndDisplayFences(); // Show all fences according to status filters
         return;
    }


    // Make AJAX call to the backend for combined search (fence name or city)
    showToast(`البحث عن "${searchTerm}"...`, 'info', 2000); // Short-lived toast
    fetch(`${API_URL_SEARCH_CITY_OR_FENCE}?q=${encodeURIComponent(searchTerm)}`)
        .then(response => {
            if (!response.ok) {
                // Try to parse error from backend if JSON
                return response.json().then(err => { 
                    throw new Error(err.message || err.error || `خطأ بالشبكة: ${response.status}`);
                }).catch(() => {
                    throw new Error(`خطأ بالشبكة: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(apiResults => {
            renderMainSearchResults(apiResults, searchTerm);
        })
        .catch(error => {
            console.error('Error fetching main search results:', error);
            showToast(`فشل البحث: ${error.message}`, 'danger');
            clearMainSearchResults();
            mainSearchResultsContainer.innerHTML = `<div class="no-results p-2 text-center text-danger">فشل البحث. حاول مرة أخرى.</div>`;
            mainSearchResultsContainer.style.display = 'block';
        });
}

function renderMainSearchResults(results, searchTerm) {
    clearMainSearchResults();

    if (!results || results.length === 0) {
        mainSearchResultsContainer.innerHTML = `<div class="no-results p-2 text-center text-muted">لا توجد نتائج لـ "${searchTerm}".</div>`;
    } else {
        results.forEach(result => {
            const item = document.createElement('div');
            item.className = 'search-result-item';
            const status = result.status || 'unknown';
            const details = statusDetails[status] || statusDetails.unknown;

            item.innerHTML = `
                <span class="status-dot" style="background-color: ${details.color};"></span>
                <span class="result-name">${result.name} <small class="text-muted">(${result.city || 'مدينة غير محددة'})</small></span>`;

            item.addEventListener('click', () => {
                map.flyTo([result.latitude, result.longitude], DETAILED_ZOOM + 2, { duration: 0.8 });
                
                const markerToOpen = checkpointMarkers[result.id];
                if (markerToOpen) {
                    // Ensure the layer containing the marker is visible
                    const fenceData = markerToOpen.options.fenceData;
                    if (fenceData) {
                        const layerGroup = markerLayers[fenceData.status || 'unknown'];
                        if (layerGroup && !map.hasLayer(layerGroup)) {
                            map.addLayer(layerGroup); // Make sure its layer group is on map
                        }
                    } 
                    // Check again if marker is on map before opening popup
                    if(map.hasLayer(markerToOpen)){
                        markerToOpen.openPopup();
                        const markerEl = markerToOpen.getElement();
                        if (markerEl) {
                            markerEl.classList.add('checkpoint-marker-highlight');
                            setTimeout(() => markerEl.classList.remove('checkpoint-marker-highlight'), 2500);
                        }
                    } else {
                        console.warn("Marker not on map, cannot open popup for:", result.name);
                        showToast("قد تكون النقطة مخفية بسبب المرشحات الحالية.", "warning");
                    }
                } else {
                    console.warn("Marker not found in checkpointMarkers for ID:", result.id);
                }
                
                mainSearchInput.value = result.name; // Keep name in search bar
                mainSearchResultsContainer.style.display = 'none'; // Hide results after click
            });
            mainSearchResultsContainer.appendChild(item);
        });
    }
    mainSearchResultsContainer.style.display = 'block';
}

function clearMainSearchResults() {
    mainSearchResultsContainer.innerHTML = '';
    // Visibility is handled by the calling function or blur/focus events
}


// Debounce utility (can be moved to a global utils.js if used elsewhere)
function debounce(func, delay) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), delay);
    };
}