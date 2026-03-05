"""
Live data from Google Sheets. Prefer 2025 worksheet when present.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import (
    DATA_DIR,
    GOOGLE_SHEET_ID,
    PROJECT_ROOT,
)


# Canonical column names (2025 layout matches 2024; add mappings here if 2025 differs)
NOTES_HEADER_ALIASES = [
    "Anything notable about this fermentation today?",
    "Notes",
]
REQUIRED_COLUMNS = [
    "Timestamp",
    "Varietal",
    "Bin",
    "Brix",
    "Temperature",
    "Reported by",
    "Date of Measurement",
]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    for alias in NOTES_HEADER_ALIASES:
        if alias in df.columns and "Notes" not in df.columns:
            df = df.rename(columns={alias: "Notes"})
            break
    if "Notes" not in df.columns:
        df["Notes"] = ""
    return df


def load_from_google_sheets(
    sheet_id: str = GOOGLE_SHEET_ID,
    credentials_path: Optional[Path] = None,
    worksheet_name: Optional[str] = None,
    *,
    prefer_2025: bool = True,
) -> pd.DataFrame:
    """
    Load fermentation data from Google Sheets.
    - If worksheet_name is set, use that sheet.
    - Else if prefer_2025 and a worksheet titled "2025" exists, use it; else use the first worksheet.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise ImportError(
            "Google Sheets live pull requires: pip install gspread google-auth"
        )

    creds_path = credentials_path or (PROJECT_ROOT / "data" / "google_credentials.json")
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Credentials not found at {creds_path}. "
            "Create a Google Cloud service account, download JSON key, save as data/google_credentials.json, "
            "and share the Google Sheet with the service account email."
        )

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
    gc = gspread.authorize(creds)
    workbook = gc.open_by_key(sheet_id)

    if worksheet_name:
        ws = workbook.worksheet(worksheet_name)
    elif prefer_2025:
        try:
            ws = workbook.worksheet("2025")
        except gspread.WorksheetNotFound:
            ws = workbook.sheet1
    else:
        ws = workbook.sheet1

    rows = ws.get_all_records()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = _normalize_columns(df)

    for c in REQUIRED_COLUMNS:
        if c not in df.columns:
            raise ValueError(
                f"Sheet missing expected column '{c}'. Found: {list(df.columns)}"
            )

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df["Date of Measurement"] = pd.to_datetime(df["Date of Measurement"], errors="coerce")
    for col in ("Bin", "Brix", "Temperature"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parsed variety / vineyard (same as load_data)
    def parse_varietal(v):
        if pd.isna(v) or not str(v).strip():
            return "", ""
        parts = str(v).strip().split(",", 1)
        return (parts[0].strip(), parts[1].strip() if len(parts) > 1 else "")

    parsed = df["Varietal"].map(parse_varietal)
    df["variety"] = [p[0] for p in parsed]
    df["vineyard_source"] = [p[1] for p in parsed]
    df["vintage"] = df["Date of Measurement"].dt.year
    df["source_file"] = "Google Sheets (live)"

    return df
