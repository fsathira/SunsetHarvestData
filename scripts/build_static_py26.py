# -*- coding: utf-8 -*-
"""
Standalone static dashboard builder for Python 2.6+ (stdlib only).
No pandas or other dependencies. Run on a server that only has Python 2.6:

  python scripts/build_static_py26.py data/fermentation_responses_20260305.csv -o dist

Or copy this script + CSV to the server and run there.
"""
from __future__ import print_function

import sys
try:
    unicode
except NameError:
    unicode = str  # Python 3

import csv
import json
import os
import shutil
from collections import defaultdict
from datetime import datetime

# Python 2.6: urllib, urllib2. Python 3: urllib.parse, urllib.request
try:
    import urllib2
    import urllib
    def _urlopen(url, timeout=15):
        return urllib2.urlopen(url, timeout=timeout)
    def _urlencode(params):
        return urllib.urlencode(params)
except ImportError:
    import urllib.request as urllib2
    import urllib.parse
    def _urlopen(url, timeout=15):
        return urllib2.urlopen(url, timeout=timeout)
    def _urlencode(params):
        return urllib.parse.urlencode(params)

# Python 2.6: optparse. Python 2.7+/3: argparse.
try:
    import argparse as _argparse
    _HAS_ARGPARSE = True
except ImportError:
    _HAS_ARGPARSE = False
try:
    import optparse
except ImportError:
    optparse = None

# --- Config ---
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FAIRFIELD_LAT = 38.2494
FAIRFIELD_LON = -122.0398
NOTES_COL = "Anything notable about this fermentation today?"
DATE_COL = "Date of Measurement"


def parse_date(s):
    """Parse date string; return (date_obj, year) or (None, None)."""
    if not s or not str(s).strip():
        return None, None
    s = str(s).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            dt = datetime.strptime(s[:10], fmt)
            return dt.date(), dt.year
        except ValueError:
            continue
    return None, None


def safe_float(s, default=None):
    try:
        if s is None or (isinstance(s, str) and not s.strip()):
            return default
        return float(s)
    except (ValueError, TypeError):
        return default


def safe_int(s, default=None):
    try:
        if s is None or (isinstance(s, str) and not s.strip()):
            return default
        return int(float(s))
    except (ValueError, TypeError):
        return default


def load_csv_rows(csv_path):
    """Load CSV into list of dicts; normalize column names."""
    rows = []
    with open(csv_path, "r" if sys.version_info[0] >= 3 else "rU") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = dict((k.strip() if k else k, v) for k, v in row.items())
            if NOTES_COL in row and "Notes" not in row:
                row["Notes"] = row.get(NOTES_COL, "")
            rows.append(row)
    return rows


def add_days(rows):
    """Add 'day' to each row (days since first measurement per varietal/bin/vintage)."""
    by_lot = defaultdict(list)
    for i, r in enumerate(rows):
        dt, year = parse_date(r.get(DATE_COL))
        varietal = (r.get("Varietal") or "").strip()
        bin_val = safe_int(r.get("Bin"))
        if dt is not None and varietal and bin_val is not None:
            by_lot[(year, varietal, bin_val)].append((i, dt, r))
    for key, group in by_lot.items():
        if not group:
            continue
        dates = [dt for (_, dt, _) in group]
        start = min(dates)
        for (idx, dt, r) in group:
            day = (dt - start).days
            rows[idx]["_day"] = day
            rows[idx]["_vintage"] = key[0]
    for r in rows:
        if "_day" not in r:
            r["_day"] = None
            r["_vintage"] = None
    return rows


def fetch_weather(start_date, end_date):
    """Fetch Fairfield weather from Open-Meteo; return dict with day_index, temp_mean_f, precip_in."""
    params = {
        "latitude": FAIRFIELD_LAT,
        "longitude": FAIRFIELD_LON,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "America/Los_Angeles",
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
    }
    url = OPEN_METEO_ARCHIVE + "?" + _urlencode(params)
    try:
        resp = _urlopen(url, timeout=15)
        data = json.loads(resp.read())
    except Exception:
        return {"day_index": [], "temp_mean_f": [], "precip_in": []}
    daily = data.get("daily", {})
    if not daily or not daily.get("time"):
        return {"day_index": [], "temp_mean_f": [], "precip_in": []}
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])
    temp_mean = [(float(a) + float(b)) / 2 for a, b in zip(tmax, tmin)] if tmax and tmin else []
    return {
        "day_index": range(len(daily["time"])),
        "temp_mean_f": temp_mean,
        "precip_in": [float(p) for p in precip] if precip else [],
    }


