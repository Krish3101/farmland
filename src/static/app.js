// Global Leaflet map state
let leafletMap = null;
let farmLayer = null;

// DOM elements
const phoneInput = document.getElementById('phoneInput');
const apiKeyInput = document.getElementById('apiKeyInput');
const fetchBtn = document.getElementById('fetchBtn');
const errorAlert = document.getElementById('errorAlert');
const resultsSection = document.getElementById('resultsSection');
const rawJson = document.getElementById('rawJson');

function showError(message) {
    errorAlert.textContent = message;
    errorAlert.classList.remove('hidden');
    resultsSection.classList.add('hidden');
}

function clearError() {
    errorAlert.textContent = '';
    errorAlert.classList.add('hidden');
}

function initMap() {
    if (leafletMap) return;
    leafletMap = L.map('map').setView([20.5937, 78.9629], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
    }).addTo(leafletMap);
}

async function handleFetch() {
    const farmId = phoneInput.value.trim();
    const apiKey = apiKeyInput.value.trim();

    // FR-21: An empty identifier is rejected before any request is made
    if (!farmId) {
        showError('Please enter a farm identifier.');
        phoneInput.focus();
        return;
    }

    clearError();
    fetchBtn.disabled = true;
    fetchBtn.textContent = 'Fetching…';
    resultsSection.classList.add('hidden');

    try {
        // FR-21: Server-side filtered lookup
        const headers = {};
        if (apiKey) {
            headers['X-API-Key'] = apiKey;
        }

        const response = await fetch(`/api/farms/geojson?farm_id=${encodeURIComponent(farmId)}`, {
            headers: headers
        });

        if (!response.ok) {
            let errorDetail = `Server returned status ${response.status}`;
            try {
                const body = await response.json();
                if (body && body.detail) {
                    errorDetail = body.detail;
                }
            } catch (_) {}
            throw new Error(errorDetail);
        }

        const featureCollection = await response.json();
        const feature = featureCollection.features && featureCollection.features[0];

        // FR-24: "No record found" shown as visible error state
        if (!feature) {
            showError(`No farm record found for identifier: ${farmId}`);
            return;
        }

        // Display results
        resultsSection.classList.remove('hidden');

        // FR-23: Display raw response alongside map
        rawJson.textContent = JSON.stringify(featureCollection, null, 2);

        // FR-22: Render boundary on map and fit to extent
        initMap();
        if (farmLayer) {
            leafletMap.removeLayer(farmLayer);
            farmLayer = null;
        }

        if (feature.geometry) {
            farmLayer = L.geoJSON(feature, {
                style: {
                    color: '#4f8ef7',
                    weight: 2,
                    fillColor: '#4f8ef7',
                    fillOpacity: 0.25
                }
            }).addTo(leafletMap);

            const bounds = farmLayer.getBounds();
            if (bounds.isValid()) {
                leafletMap.fitBounds(bounds, { padding: [30, 30] });
            }
        }

    } catch (err) {
        // FR-24: Surface authorization, server, and network errors visibly
        showError(`Error: ${err.message}`);
    } finally {
        // FR-24: Controls are re-enabled after every attempt
        fetchBtn.disabled = false;
        fetchBtn.textContent = 'Fetch Farm Data';
    }
}

// Event Listeners
fetchBtn.addEventListener('click', handleFetch);

phoneInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleFetch();
});

apiKeyInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleFetch();
});
