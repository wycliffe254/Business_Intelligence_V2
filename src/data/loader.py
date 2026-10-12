"""Data ingestion: read CSV as raw strings, standardise headers and check the file is analysable.

A file does NOT need all 32 sample columns. It is accepted when it holds a usable date column and at
least one amount column; missing columns only limit which analyses are possible (see src/data/schema.py).
"""
from __future__ import annotations
import io
from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd
from src.data.schema import SchemaReport, prepare_frame

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class LoadResult:
    success: bool
    raw_df: pd.DataFrame | None = None          # exactly as uploaded (original headers, untouched values)
    schema: SchemaReport | None = None
    missing_columns: list = field(default_factory=list)
    extra_columns: list = field(default_factory=list)
    error_message: str = ""
    headers: list = field(default_factory=list)           # headers exactly as in the uploaded file (for the matching screen)


def load_csv(file_like, column_map=None) -> LoadResult:
    try:
        if hasattr(file_like, "read"):
            data = file_like.read()
            buf = io.BytesIO(data) if isinstance(data, bytes) else io.StringIO(data)
            df = pd.read_csv(buf, dtype=str, keep_default_na=True)
        else:
            df = pd.read_csv(file_like, dtype=str, keep_default_na=True)
    except Exception as exc:  # noqa: BLE001
        return LoadResult(False, error_message=f"The uploaded file could not be read as a CSV. Details: {exc}")
    if df.empty:
        return LoadResult(False, error_message="The uploaded file contains no data rows.")
    df.columns = [str(c).strip() for c in df.columns]
    _, schema = prepare_frame(df, column_map)      # raw_df keeps the headers exactly as uploaded; the pipeline standardises once
    if not schema.viable:
        return LoadResult(False, df, schema, schema.missing_columns, schema.unrecognised_columns, schema.message, list(df.columns))
    return LoadResult(True, df, schema, schema.missing_columns, schema.unrecognised_columns, "", list(df.columns))


def sample_path(relative: str) -> Path:
    return PROJECT_ROOT / relative


def load_default_sample() -> LoadResult:
    return load_csv(str(sample_path("data/sample/kenyan_sme_bi_financial_operational_data_1800_records.csv")))