def build_payload(rows):
    """Build JSON payload for the static page."""
    vintages = sorted(set(r["_vintage"] for r in rows if r.get("_vintage") is not None))
    varietals = sorted(set((r.get("Varietal") or "").strip() for r in rows if (r.get("Varietal") or "").strip()))
    bins_by_key = {}
    lots = {}

    by_lot = defaultdict(list)
    for r in rows:
        vint = r.get("_vintage")
        varietal = (r.get("Varietal") or "").strip()
        bin_val = safe_int(r.get("Bin"))
        day = r.get("_day")
        if vint is None or not varietal or bin_val is None or day is None:
            continue
        by_lot[(vint, varietal, bin_val)].append(r)

    for (vint, varietal, bin_val), group in by_lot.items():
        group = sorted(group, key=lambda x: (x.get(DATE_COL),))
        key_bins = str(vint) + "|" + varietal
        if key_bins not in bins_by_key:
            bins_by_key[key_bins] = []
        if bin_val not in bins_by_key[key_bins]:
            bins_by_key[key_bins].append(bin_val)
        lot_key = str(vint) + "|" + varietal + "|" + str(bin_val)

        dates = []
        for r in group:
            dt, _ = parse_date(r.get(DATE_COL))
            if dt:
                dates.append(dt)
        if not dates:
            continue
        start_date = min(dates)
        end_date = max(dates)
        weather = fetch_weather(start_date, end_date)

        hover_brix = []
        hover_temp = []
        rows_out = []
        for r in group:
            note = (r.get("Notes") or "") if isinstance(r.get("Notes"), (str, unicode)) else ""
            rep = (r.get("Reported by") or "") if isinstance(r.get("Reported by"), (str, unicode)) else ""
            dt, _ = parse_date(r.get(DATE_COL))
            date_str = dt.strftime("%Y-%m-%d") if dt else ""
            day = r.get("_day", 0)
            brix = safe_float(r.get("Brix"))
            temp = safe_float(r.get("Temperature"))
            rows_out.append({
                "day": day,
                "date": date_str,
                "brix": brix,
                "temp": temp,
                "notes": note,
                "reported_by": rep,
            })
            note_trim = note[:150] + ("..." if len(note) > 150 else "")
            hover_brix.append("Day %s · %s<br>Brix: %s<br>%s<br>%s" % (day, date_str, r.get("Brix"), rep, note_trim))
            hover_temp.append("Day %s · %s<br>Must: %s °F<br>%s<br>%s" % (day, date_str, r.get("Temperature"), rep, note_trim))

        lot = {
            "days": [r.get("_day") for r in group],
            "brix": [safe_float(r.get("Brix")) for r in group],
            "must_temp": [safe_float(r.get("Temperature")) for r in group],
            "hover_brix": hover_brix,
            "hover_temp": hover_temp,
            "rows": rows_out,
            "weather": weather,
        }
        lots[lot_key] = lot

    for k in bins_by_key:
        bins_by_key[k] = sorted(bins_by_key[k])

    return {
        "vintages": vintages,
        "varietals": varietals,
        "binsByKey": bins_by_key,
        "lots": lots,
    }


def make_html(payload):
    """Return full HTML with embedded JSON. Uses placeholder __DATA_JS__."""
    data_js = json.dumps(payload)
    # Load template from same dir or inline (template uses __DATA_JS__)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "build_static_template.html")
    if os.path.exists(template_path):
        with open(template_path, "r") as f:
            html = f.read()
    else:
        html = _get_embedded_template()
    return html.replace("__DATA_JS__", data_js)


