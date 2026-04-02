/* OpenQuery Dashboard — Vanilla JS */

const API = '/api/v1';
const history = [];
let allSources = [];

// ── Bootstrap ──

document.addEventListener('DOMContentLoaded', () => {
  fetchSources();
  fetchHealth();
  setInterval(fetchHealth, 30000);

  document.getElementById('query-form').addEventListener('submit', submitQuery);
  document.getElementById('source-filter').addEventListener('input', filterSources);
  document.getElementById('country-filter').addEventListener('change', filterSources);
});

// ── Sources ──

async function fetchSources() {
  try {
    const res = await fetch(`${API}/sources`);
    const data = await res.json();
    allSources = Array.isArray(data) ? data : (data.sources || []);
    renderSourcesTable(allSources);
    populateDropdowns(allSources);
  } catch (e) {
    console.error('Failed to fetch sources:', e);
  }
}

function renderSourcesTable(sources) {
  const tbody = document.getElementById('sources-body');

  if (!sources.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="center muted">No sources found</td></tr>';
    return;
  }

  tbody.innerHTML = sources.map(s => {
    const meta = s.meta || s;
    return `<tr>
      <td><strong>${meta.name || ''}</strong></td>
      <td>${meta.country || ''}</td>
      <td><span class="status-dot status-healthy"></span>Healthy</td>
      <td>${meta.display_name || meta.description || ''}</td>
      <td>${(meta.supported_inputs || []).join(', ')}</td>
      <td>${meta.requires_captcha ? 'Yes' : 'No'}</td>
    </tr>`;
  }).join('');
}

function populateDropdowns(sources) {
  // Source dropdown
  const select = document.getElementById('source-select');
  select.innerHTML = '<option value="">Select a source...</option>' +
    sources.map(s => {
      const meta = s.meta || s;
      return `<option value="${meta.name}">${meta.name} — ${meta.display_name || ''}</option>`;
    }).join('');

  // Country filter
  const countries = [...new Set(sources.map(s => (s.meta || s).country).filter(Boolean))].sort();
  const countrySelect = document.getElementById('country-filter');
  countrySelect.innerHTML = '<option value="">All Countries</option>' +
    countries.map(c => `<option value="${c}">${c}</option>`).join('');
}

function filterSources() {
  const text = document.getElementById('source-filter').value.toLowerCase();
  const country = document.getElementById('country-filter').value;

  const filtered = allSources.filter(s => {
    const meta = s.meta || s;
    const matchText = !text ||
      (meta.name || '').toLowerCase().includes(text) ||
      (meta.display_name || '').toLowerCase().includes(text) ||
      (meta.description || '').toLowerCase().includes(text);
    const matchCountry = !country || meta.country === country;
    return matchText && matchCountry;
  });

  renderSourcesTable(filtered);
}

// ── Health ──

async function fetchHealth() {
  try {
    const res = await fetch(`${API}/health`);
    const data = await res.json();

    const statusEl = document.getElementById('overall-status');
    const statusColor = data.status === 'ok' ? 'var(--green)' :
                       data.status === 'degraded' ? 'var(--yellow)' : 'var(--red)';
    statusEl.innerHTML = `<span style="color:${statusColor}">&#9679;</span> ${data.status.toUpperCase()}`;

    const countEl = document.getElementById('source-count');
    countEl.textContent = `${data.sources_total || 0} sources | ${data.sources_healthy || 0} healthy`;

    document.getElementById('refresh-timer').textContent = `(updated ${new Date().toLocaleTimeString()})`;
  } catch (e) {
    console.error('Failed to fetch health:', e);
  }
}

// ── Query ──

async function submitQuery(e) {
  e.preventDefault();

  const source = document.getElementById('source-select').value;
  const docType = document.getElementById('doc-type').value;
  const docNumber = document.getElementById('doc-number').value;
  const btn = document.getElementById('query-btn');

  if (!source || !docNumber) return;

  btn.disabled = true;
  btn.textContent = 'Querying...';

  try {
    const res = await fetch(`${API}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source: source,
        document_type: docType,
        document_number: docNumber,
      }),
    });

    const data = await res.json();

    // Show result
    const resultEl = document.getElementById('query-result');
    resultEl.classList.remove('hidden');
    document.getElementById('result-json').textContent = JSON.stringify(data, null, 2);

    // Add to history
    addToHistory({
      time: new Date().toLocaleTimeString(),
      source: source,
      document: `${docType}:${docNumber.slice(0, 4)}***`,
      latency: `${data.latency_ms || 0}ms`,
      ok: data.ok,
      error: data.error,
    });
  } catch (e) {
    addToHistory({
      time: new Date().toLocaleTimeString(),
      source: source,
      document: `${docType}:${docNumber.slice(0, 4)}***`,
      latency: '-',
      ok: false,
      error: e.message,
    });
  } finally {
    btn.disabled = false;
    btn.textContent = 'Query';
  }
}

// ── History ──

function addToHistory(entry) {
  history.unshift(entry);
  if (history.length > 50) history.pop();

  const tbody = document.getElementById('history-body');
  tbody.innerHTML = history.map(h => {
    const badge = h.ok
      ? '<span class="badge badge-ok">OK</span>'
      : `<span class="badge badge-error">${h.error || 'ERROR'}</span>`;
    return `<tr>
      <td>${h.time}</td>
      <td>${h.source}</td>
      <td>${h.document}</td>
      <td>${h.latency}</td>
      <td>${badge}</td>
    </tr>`;
  }).join('');
}
