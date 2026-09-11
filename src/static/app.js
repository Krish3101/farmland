let leafletMap = null;
let farmLayer = null;

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

        if (!feature) {
            showError(`No farm record found for identifier: ${farmId}`);
            return;
        }

        resultsSection.classList.remove('hidden');

        rawJson.textContent = JSON.stringify(featureCollection, null, 2);

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
        showError(`Error: ${err.message}`);
    } finally {
        fetchBtn.disabled = false;
        fetchBtn.textContent = 'Fetch Farm Data';
    }
}

fetchBtn.addEventListener('click', handleFetch);

phoneInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleFetch();
});

apiKeyInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleFetch();
});
