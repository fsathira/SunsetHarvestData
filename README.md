# Sunset Cellars — Harvest Fermentation Dashboard

Dashboard and data analysis of Sunset Cellars' harvest daily fermentation statistics.

Fermentation tracking for **Sunset Cellars** (Suisun Valley, Fairfield, CA). Data is pulled **live from Google Sheets** (2025-first layout). For each fermentation (vintage + varietal + bin), the dashboard shows **Brix** and **must temperature** by **day** (days since first measurement), stacked with **Fairfield, CA weather** (air temperature and rain) over the same period. Team notes appear on hover and on click.

- **Data source**: [Harvest Stats - Fermentation Tracking (Responses)](https://docs.google.com/spreadsheets/d/1NGHc3Q_jfsFJcWAtD34R_PjBmXzxj3hYeIQZvdt83RI/edit?gid=1688524201)
- **Weather**: Open-Meteo Historical API (Fairfield coordinates), no API key required.

## Data overview

- **Columns**: Timestamp, Varietal, Bin, Brix, Temperature, Notes, Reported by, Date of Measurement.
- **2025-first**: If the workbook has a worksheet titled **"2025"**, it is used when loading from Google Sheets; otherwise the first sheet is used.
- **Vintage** is inferred from *Date of Measurement* (year). **Day** = days since the first measurement for that fermentation (varietal + bin + vintage).
- See [DATA_OVERVIEW.md](DATA_OVERVIEW.md) for column definitions and data-quality notes.

## Setup

1. **Python 3.10+** and a virtualenv (recommended):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Live data from Google Sheets (recommended)**  
   - In [Google Cloud Console](https://console.cloud.google.com/): create a project → enable **Google Sheets API** and **Google Drive API** → **APIs & Services → Credentials** → **Create credentials → Service account**. Create a key (JSON) and download it.
   - Save the JSON key as **`data/google_credentials.json`** (path is in `.gitignore`; do not commit it).
   - Share your Google Sheet with the **service account email** (e.g. `xxx@yyy.iam.gserviceaccount.com`) with **Viewer** access.
   - The app will load from the sheet on startup; if a worksheet named **"2025"** exists, that tab is used first.

3. **CSV fallback (no credentials)**  
   If `data/google_credentials.json` is missing or Sheets fails, the app falls back to CSV: put one or more `*.csv` files in `data/` (e.g. export from the sheet). A sample file `data/fermentation_responses_sample.csv` is included so you can run the app without Sheets.

## Run the dashboard

From the project root:

```bash
python -m src.dashboard
```

Then open **http://127.0.0.1:8050**.

- **Vintage**, **Varietal / Vineyard**, and **Bin** select one fermentation.
- **Stacked chart**: (1) Brix vs day, (2) Must temperature vs day, (3) Fairfield weather (air temp + rain) vs day. All share the same **day** axis (day 0 = first measurement for that lot).
- **Hover** over a point for date, value, reporter, and notes snippet.
- **Click** a point to show the full note in the panel below.

To force CSV-only (no Google Sheets), run with an explicit file or set `use_google_sheets=False` in code.

## Data pipeline and QC

1. **Load** — `get_raw_data(use_google_sheets=True)` tries Google Sheets (2025-first), then CSV in `data/`.
2. **QC** — `run_qc(raw_df)` in `src/qc.py` returns `(cleaned_df, qc_report)`. Add validation or cleaning there without changing the dashboard.
3. **Dashboard** — Uses the cleaned dataframe; adds **day** per fermentation and fetches Fairfield weather for the date range of the selected lot.

## Project layout

```
HarvestData/
├── README.md
├── DATA_OVERVIEW.md
├── requirements.txt
├── data/
│   ├── google_credentials.json   # (you add this for live Sheets)
│   └── fermentation_responses_sample.csv
├── assets/
│   └── sunset_cellars.css
└── src/
    ├── config.py        # Sheet ID, 2025-first flag
    ├── load_data.py     # get_raw_data() → Sheets or CSV
    ├── sheets_client.py # Live Google Sheets (2025-first)
    ├── weather.py       # Fairfield weather (Open-Meteo)
    ├── qc.py            # QC stub
    └── dashboard.py     # Stacked Brix / temp / weather by day
```

## Styling

The dashboard uses a **Sunset Cellars**–inspired palette (burgundy, cream, earth tones) and typography (Cormorant Garamond, Lato) to align with [sunsetcellars.com](https://sunsetcellars.com).
