# Harvest Fermentation Data — Overview

## Source

- **Google Sheet**: [Harvest Stats - Fermentation Tracking (Responses)](https://docs.google.com/spreadsheets/d/1NGHc3Q_jfsFJcWAtD34R_PjBmXzxj3hYeIQZvdt83RI/edit?gid=1688524201#gid=1688524201)
- **Live pull**: The dashboard loads from this sheet via the Google Sheets API (see README for credentials). **2025-first**: if a worksheet titled **"2025"** exists, it is used; otherwise the first worksheet is used.
- **Seasons**: 2024 and 2025 (multiple sheets/tabs may exist).

## Column Definitions


| Column | Field                   | Description                                                                                                                                                                  |
| ------ | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A      | **Timestamp**           | Form submission date/time (when the row was entered).                                                                                                                        |
| B      | **Varietal**            | Full source string: e.g. `"GRENACHE, Redgale Vineyard, Solano County"`. Parse to **variety** (e.g. Grenache) and **vineyard/source** (e.g. Redgale Vineyard, Solano County). |
| C      | **Bin**                 | Fermentation bin identifier (1, 2, 3, 4). Same varietal can have multiple bins.                                                                                              |
| D      | **Brix**                | Sugar level (°Brix). Typically starts ~25–31, drops toward 0 or slightly negative at dryness.                                                                                |
| E      | **Temperature**         | Must temperature (°F). Often 65–95°F during active fermentation.                                                                                                             |
| F      | **Notes**               | Free text: "Anything notable about this fermentation today?" — additions, sensory notes, issues (e.g. H₂S), treatments.                                                      |
| G      | **Reported by**         | Name of team member who entered the record.                                                                                                                                  |
| H      | **Date of Measurement** | Date the measurement was taken (may differ from Timestamp). **Use for fermentation timeline.**                                                                               |


## Varietals / Lots in Sample (2024)

- **GRENACHE**, Redgale Vineyard, Solano County — Bins 1, 2  
- **ZINFANDEL**, Lucchesi Vineyard, Green Valley — Bins 1, 2, 3  
- **BARBERA**, Estate, Green Valley — Bins 1, 2, 3, 4

## Data Quality Notes (for future QC)

- **Vintage**: Infer from **Date of Measurement** (year) or from sheet name; Timestamp can span two calendar years (e.g. late night 9/16 vs 9/17).
- **Missing values**: Some rows have empty or minimal notes; "Reported by" sometimes appears in the notes field (data entry inconsistency).
- **Anomalies to flag**:
  - **Brix**: Negative values are valid (post-dry); sudden large *increases* may be data entry errors or additions (e.g. juice).
  - **Temperature**: Extremes (e.g. <50°F or >100°F) worth checking.
  - **Date of Measurement**: Should be consistent with Timestamp and in harvest window (e.g. Aug–Nov for Napa/Solano).
- **Multiple entries per day**: Same varietal/bin can have several rows per day (e.g. AM/PM); all are kept for trend and notes.

## Suggested Dashboard Aggregations

- **Vintage** → filter by year (from Date of Measurement or sheet).
- **Variety / Vineyard** → filter by parsed Varietal (e.g. "Grenache" or "Zinfandel, Lucchesi").
- **Bin** → series per bin for Brix and Temperature over time.
- **Notes** → show in tooltips on hover and/or in a detail panel on click.

