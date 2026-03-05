"""
Data quality control for fermentation data.

This module is structured so you can add validation, anomaly detection,
and cleaning steps without changing the dashboard. The pipeline is:

  raw_df = get_raw_data(...)
  cleaned_df, qc_report = run_qc(raw_df)
  # Dashboard uses cleaned_df; qc_report can be shown or logged.
"""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class QCReport:
    """Placeholder for QC findings: missing values, anomalies, applied fixes."""

    n_rows_raw: int = 0
    n_rows_after: int = 0
    missing: dict = field(default_factory=dict)
    anomalies: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    applied_fixes: list = field(default_factory=list)


def run_qc(df: pd.DataFrame) -> tuple[pd.DataFrame, QCReport]:
    """
    Run data quality checks and optional cleaning.

    Currently:
    - Reports basic missing counts for key columns.
    - Optionally flags obvious anomalies (e.g. Brix jump, temp extremes).
    - Returns the same dataframe unchanged; add cleaning steps here later.
    """
    report = QCReport(n_rows_raw=len(df))

    # Missing values
    key_cols = ["Date of Measurement", "Varietal", "Bin", "Brix", "Temperature"]
    for col in key_cols:
        if col in df.columns:
            report.missing[col] = int(df[col].isna().sum())

    # Optional anomaly checks (placeholders)
    if "Brix" in df.columns:
        _check_brix_anomalies(df, report)
    if "Temperature" in df.columns:
        _check_temp_anomalies(df, report)

    # For now: no rows dropped or modified
    cleaned = df.copy()
    report.n_rows_after = len(cleaned)

    return cleaned, report


def _check_brix_anomalies(df: pd.DataFrame, report: QCReport) -> None:
    """Flag large day-over-day Brix increases (possible data entry or addition)."""
    # Group by varietal + bin, sort by date, diff
    for (varietal, bin_val), g in df.groupby(["Varietal", "Bin"]):
        g = g.sort_values("Date of Measurement")
        if len(g) < 2:
            continue
        brix = g["Brix"].astype(float)
        diff = brix.diff()
        # Large increase (e.g. > 3 Brix in one step) might be worth reviewing
        big_jumps = diff > 3
        if big_jumps.any():
            for idx in g.index[big_jumps]:
                report.anomalies.append(
                    {
                        "type": "brix_jump",
                        "index": idx,
                        "varietal": varietal,
                        "bin": bin_val,
                        "diff": float(diff.loc[idx]),
                    }
                )


def _check_temp_anomalies(df: pd.DataFrame, report: QCReport) -> None:
    """Flag temperatures outside typical fermentation range (e.g. < 50 or > 100 °F)."""
    temp = pd.to_numeric(df["Temperature"], errors="coerce")
    low = (temp < 50) & temp.notna()
    high = temp > 100
    for idx in df.index[low]:
        report.anomalies.append(
            {"type": "temp_low", "index": idx, "value": float(temp.loc[idx])}
        )
    for idx in df.index[high]:
        report.anomalies.append(
            {"type": "temp_high", "index": idx, "value": float(temp.loc[idx])}
        )
