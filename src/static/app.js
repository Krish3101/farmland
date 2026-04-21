// Global state
let lastFarmResponse = null;
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
const submitBtn      = document.getElementById('submitBtn');

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
    submitBtn.classList.add('hidden');
    lastFarmResponse = null;

    try {
        const response = await fetch(`/api/farm/${encodeURIComponent(phoneNumber)}`);

        // W-3 fix: explicitly handle non-2xx responses
        if (!response.ok) {
            let detail = `Server returned ${response.status}`;
            try {
                const errBody = await response.json();
                detail = errBody.detail || detail;
            } catch (_) { /* body wasn't JSON — keep the status code message */ }
            throw new Error(detail);
        }

        const data = await response.json();

        // Save globally for POST
        lastFarmResponse = data;

        // Reveal results panel
        resultsSection.classList.remove('hidden');

        // ── Status badge ──────────────────────────────────────────────────────
        const status = data.properties?.status || 'unknown';
        statusBadge.textContent = status;
        statusBadge.className = 'badge';
        if (status === 'success')              statusBadge.classList.add('badge-success');
        else if (status === 'success_with_fixes') statusBadge.classList.add('badge-warning');
        else                                   statusBadge.classList.add('badge-error');

        // ── Telemetry list ────────────────────────────────────────────────────
        const fixes = data.properties?.fixes_applied || [];
        telemetryList.innerHTML = '';
        if (fixes.length > 0) {
            noFixes.classList.add('hidden');
            fixes.forEach(fix => {
                const li = document.createElement('li');
                li.textContent = fix;
                telemetryList.appendChild(li);
            });
        } else {
            noFixes.classList.remove('hidden');
        }

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
            submitBtn.classList.remove('hidden');
        }

    } catch (err) {
        // Visible error state — never freezes silently
        resultsSection.classList.remove('hidden');
        statusBadge.textContent = 'error';
        statusBadge.className = 'badge badge-error';
        telemetryList.innerHTML = '';
        noFixes.classList.add('hidden');
        rawJson.textContent = `❌ Error: ${err.message}`;
    } finally {
        fetchBtn.disabled = false;
        fetchBtn.textContent = 'Fetch & Clean (GET)';
    }
});

// ─── POST logic ──────────────────────────────────────────────────────────────
submitBtn.addEventListener('click', async () => {
    if (!lastFarmResponse) { alert('No farm data loaded. Please fetch first.'); return; }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting…';

    try {
        const response = await fetch('/api/sentinel/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ geojson_payload: lastFarmResponse }),
        });

        // W-3 fix applied to POST as well
        if (!response.ok) {
            let detail = `Server returned ${response.status}`;
            try { const e = await response.json(); detail = e.detail || detail; } catch (_) {}
            throw new Error(detail);
        }

        const result = await response.json();
        alert(`✅ ${result.message}`);
    } catch (err) {
        alert(`❌ Submission failed: ${err.message}`);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '🛰️ Submit to Sentinel (POST)';
    }
});

// ─── Enter key ───────────────────────────────────────────────────────────────
phoneInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') fetchBtn.click();
});
