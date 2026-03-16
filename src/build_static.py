"""
Build a static HTML version of the fermentation dashboard.
Reads CSV, runs QC and add_days, pre-fetches weather per lot, outputs dist/ with
index.html and assets for hosting on a static server (e.g. cs.stanford.edu/~user/projects/).
"""
import sys
if sys.version_info[0] < 3:
    sys.exit("This script requires Python 3. Run: python3 -m src.build_static ...")

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from .config import DATA_DIR, PROJECT_ROOT
from .load_data import load_from_csv, load_from_csv_multi, get_raw_data
from .qc import run_qc
from .weather import fetch_fairfield_weather


def _add_days(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'day' (days since first measurement) per (Varietal, Bin, vintage)."""
    out = df.copy()
    out["day"] = None
    for (varietal, bin_val, vint), g in df.groupby(["Varietal", "Bin", "vintage"]):
        g = g.dropna(subset=["Date of Measurement"])
        if g.empty:
            continue
        start = g["Date of Measurement"].min()
        mask = (out["Varietal"] == varietal) & (out["Bin"] == bin_val) & (out["vintage"] == vint)
        out.loc[mask, "day"] = (out.loc[mask, "Date of Measurement"] - start).dt.days
    return out


def build_payload(csv_path: Path | None, data_dir: Path | None) -> dict:
    """Load CSV, QC, add days, fetch weather per lot; return JSON-serializable payload."""
    if csv_path is not None:
        raw = get_raw_data(single_file=csv_path, use_google_sheets=False)
    else:
        raw = get_raw_data(data_dir=data_dir or DATA_DIR, use_google_sheets=False)
    if len(raw) == 0:
        return {"vintages": [], "varietals": [], "binsByKey": {}, "lots": {}}

    df, _ = run_qc(raw)
    df = _add_days(df)

    vintages = sorted(df["vintage"].dropna().astype(int).unique().tolist())
    varietals = sorted(df["Varietal"].dropna().unique().tolist())

    bins_by_key = {}
    lots = {}

    for (vintage, varietal, bin_val), g in df.groupby(["vintage", "Varietal", "Bin"]):
        g = g.sort_values("Date of Measurement").dropna(subset=["Date of Measurement", "day"])
        if g.empty:
            continue
        key_bins = f"{int(vintage)}|{varietal}"
        if key_bins not in bins_by_key:
            bins_by_key[key_bins] = []
        bin_int = int(bin_val)
        if bin_int not in bins_by_key[key_bins]:
            bins_by_key[key_bins].append(bin_int)
        lot_key = f"{int(vintage)}|{varietal}|{bin_int}"

        start = g["Date of Measurement"].min().date()
        end = g["Date of Measurement"].max().date()
        try:
            weather_df = fetch_fairfield_weather(start, end)
        except Exception:
            weather_df = pd.DataFrame()

        rows = []
        hover_brix = []
        hover_temp = []
        for _, r in g.iterrows():
            note = (r.get("Notes") or "") if pd.notna(r.get("Notes")) else ""
            rep = (r.get("Reported by") or "") if pd.notna(r.get("Reported by")) else ""
            d = r["Date of Measurement"]
            date_str = d.strftime("%Y-%m-%d") if pd.notna(d) else ""
            rows.append({
                "day": int(r["day"]),
                "date": date_str,
                "brix": float(r["Brix"]) if pd.notna(r["Brix"]) else None,
                "temp": float(r["Temperature"]) if pd.notna(r["Temperature"]) else None,
                "notes": note,
                "reported_by": rep,
            })
            hover_brix.append(f"Day {int(r['day'])} · {date_str}<br>Brix: {r['Brix']}<br>{rep}<br>{note[:150]}{'…' if len(note) > 150 else ''}")
            hover_temp.append(f"Day {int(r['day'])} · {date_str}<br>Must: {r['Temperature']} °F<br>{rep}<br>{note[:150]}{'…' if len(note) > 150 else ''}")

        lot = {
            "days": g["day"].astype(int).tolist(),
            "brix": g["Brix"].astype(float).tolist(),
            "must_temp": g["Temperature"].astype(float).tolist(),
            "hover_brix": hover_brix,
            "hover_temp": hover_temp,
            "rows": rows,
            "weather": {
                "day_index": weather_df["day_index"].tolist() if not weather_df.empty else [],
                "temp_mean_f": weather_df["temp_mean_f"].tolist() if not weather_df.empty else [],
                "precip_in": weather_df["precip_in"].tolist() if not weather_df.empty else [],
            } if not weather_df.empty else {"day_index": [], "temp_mean_f": [], "precip_in": []},
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


def make_html(payload: dict, assets_dir: Path) -> str:
    """Return full HTML string with embedded data and JS."""
    data_js = json.dumps(payload, allow_nan=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fermentation Tracking — Sunset Cellars</title>
  <link rel="icon" href="./assets/favicon.ico" type="image/x-icon">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Lato:wght@400;700&display=swap">
  <link rel="stylesheet" href="./assets/sunset_cellars.css">
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body {{ margin: 0; font-family: 'Lato', 'Helvetica Neue', sans-serif; background-color: #F8F5F0; color: #2C2C2C; }}
    .app-container {{ min-height: 100vh; }}
    .dashboard-header {{ background-color: #5C2C2E; color: white; padding: 1.5rem 2rem; margin-bottom: 2rem; }}
    .dashboard-header img {{ height: 48px; width: auto; display: block; margin-bottom: 0.75rem; max-height: 52px; }}
    .dashboard-header h1 {{ font-family: 'Cormorant Garamond', Georgia, serif; font-weight: 600; margin: 0; font-size: 1.75rem; letter-spacing: 0.02em; }}
    .dashboard-header p {{ margin: 0.25rem 0 0; opacity: 0.9; font-size: 0.95rem; }}
    .dashboard-body {{ max-width: 1200px; margin: 0 auto; padding: 0 1.5rem 2rem; }}
    .filters {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
    .filters label {{ display: block; margin-bottom: 0.35rem; color: #5C5C5C; font-size: 0.85rem; }}
    .filters select {{ width: 100%; padding: 0.5rem; border: 1px solid #D4C4B0; border-radius: 6px; font-family: inherit; }}
    .card {{ background-color: #fff; padding: 1.25rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid #D4C4B0; margin-bottom: 1.5rem; }}
    #note-detail {{ margin-top: 1rem; padding: 1rem 1.25rem; background-color: #fff; border-radius: 8px; border: 1px solid #D4C4B0; min-height: 60px; display: none; }}
    #note-detail.visible {{ display: block; }}
    footer {{ margin-top: 2rem; text-align: center; color: #5C5C5C; font-size: 0.8rem; }}
  </style>
</head>
<body>
  <div class="app-container">
    <header class="dashboard-header">
      <img src="./assets/SUNSET_LOGO_white.png" alt="Sunset Cellars">
      <h1>Fermentation Tracking</h1>
      <p>Sunset Cellars — Suisun Valley, Fairfield, CA · Data from CSV export</p>
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
      <footer>Brix &amp; must temp by fermentation day · Fairfield weather from Open-Meteo</footer>
    </div>
  </div>
  <script id="harvest-data" type="application/json">{data_js}</script>
  <script>
(function() {{
  var dataEl = document.getElementById('harvest-data');
  var PAYLOAD = JSON.parse(dataEl.textContent);
  var vintages = PAYLOAD.vintages || [];
  var varietals = PAYLOAD.varietals || [];
  var binsByKey = PAYLOAD.binsByKey || {{}};
  var lots = PAYLOAD.lots || {{}};

  var COLORS = {{ primary: '#5C2C2E', primary_light: '#8B4042', accent: '#2D5016', border: '#D4C4B0', text: '#2C2C2C' }};

  function lotKey(vintage, varietal, bin) {{ return vintage + '|' + varietal + '|' + bin; }}

  function getVarietal() {{ return varietals[parseInt(document.getElementById('filter-varietal').value, 10)]; }}
  function getBins(vintage, varietal) {{
    var k = vintage + '|' + varietal;
    return binsByKey[k] || [];
  }}

  function buildFigureSubplots(lot) {{
    if (!lot || !lot.days || lot.days.length === 0) {{ Plotly.react('graph-stacked', [], {{}}); return; }}
    var trace1 = {{ x: lot.days, y: lot.brix, mode: 'lines+markers', name: 'Brix', type: 'scatter', line: {{ width: 2, color: COLORS.primary }}, marker: {{ size: 8 }}, hovertext: lot.hover_brix, hoverinfo: 'text', xaxis: 'x', yaxis: 'y' }};
    var trace2 = {{ x: lot.days, y: lot.must_temp, mode: 'lines+markers', name: 'Must temp (°F)', type: 'scatter', line: {{ width: 2, color: COLORS.primary_light }}, marker: {{ size: 8 }}, hovertext: lot.hover_temp, hoverinfo: 'text', xaxis: 'x2', yaxis: 'y2' }};
    var hasWeather = lot.weather && lot.weather.day_index && lot.weather.day_index.length > 0;
    var data = [trace1, trace2];
    if (hasWeather) {{
      data.push({{ x: lot.weather.day_index, y: lot.weather.temp_mean_f, mode: 'lines+markers', name: 'Air temp (°F)', type: 'scatter', line: {{ width: 2, color: COLORS.accent }}, marker: {{ size: 6 }}, xaxis: 'x3', yaxis: 'y3' }});
      data.push({{ x: lot.weather.day_index, y: lot.weather.precip_in, name: 'Rain (in)', type: 'bar', marker: {{ color: 'rgba(100,149,237,0.7)' }}, xaxis: 'x3', yaxis: 'y4' }});
    }}
    var layout = {{
      grid: {{ rows: 3, columns: 1, pattern: 'independent', roworder: 'top to bottom' }},
      xaxis: {{ title: 'Day (fermentation)', anchor: 'y', domain: [0, 1] }},
      yaxis: {{ title: 'Brix (°)', anchor: 'x', domain: [0.65, 1] }},
      xaxis2: {{ title: 'Day (fermentation)', anchor: 'y2', domain: [0, 1] }},
      yaxis2: {{ title: 'Must temp (°F)', anchor: 'x2', domain: [0.32, 0.65] }},
      xaxis3: {{ title: 'Day (fermentation)', anchor: 'y3', domain: [0, 1] }},
      yaxis3: {{ title: 'Air temp (°F)', anchor: 'x3', domain: [0, 0.32] }},
      yaxis4: {{ title: 'Rain (in)', side: 'right', overlaying: 'y3', anchor: 'x3' }},
      showlegend: true,
      legend: {{ orientation: 'h', y: 1.02 }},
      margin: {{ t: 80, b: 50, l: 60, r: 50 }},
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: {{ family: 'Lato', size: 12 }}
    }};
    Plotly.react('graph-stacked', data, layout);
  }}

  function updateBinOptions() {{
    var vintage = parseInt(document.getElementById('filter-vintage').value, 10);
    var varietal = getVarietal();
    var bins = getBins(vintage, varietal);
    var sel = document.getElementById('filter-bin');
    sel.innerHTML = '';
    bins.forEach(function(b) {{
      var opt = document.createElement('option');
      opt.value = b;
      opt.textContent = 'Bin ' + b;
      sel.appendChild(opt);
    }});
    return bins[0];
  }}

  function render() {{
    var vintageSel = document.getElementById('filter-vintage');
    var varietalSel = document.getElementById('filter-varietal');
    var binSel = document.getElementById('filter-bin');
    vintageSel.innerHTML = vintages.map(function(v, i) {{ return '<option value="' + v + '">' + v + '</option>'; }}).join('');
    varietalSel.innerHTML = varietals.map(function(v, i) {{ return '<option value="' + i + '">' + v.replace(/</g, '&lt;') + '</option>'; }}).join('');
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

    vintageSel.addEventListener('change', function() {{ var b = updateBinOptions(); if (b != null) binSel.value = b; onFilterChange(); }});
    varietalSel.addEventListener('change', function() {{ var b = updateBinOptions(); if (b != null) binSel.value = b; onFilterChange(); }});
    binSel.addEventListener('change', onFilterChange);

    function onFilterChange() {{
      var v = parseInt(vintageSel.value, 10);
      var varVal = getVarietal();
      var b = parseInt(binSel.value, 10);
      var k = lotKey(v, varVal, b);
      buildFigureSubplots(lots[k] || null);
      document.getElementById('note-detail').className = '';
      document.getElementById('note-detail').style.display = 'none';
    }}

    var noteDiv = document.getElementById('note-detail');
    document.getElementById('graph-stacked').on('plotly_click', function(d) {{
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
      noteDiv.innerHTML = '<strong>Day ' + row.day + ' · ' + row.date + ' — Bin ' + b + '</strong><br><span style="color:#5C5C5C;font-size:0.9rem">Reported by: ' + (row.reported_by || '') + '</span><br><p style="margin:0.5rem 0 0;white-space:pre-wrap">' + (row.notes || '(No note)').replace(/</g, '&lt;').replace(/&/g, '&amp;') + '</p>';
      noteDiv.className = 'visible';
      noteDiv.style.display = 'block';
    }});
  }}

  if (vintages.length && varietals.length) render(); else document.getElementById('graph-stacked').innerHTML = '<p>No data.</p>';
}})();
  </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Build static HTML dashboard from CSV")
    parser.add_argument("csv", nargs="?", default=None, help="Path to CSV file (default: use all *.csv in data/)")
    parser.add_argument("-o", "--output", default="dist", help="Output directory (default: dist)")
    args = parser.parse_args()

    csv_path = Path(args.csv).resolve() if args.csv else None
    out_dir = Path(args.output).resolve()
    if csv_path is not None and not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    print("Loading data...")
    payload = build_payload(csv_path, None)
    if not payload["vintages"]:
        print("No fermentation data found.")
    else:
        print(f"Found {len(payload['vintages'])} vintage(s), {len(payload['varietals'])} varietal(s), {len(payload['lots'])} lot(s).")

    out_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    for name in ["SUNSET_LOGO_white.png", "favicon.ico", "sunset_cellars.css"]:
        src = PROJECT_ROOT / "assets" / name
        if src.exists():
            shutil.copy2(src, assets_dir / name)
            print(f"Copied assets/{name}")
        else:
            print(f"Warning: assets/{name} not found, skipping")

    html = make_html(payload, assets_dir)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Wrote {out_dir / 'index.html'}")

    print("Done. Upload the contents of", out_dir, "to your web server (e.g. ~/public_html/projects/).")


if __name__ == "__main__":
    main()
