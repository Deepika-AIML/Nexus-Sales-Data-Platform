"""
Shared date-parsing helper.

Real-world CSVs frequently mix date formats within a single column (e.g. a
handful of rows exported later in ISO format while the rest are M/D/YYYY).
`pandas.to_datetime` with format inference silently returns NaT for rows
that don't match the format it locked onto — that would cause Nexus to
mis-flag perfectly valid dates as invalid. `format="mixed"` (pandas >= 2.0)
parses every value independently and avoids that failure mode, at a
modest performance cost that is acceptable at the profiling/review scale
this module operates at (PySpark handles bulk parsing at full data scale).
"""
import warnings

import pandas as pd


def parse_dates_robust(series: pd.Series) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return pd.to_datetime(series, format="mixed", errors="coerce")
        except (TypeError, ValueError):
            return pd.to_datetime(series, errors="coerce")


def is_parseable_date(value: str) -> bool:
    if value is None or str(value).strip() == "":
        return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pd.to_datetime(value, format="mixed", errors="raise")
        return True
    except Exception:
        return False
