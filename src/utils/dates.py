"""Date parsing for the dataset's mixed formats (ISO, DD-MM-YYYY, DD/MM or MM/DD).

ASSUMPTION: where both components are <= 12 the order is genuinely ambiguous;
we default to day-first (Kenyan/international convention) and flag the row.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
import pandas as pd

_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T].*)?$")
_SEP_RE = re.compile(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$")


@dataclass
class DateParseResult:
    parsed: pd.Timestamp | None
    is_valid: bool
    is_ambiguous: bool
    raw_value: str


def parse_single_date(value) -> DateParseResult:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return DateParseResult(None, False, False, str(value))
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "nat"}:
        return DateParseResult(None, False, False, text)
    m = _ISO_RE.match(text)
    if m:
        try:
            return DateParseResult(pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3))), True, False, text)
        except ValueError:
            return DateParseResult(None, False, False, text)
    m = _SEP_RE.match(text)
    if m:
        a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ambiguous = False
        if a > 12 and 1 <= b <= 12:
            day, month = a, b
        elif b > 12 and 1 <= a <= 12:
            day, month = b, a
        elif 1 <= a <= 12 and 1 <= b <= 12:
            day, month, ambiguous = a, b, True
        else:
            return DateParseResult(None, False, False, text)
        try:
            return DateParseResult(pd.Timestamp(year, month, day), True, ambiguous, text)
        except ValueError:
            return DateParseResult(None, False, False, text)
    return DateParseResult(None, False, False, text)


def parse_date_series(series: pd.Series) -> pd.DataFrame:
    results = [parse_single_date(v) for v in series.tolist()]
    return pd.DataFrame({
        "parsed_date": pd.to_datetime([r.parsed for r in results]),
        "is_valid_date": [r.is_valid for r in results],
        "is_ambiguous_date": [r.is_ambiguous for r in results],
    }, index=series.index)
