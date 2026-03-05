"""
Load fermentation data from Google Sheets (live) or CSV fallback.

Data flow: Raw load → optional QC (see qc.py) → dashboard.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import COLUMNS, DATA_DIR, PREFER_2025_WORKSHEET


def parse_varietal(varietal: str) -> tuple[str, str]:
    """Split 'VARIETY, Vineyard, Region' into (variety, vineyard_source)."""
    if pd.isna(varietal) or not str(varietal).strip():
        return "", ""
    parts = str(varietal).split(",", 1)
    variety = parts[0].strip() if parts else ""
    vineyard_source = parts[1].strip() if len(parts) > 1 else ""
    return variety, vineyard_source


def load_from_csv(
    path: Optional[Path] = None,
    *,
    variety_column: str = "Varietal",
    date_column: str = "Date of Measurement",
    timestamp_column: str = "Timestamp",
) -> pd.DataFrame:
    """
    Load one CSV file (e.g. exported from one Google Sheet tab).
    Expects columns: Timestamp, Varietal, Bin, Brix, Temperature, Notes, Reported by, Date of Measurement.
    """
    path = path or (DATA_DIR / "fermentation_responses.csv")
    if not path.exists():
        raise FileNotFoundError(
            f"Data file not found: {path}. Export the sheet as CSV (File → Download → CSV) and save as {path.name} in the data/ folder."
        )

    df = pd.read_csv(path)
    # Normalize column names (strip spaces; sheet export might differ)
    df.columns = df.columns.str.strip()

    # Map Google Form header to canonical name
    notes_col = "Anything notable about this fermentation today?"
    if notes_col in df.columns and "Notes" not in df.columns:
        df = df.rename(columns={notes_col: "Notes"})

    # Ensure we have expected columns (allow extra columns)
    for c in [timestamp_column, variety_column, "Bin", "Brix", "Temperature", "Notes", "Reported by", date_column]:
        if c not in df.columns:
            raise ValueError(f"Expected column '{c}' not found. Columns: {list(df.columns)}")

    # Parse dates
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    df[timestamp_column] = pd.to_datetime(df[timestamp_column], errors="coerce")

    # Numerics
    for col in ("Bin", "Brix", "Temperature"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Add parsed variety and vineyard for filtering
    parsed = df[variety_column].map(parse_varietal)
    df["variety"] = [p[0] for p in parsed]
    df["vineyard_source"] = [p[1] for p in parsed]

    # Vintage from Date of Measurement (year)
    df["vintage"] = df[date_column].dt.year

    return df


def load_from_csv_multi(
    data_dir: Optional[Path] = None,
    pattern: str = "*.csv",
) -> pd.DataFrame:
    """
    Load all CSVs in data_dir and combine with a 'source' column (filename).
    Use one CSV per sheet/vintage if you export each tab separately.
    """
    data_dir = data_dir or DATA_DIR
    files = sorted(Path(data_dir).glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern} in {data_dir}")

    frames = []
    for f in files:
        try:
            df = load_from_csv(f)
            df["source_file"] = f.name
            frames.append(df)
        except Exception as e:
            raise RuntimeError(f"Failed to load {f}: {e}") from e

    return pd.concat(frames, ignore_index=True)


def get_raw_data(
    data_dir: Optional[Path] = None,
    single_file: Optional[Path] = None,
    use_google_sheets: bool = True,
    credentials_path: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Entry point for raw data loading.
    - If use_google_sheets is True, try loading from Google Sheets first (2025-first).
    - On failure or if use_google_sheets is False, fall back to CSV: single_file or all *.csv in data_dir.
    """
    if use_google_sheets:
        try:
            from .sheets_client import load_from_google_sheets
            return load_from_google_sheets(
                credentials_path=credentials_path,
                prefer_2025=PREFER_2025_WORKSHEET,
            )
        except Exception as e:
            print(f"Google Sheets load failed: {e}. Falling back to CSV.")
    if single_file is not None:
        return load_from_csv(single_file)
    return load_from_csv_multi(data_dir=data_dir)
