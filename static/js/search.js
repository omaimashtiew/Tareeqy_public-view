// static/js/search.js

const mainSearchInput = document.getElementById('search-input');
const mainSearchResultsContainer = document.querySelector('.search-results');
const searchButton = document.getElementById('search-btn');

function debounce(func, delay) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), delay);
    };
}

function setupSearchEventListeners() {
    if (mainSearchInput && mainSearchResultsContainer && searchButton) {
        mainSearchInput.addEventListener('input', debounce(performMainSearch, 300)); // Reduced debounce slightly

        mainSearchInput.addEventListener('focus', () => {
            if (mainSearchInput.value.trim().length >= 1 && mainSearchResultsContainer.children.length > 0) { // Min 1 char to show existing
                mainSearchResultsContainer.style.display = 'block';
            }
        });

        searchButton.addEventListener('click', () => {
             mainSearchInput.focus();
             performMainSearch(); 
        });

        mainSearchInput.addEventListener('keyup', (event) => {
            if (event.key === "Escape") {
                mainSearchResultsContainer.style.display = 'none';
            } else if (mainSearchInput.value.trim() === "") {
                clearMainSearchResults();
                processAndDisplayFences(); 
            }
        });

    } else {
        if (!mainSearchInput) console.error("SEARCH.JS: Main search input not found.");
        if (!mainSearchResultsContainer) console.error("SEARCH.JS: Main search results container not found.");
        if (!searchButton) console.error("SEARCH.JS: Main search button not found.");
    }

    document.addEventListener('click', function(event) {
        if (mainSearchInput && mainSearchResultsContainer && searchButton) {
            const isClickInsideSearch = mainSearchInput.contains(event.target) ||
                                       mainSearchResultsContainer.contains(event.target) ||
                                       searchButton.contains(event.target);
            if (!isClickInsideSearch) {
                mainSearchResultsContainer.style.display = 'none';
            }
        }
    });
}

function performMainSearch() {
    const searchTerm = mainSearchInput.value.trim();

    if (searchTerm.length === 0) {
        clearMainSearchResults();
        processAndDisplayFences();
        return;
    }

    // Changed minimum length to 1 for suggestions
    if (searchTerm.length < 1) { 
        mainSearchResultsContainer.style.display = 'none';
        return;
    }
    
    // Show a subtle loading indicator in the dropdown
    mainSearchResultsContainer.innerHTML = `<div class="search-loading p-2 text-center text-muted"><i class="fas fa-spinner fa-spin me-2"></i>جاري البحث...</div>`;
    mainSearchResultsContainer.style.display = 'block';


    fetch(`${API_URL_SEARCH_CITY_OR_FENCE}?q=${encodeURIComponent(searchTerm)}`)
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.message || err.error || `Network error: ${response.status}`);
                }).catch(() => {
                    throw new Error(`Network error: ${response.status} (Could not parse error JSON)`);
                });
            }
            return response.json();
        })
        .then(apiResults => {
            renderMainSearchResults(apiResults, searchTerm);
        })
        .catch(error => {
            console.error('SEARCH.JS: Error fetching main search results:', error);
            clearMainSearchResults(); // Clear loading indicator
            mainSearchResultsContainer.innerHTML = `<div class="no-results p-2 text-center text-danger">فشل البحث: ${error.message}</div>`;
            mainSearchResultsContainer.style.display = 'block';
        });
}

function renderMainSearchResults(results, searchTerm) {
    clearMainSearchResults(); // Clear previous results or loading indicator

    if (!results) {
        mainSearchResultsContainer.innerHTML = `<div class="no-results p-2 text-center text-muted">لا توجد نتائج لـ "${searchTerm}".</div>`;
        mainSearchResultsContainer.style.display = 'block';
        return;
    }
    
    if (results.message && results.length === undefined) {
        mainSearchResultsContainer.innerHTML = `<div class="no-results p-2 text-center text-warning">${results.message}</div>`;
        mainSearchResultsContainer.style.display = 'block';
        return;
    }

    if (results.length === 0) {
        mainSearchResultsContainer.innerHTML = `<div class="no-results p-2 text-center text-muted">لا توجد نتائج لـ "${searchTerm}".</div>`;
    } else {
        results.forEach(result => {
            const item = document.createElement('div');
            item.className = 'search-result-item';
            const status = result.status || 'unknown';
            const details = statusDetails[status] || statusDetails.unknown;
            const name = result.name || 'اسم غير معروف';
            const city = result.city || 'مدينة غير محددة';

            const displayName = `${name} <small class="text-muted">(${city})</small>`;
            
            item.innerHTML = `
                <span class="status-dot" style="background-color: ${details.color};"></span>
                <span class="result-name">${displayName}</span>`;

            item.addEventListener('click', () => {
                if (!result.latitude || !result.longitude) {
                    console.warn("SEARCH.JS: Clicked search result has no coordinates:", result);
                    return;
                }
                map.flyTo([result.latitude, result.longitude], DETAILED_ZOOM + 1, { duration: 0.8 });
                
                const markerToOpen = checkpointMarkers[result.id];
                if (markerToOpen) {
                    const fenceDataForMarker = markerToOpen.options.fenceData;
                    if (fenceDataForMarker) {
                        const markerStatus = fenceDataForMarker.status || 'unknown';
                        if (!activeStatusFilters.includes(markerStatus)) {
                            const layerGroup = markerLayers[markerStatus] || markerLayers.unknown;
                            if(layerGroup && !map.hasLayer(layerGroup)) map.addLayer(layerGroup);
                            if(!map.hasLayer(markerToOpen)) markerToOpen.addTo(layerGroup || map);
                        }
                    }
                    
                    if(map.hasLayer(markerToOpen)){
                        markerToOpen.openPopup();
                        const markerEl = markerToOpen.getElement();
                        if (markerEl) {
                            markerEl.classList.add('checkpoint-marker-highlight');
                            setTimeout(() => markerEl.classList.remove('checkpoint-marker-highlight'), 2500);
                        }
                    } else {
                        console.warn("SEARCH.JS: Marker not on map for:", result.name);
                    }
                } else {
                    console.warn("SEARCH.JS: Marker not found for ID:", result.id, "Name:", result.name);
                }
                
                clearMainSearchResults();
                mainSearchResultsContainer.style.display = 'none';
                // mainSearchInput.value = ''; // Optionally clear the search input text
            });
            mainSearchResultsContainer.appendChild(item);
        });
    }
    mainSearchResultsContainer.style.display = 'block';
}

function clearMainSearchResults() {
    if (mainSearchResultsContainer) {
        mainSearchResultsContainer.innerHTML = '';
        // mainSearchResultsContainer.style.display = 'none'; // Display is handled by caller
    }
}