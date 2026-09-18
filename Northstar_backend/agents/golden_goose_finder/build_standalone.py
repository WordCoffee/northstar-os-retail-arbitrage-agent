"""Generate standalone panel with embedded live scan data."""
import json
from pathlib import Path

# Read the latest live scan report
report_dir = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\agents\data\golden-goose-reports")
reports = sorted(report_dir.glob("goose_live_scan_*.json"), reverse=True)
if not reports:
    print("No live scan reports found!")
    exit(1)

latest = reports[0]
print(f"Using: {latest.name}")
data = json.load(open(latest))
opps = data.get("opportunities", [])
print(f"Embedding {len(opps)} opportunities")

# Read the panel HTML
panel_path = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\docs\index.html")
html = panel_path.read_text(encoding="utf-8")

# Replace the runScan function to load embedded data
old_scan = """    // --- Scan handler ---
    async function runScan() {
      if (state.scanning) return;
      state.scanning = true;
      $('btn-mock').disabled = true;
      $('btn-mock').innerHTML = '<span class="spinner"></span> Scanning…';
      setStatus('running', 'Running mock scan — discovering multi-pack opportunities…');

      try {
        var filters = getFilters();
        var params = {};
        if (filters.category) params.categories = [filters.category];
        params.roi_floor = filters.roi_floor;
        params.min_monthly_sales = filters.min_monthly_sales;

        var data = await apiPost('/scan-mock', params);

        state.opportunities = data.opportunities || [];
        applyFiltersAndRender();
        renderKpis(data.summary || {}, data.meta || {});

        setStatus('done', 'Scan complete — ' + state.opportunities.length + ' opportunities found in ' + ((data.meta || {}).elapsed_seconds || '?') + 's');
      } catch (err) {
        setStatus('error', 'Scan failed: ' + err.message);
        state.opportunities = [];
        state.filtered = [];
        renderTable();
      } finally {
        state.scanning = false;
        $('btn-mock').disabled = false;
        $('btn-mock').innerHTML = '▶ Run Mock Scan';
      }
    }"""

embedded_json = json.dumps(opps, default=str)

new_scan = f"""    // --- Embedded live scan data ---
    var EMBEDDED_DATA = {embedded_json};

    // --- Scan handler (loads embedded data) ---
    async function runScan() {{
      if (state.scanning) return;
      state.scanning = true;
      $('btn-mock').disabled = true;
      $('btn-mock').innerHTML = '<span class="spinner"></span> Loading…';
      setStatus('running', 'Loading live scan data — {len(opps)} Costco opportunities…');

      try {{
        state.opportunities = EMBEDDED_DATA;
        applyFiltersAndRender();
        renderKpis({{}}, {{}});

        setStatus('done', 'Loaded ' + state.opportunities.length + ' live Costco opportunities');
      }} catch (err) {{
        setStatus('error', 'Load failed: ' + err.message);
        state.opportunities = [];
        state.filtered = [];
        renderTable();
      }} finally {{
        state.scanning = false;
        $('btn-mock').disabled = false;
        $('btn-mock').innerHTML = '▶ Load Opportunities';
      }}
    }}"""

html = html.replace(old_scan, new_scan)

# Also update the button text
html = html.replace('▶ Run Mock Scan', '▶ Load Opportunities')
html = html.replace('Running mock scan — discovering multi-pack opportunities…', 'Loading live scan data…')

# Update status text
html = html.replace('Scan complete —', 'Loaded')
html = html.replace('Scan failed:', 'Load failed:')

# Remove the API helper function since we don't need it
old_api = """    // --- API helper ---
    async function apiPost(endpoint, body) {
      var resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!resp.ok) {
        var text = await resp.text();
        throw new Error(endpoint + ' failed (' + resp.status + '): ' + text.substring(0, 200));
      }
      return resp.json();
    }"""

new_api = """    // --- Standalone mode (no API needed) ---
    // Data is embedded directly in this file from the latest live scan."""

html = html.replace(old_api, new_api)

# Update title
html = html.replace('<title>Northstar OS — Golden Goose Finder</title>',
                    '<title>Northstar OS — Golden Goose Finder (Live Costco Scan)</title>')

# Add a header banner
banner = '<div style="background:var(--green);color:#000;text-align:center;padding:6px;font-size:11px;font-weight:600;letter-spacing:.05em">LIVE COSTCO SCAN — ' + str(len(opps)) + ' OPPORTUNITIES — ' + str(sum(1 for o in opps if o.get("tier") == "HIGH")) + ' HIGH TIER</div>'
html = html.replace('<body>', '<body>' + banner)

panel_path.write_text(html, encoding="utf-8")
print(f"Standalone panel written to: {panel_path}")
print(f"File size: {panel_path.stat().st_size / 1024:.0f} KB")
