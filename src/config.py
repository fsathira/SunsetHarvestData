"""
Configuration for data sources and column mapping.
"""
from pathlib import Path

# Google Sheet ID (from the URL: /d/{SHEET_ID}/edit)
GOOGLE_SHEET_ID = "1NGHc3Q_jfsFJcWAtD34R_PjBmXzxj3hYeIQZvdt83RI"

# Default gid for "Fermentation Tracking (Responses)" — can add more for other tabs
DEFAULT_SHEET_GID = "1688524201"

# 2025-first: when loading from Sheets, use worksheet titled "2025" if present
PREFER_2025_WORKSHEET = True

# Column names as they appear in the sheet (or CSV export)
COLUMNS = [
    "Timestamp",
    "Varietal",
    "Bin",
    "Brix",
    "Temperature",
    "Notes",
    "Reported by",
    "Date of Measurement",
]

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
