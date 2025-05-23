// static/js/search.js

const mainSearchInput = document.getElementById('search-input');
const mainSearchResultsContainer = document.querySelector('.search-results');
const searchButton = document.getElementById('search-btn');
let allFencesNames = [];

function loadAllFencesNames() {
    fetch(`${API_URL_SEARCH_CITY_OR_FENCE}?q=`)
        .then(response => response.json())
        .then(data => {
            if (Array.isArray(data)) {
                allFencesNames = data.map(fence => fence.name).filter(name => name);
            }
        })
        .catch(error => {
            console.error('SEARCH.JS: Error loading fences names:', error);
        });
}

// استدعاء الدالة عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', loadAllFencesNames);

function setupSearchEventListeners() {
    if (mainSearchInput && mainSearchResultsContainer && searchButton) {
        // تم إزالة الدالة debounce هنا لجعل البحث فوريًا
        mainSearchInput.addEventListener('input', performMainSearch);

        mainSearchInput.addEventListener('focus', () => {
            if (mainSearchInput.value.trim().length >= 1 && mainSearchResultsContainer.children.length > 0) {
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

    // البحث المحلي الفوري
    if (allFencesNames.length > 0 && searchTerm.length >= 1) {
        const localResults = allFencesNames.filter(name => 
            name.toLowerCase().includes(searchTerm.toLowerCase()) || 
            name.toLowerCase().startsWith(searchTerm.toLowerCase())
        ).slice(0, 1);

        if (localResults.length > 0) {
            renderLocalSearchResults(localResults, searchTerm);
            return; // إظهار النتائج المحلية فقط دون انتظار الخادم
        }
    }

    // إذا لم تكن هناك نتائج محلية، نبحث في الخادم
    mainSearchResultsContainer.style.display = 'block';

    fetch(`${API_URL_SEARCH_CITY_OR_FENCE}?q=${encodeURIComponent(searchTerm)}`)
        .then(response => {
            if (!response.ok) throw new Error('Network error');
            return response.json();
        })
        .then(apiResults => {
            renderMainSearchResults(apiResults, searchTerm);
        })
        .catch(error => {
            console.error('SEARCH.JS: Error fetching search results:', error);
            clearMainSearchResults();
        });
}

// باقي الدوال تبقى كما هي بدون تغيير
function renderLocalSearchResults(results, searchTerm) {
    clearMainSearchResults();
    
    results.forEach(name => {
        const item = document.createElement('div');
        item.className = 'search-result-item local-result';
        item.innerHTML = `
            <span class="result-name">${highlightMatch(name, searchTerm)}</span>
            <span class="local-badge">محلي</span>`;
        
        item.addEventListener('click', () => {
            mainSearchInput.value = name;
            performMainSearch();
        });
        
        mainSearchResultsContainer.appendChild(item);
    });
    
    mainSearchResultsContainer.style.display = 'block';
}

function highlightMatch(text, match) {
    if (!match) return text;
    const regex = new RegExp(`(${match})`, 'gi');
    return text.replace(regex, '<span class="highlight-match">$1</span>');
}

function renderMainSearchResults(results, searchTerm) {
    clearMainSearchResults();

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
            });
            mainSearchResultsContainer.appendChild(item);
        });
    }
    mainSearchResultsContainer.style.display = 'block';
}

function clearMainSearchResults() {
    if (mainSearchResultsContainer) {
        mainSearchResultsContainer.innerHTML = '';
    }
}