def _get_embedded_template():
    """Embedded HTML template (no external file)."""
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fermentation Tracking - Sunset Cellars</title>
  <link rel="icon" href="./assets/favicon.ico" type="image/x-icon">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Lato:wght@400;700&display=swap">
  <link rel="stylesheet" href="./assets/sunset_cellars.css">
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body { margin: 0; font-family: 'Lato', 'Helvetica Neue', sans-serif; background-color: #F8F5F0; color: #2C2C2C; }
    .app-container { min-height: 100vh; }
    .dashboard-header { background-color: #5C2C2E; color: white; padding: 1.5rem 2rem; margin-bottom: 2rem; }
    .dashboard-header img { height: 48px; width: auto; display: block; margin-bottom: 0.75rem; max-height: 52px; }
    .dashboard-header h1 { font-family: 'Cormorant Garamond', Georgia, serif; font-weight: 600; margin: 0; font-size: 1.75rem; letter-spacing: 0.02em; }
    .dashboard-header p { margin: 0.25rem 0 0; opacity: 0.9; font-size: 0.95rem; }
    .dashboard-body { max-width: 1200px; margin: 0 auto; padding: 0 1.5rem 2rem; }
    .filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
    .filters label { display: block; margin-bottom: 0.35rem; color: #5C5C5C; font-size: 0.85rem; }
    .filters select { width: 100%; padding: 0.5rem; border: 1px solid #D4C4B0; border-radius: 6px; font-family: inherit; }
    .card { background-color: #fff; padding: 1.25rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid #D4C4B0; margin-bottom: 1.5rem; }
    #note-detail { margin-top: 1rem; padding: 1rem 1.25rem; background-color: #fff; border-radius: 8px; border: 1px solid #D4C4B0; min-height: 60px; display: none; }
    #note-detail.visible { display: block; }
    footer { margin-top: 2rem; text-align: center; color: #5C5C5C; font-size: 0.8rem; }
  </style>
</head>
<body>
  <div class="app-container">
    <header class="dashboard-header">
      <img src="./assets/SUNSET_LOGO_white.png" alt="Sunset Cellars">
      <h1>Fermentation Tracking</h1>
      <p>Sunset Cellars - Suisun Valley, Fairfield, CA - Data from CSV export</p>
    </header>
    <div class="dashboard-body">
      <div class="filters">
        <div>
          <label for="filter-vintage">Vintage</label>
          <select id="filter-vintage"></select>
        </div>
        <div>
          <label for="filter-varietal">Varietal / Vineyard</label>
          <select id="filter-varietal"></select>
        </div>
        <div>
          <label for="filter-bin">Bin</label>
          <select id="filter-bin"></select>
        </div>
      </div>
      <div class="card">
        <div id="graph-stacked" style="height: 720px;"></div>
      </div>
      <div id="note-detail"></div>
      <footer>Brix &amp; must temp by fermentation day - Fairfield weather from Open-Meteo</footer>
    </div>
  </div>
  <script id="harvest-data" type="application/json">__DATA_JS__</script>
  <script>
(function() {
  var dataEl = document.getElementById('harvest-data');
  var PAYLOAD = JSON.parse(dataEl.textContent);
  var vintages = PAYLOAD.vintages || [];
  var varietals = PAYLOAD.varietals || [];
  var binsByKey = PAYLOAD.binsByKey || {};
  var lots = PAYLOAD.lots || {};

  var COLORS = { primary: '#5C2C2E', primary_light: '#8B4042', accent: '#2D5016', border: '#D4C4B0', text: '#2C2C2C' };

  function lotKey(vintage, varietal, bin) { return vintage + '|' + varietal + '|' + bin; }

  function getVarietal() { return varietals[parseInt(document.getElementById('filter-varietal').value, 10)]; }
  function getBins(vintage, varietal) {
    var k = vintage + '|' + varietal;
    return binsByKey[k] || [];
  }

  function buildFigureSubplots(lot) {
    if (!lot || !lot.days || lot.days.length === 0) { Plotly.react('graph-stacked', [], {}); return; }
    var trace1 = { x: lot.days, y: lot.brix, mode: 'lines+markers', name: 'Brix', type: 'scatter', line: { width: 2, color: COLORS.primary }, marker: { size: 8 }, hovertext: lot.hover_brix, hoverinfo: 'text', xaxis: 'x', yaxis: 'y' };
    var trace2 = { x: lot.days, y: lot.must_temp, mode: 'lines+markers', name: 'Must temp (°F)', type: 'scatter', line: { width: 2, color: COLORS.primary_light }, marker: { size: 8 }, hovertext: lot.hover_temp, hoverinfo: 'text', xaxis: 'x2', yaxis: 'y2' };
    var hasWeather = lot.weather && lot.weather.day_index && lot.weather.day_index.length > 0;
    var data = [trace1, trace2];
    if (hasWeather) {
      data.push({ x: lot.weather.day_index, y: lot.weather.temp_mean_f, mode: 'lines+markers', name: 'Air temp (°F)', type: 'scatter', line: { width: 2, color: COLORS.accent }, marker: { size: 6 }, xaxis: 'x3', yaxis: 'y3' });
      data.push({ x: lot.weather.day_index, y: lot.weather.precip_in, name: 'Rain (in)', type: 'bar', marker: { color: 'rgba(100,149,237,0.7)' }, xaxis: 'x3', yaxis: 'y4' });
    }
    var layout = {
      grid: { rows: 3, columns: 1, pattern: 'independent', roworder: 'top to bottom' },
      xaxis: { title: 'Day (fermentation)', anchor: 'y', domain: [0, 1] },
      yaxis: { title: 'Brix (°)', anchor: 'x', domain: [0.65, 1] },
      xaxis2: { title: 'Day (fermentation)', anchor: 'y2', domain: [0, 1] },
      yaxis2: { title: 'Must temp (°F)', anchor: 'x2', domain: [0.32, 0.65] },
      xaxis3: { title: 'Day (fermentation)', anchor: 'y3', domain: [0, 1] },
      yaxis3: { title: 'Air temp (°F)', anchor: 'x3', domain: [0, 0.32] },
      yaxis4: { title: 'Rain (in)', side: 'right', overlaying: 'y3', anchor: 'x3' },
      showlegend: true,
      legend: { orientation: 'h', y: 1.02 },
      margin: { t: 80, b: 50, l: 60, r: 50 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Lato', size: 12 }
    };
    Plotly.react('graph-stacked', data, layout);
  }

  function updateBinOptions() {
    var vintage = parseInt(document.getElementById('filter-vintage').value, 10);
    var varietal = getVarietal();
    var bins = getBins(vintage, varietal);
    var sel = document.getElementById('filter-bin');
    sel.innerHTML = '';
    for (var i = 0; i < bins.length; i++) {
      var opt = document.createElement('option');
      opt.value = bins[i];
      opt.textContent = 'Bin ' + bins[i];
      sel.appendChild(opt);
    }
    return bins[0];
  }

  function render() {
    var vintageSel = document.getElementById('filter-vintage');
    var varietalSel = document.getElementById('filter-varietal');
    var binSel = document.getElementById('filter-bin');
    vintageSel.innerHTML = vintages.map(function(v) { return '<option value="' + v + '">' + v + '</option>'; }).join('');
    varietalSel.innerHTML = varietals.map(function(v, i) { return '<option value="' + i + '">' + v.replace(/</g, '&lt;') + '</option>'; }).join('');
    var firstBin = updateBinOptions();
    if (firstBin !== undefined) binSel.value = firstBin;

    var vintage = vintages.length ? vintages[vintages.length - 1] : null;
    if (vintage != null) vintageSel.value = vintage;
    varietalSel.value = '0';
    updateBinOptions();
    var varietal = getVarietal();
    var bin = getBins(vintage, varietal)[0];
    if (bin != null) binSel.value = bin;

    var key = lotKey(vintage, varietal, bin);
    var lot = lots[key];
    buildFigureSubplots(lot);

    vintageSel.addEventListener('change', function() { var b = updateBinOptions(); if (b != null) binSel.value = b; onFilterChange(); });
    varietalSel.addEventListener('change', function() { var b = updateBinOptions(); if (b != null) binSel.value = b; onFilterChange(); });
    binSel.addEventListener('change', onFilterChange);

    function onFilterChange() {
      var v = parseInt(vintageSel.value, 10);
      var varVal = getVarietal();
      var b = parseInt(binSel.value, 10);
      var k = lotKey(v, varVal, b);
      buildFigureSubplots(lots[k] || null);
      document.getElementById('note-detail').className = '';
      document.getElementById('note-detail').style.display = 'none';
    }

    var noteDiv = document.getElementById('note-detail');
    document.getElementById('graph-stacked').on('plotly_click', function(d) {
      if (!d || !d.points || d.points.length === 0) return;
      var pt = d.points[0];
      if (pt.curveNumber > 1) return;
      var pointIndex = pt.pointIndex;
      var v = parseInt(vintageSel.value, 10);
      var varVal = getVarietal();
      var b = parseInt(binSel.value, 10);
      var k = lotKey(v, varVal, b);
      var lot = lots[k];
      if (!lot || !lot.rows || pointIndex >= lot.rows.length) return;
      var row = lot.rows[pointIndex];
      noteDiv.innerHTML = '<strong>Day ' + row.day + ' - ' + row.date + ' - Bin ' + b + '</strong><br><span style="color:#5C5C5C;font-size:0.9rem">Reported by: ' + (row.reported_by || '') + '</span><br><p style="margin:0.5rem 0 0;white-space:pre-wrap">' + (row.notes || '(No note)').replace(/</g, '&lt;').replace(/&/g, '&amp;') + '</p>';
      noteDiv.className = 'visible';
      noteDiv.style.display = 'block';
    });
  }

  if (vintages.length && varietals.length) render(); else document.getElementById('graph-stacked').innerHTML = '<p>No data.</p>';
})();
  </script>
</body>
</html>
"""


def main():
    csv_path = None
    out_dir = os.path.abspath("dist")
    if _HAS_ARGPARSE:
        parser = _argparse.ArgumentParser(description="Build static HTML dashboard from CSV (stdlib only)")
        parser.add_argument("csv", nargs="?", default=None, help="Path to CSV file")
        parser.add_argument("-o", "--output", default="dist", help="Output directory (default: dist)")
        args = parser.parse_args()
        csv_path = args.csv
        out_dir = os.path.abspath(args.output)
    elif optparse is not None:
        parser = optparse.OptionParser(usage="usage: %prog [csv_file] [options]")
        parser.add_option("-o", "--output", dest="output", default="dist", help="Output directory (default: dist)")
        (options, args) = parser.parse_args()
        csv_path = args[0] if args else None
        out_dir = os.path.abspath(options.output)
    else:
        print("Need optparse (Python 2.6) or argparse (Python 2.7+)")
        return 1

    if csv_path and not os.path.exists(csv_path):
        print("CSV not found: " + csv_path)
        return 1

    print("Loading data...")
    if csv_path:
        rows = load_csv_rows(csv_path)
    else:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        all_rows = []
        for f in sorted(os.listdir(data_dir)):
            if f.endswith(".csv"):
                all_rows.extend(load_csv_rows(os.path.join(data_dir, f)))
        rows = all_rows

    if not rows:
        print("No rows in CSV.")
        return 1

    rows = add_days(rows)
    payload = build_payload(rows)

    if not payload["vintages"]:
        print("No fermentation data found.")
    else:
        print("Found %d vintage(s), %d varietal(s), %d lot(s)." % (
            len(payload["vintages"]), len(payload["varietals"]), len(payload["lots"])))

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    assets_dir = os.path.join(out_dir, "assets")
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ["SUNSET_LOGO_white.png", "favicon.ico", "sunset_cellars.css"]:
        src = os.path.join(project_root, "assets", name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(assets_dir, name))
            print("Copied assets/" + name)
        else:
            print("Warning: assets/" + name + " not found, skipping")

    html = make_html(payload)
    index_path = os.path.join(out_dir, "index.html")
    try:
        html_bytes = html.encode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        html_bytes = html
    with open(index_path, "wb") as f:
        f.write(html_bytes)
    print("Wrote " + index_path)
    print("Done. Upload the contents of " + out_dir + " to your web server.")
    return 0


if __name__ == "__main__":
    exit(main())
