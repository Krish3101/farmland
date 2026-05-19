// Global state
let leafletMap = null;
let farmLayer = null;

// ─── DOM refs ────────────────────────────────────────────────────────────────
const phoneInput     = document.getElementById('phoneInput');
const fetchBtn       = document.getElementById('fetchBtn');
const resultsSection = document.getElementById('resultsSection');
const telemetryList  = document.getElementById('telemetryList');
const noFixes        = document.getElementById('noFixes');
const rawJson        = document.getElementById('rawJson');
const statusBadge    = document.getElementById('statusBadge');

// ─── Leaflet map (singleton) ─────────────────────────────────────────────────
function initMap() {
    if (leafletMap) return;
    leafletMap = L.map('map').setView([20.5937, 78.9629], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
    }).addTo(leafletMap);
}

// ─── GET logic ───────────────────────────────────────────────────────────────
fetchBtn.addEventListener('click', async () => {
    const phoneNumber = phoneInput.value.trim();
    if (!phoneNumber) { alert('Please enter a phone number.'); return; }

    fetchBtn.disabled = true;
    fetchBtn.textContent = 'Fetching…';
    resultsSection.classList.add('hidden');

    try {
        // Query the server-side filter — avoids fetching the entire collection
        const response = await fetch(`/api/farms/geojson?farm_id=${encodeURIComponent(phoneNumber)}`);

        if (!response.ok) {
            let detail = `Server returned ${response.status}`;
            try {
                const errBody = await response.json();
                detail = errBody.detail || detail;
            } catch (_) { }
            throw new Error(detail);
        }

        const featureCollection = await response.json();
        
        // The server already filtered by farm_id — grab the first result
        const data = featureCollection.features[0];

        if (!data) {
            throw new Error(`No farmland record found for phone number: ${phoneNumber}`);
        }

        // Reveal results panel
        resultsSection.classList.remove('hidden');

        // ── Status badge ──────────────────────────────────────────────────────
        statusBadge.textContent = 'PostGIS Native Healing';
        statusBadge.className = 'badge badge-success';

        // ── Telemetry list ────────────────────────────────────────────────────
        telemetryList.innerHTML = '';
        noFixes.classList.remove('hidden');
        noFixes.innerHTML = 'Processed via SQL Materialized View';

        // ── Raw JSON ──────────────────────────────────────────────────────────
        rawJson.textContent = JSON.stringify(data, null, 2);

        // ── Leaflet map ───────────────────────────────────────────────────────
        initMap();
        if (farmLayer) { leafletMap.removeLayer(farmLayer); farmLayer = null; }

        if (data.geometry) {
            farmLayer = L.geoJSON(data, {
                style: { color: '#4f8ef7', weight: 2, fillColor: '#4f8ef7', fillOpacity: 0.2 },
            }).addTo(leafletMap);
            leafletMap.fitBounds(farmLayer.getBounds(), { padding: [30, 30] });
        }

    } catch (err) {
        // Visible error state
        resultsSection.classList.remove('hidden');
        statusBadge.textContent = 'error';
        statusBadge.className = 'badge badge-error';
        telemetryList.innerHTML = '';
        noFixes.classList.add('hidden');
        rawJson.textContent = `Error: ${err.message}`;
    } finally {
        fetchBtn.disabled = false;
        fetchBtn.textContent = 'Fetch Farm Data';
    }
});

// ─── Enter key ───────────────────────────────────────────────────────────────
phoneInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') fetchBtn.click();
});
