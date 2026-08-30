"""
Nexus Column Mapping Engine
============================
Maps arbitrary source CSV columns onto the canonical Nexus sales schema.

This is intentionally NOT exact-string-matching. Confidence is a weighted
combination of five independent signals:

  1. Normalized name equality / synonym membership   (up to 55 pts)
  2. Fuzzy name similarity against synonyms           (up to 20 pts)
  3. Keyword token overlap                            (up to 10 pts)
  4. Datatype compatibility (sample values vs field)  (up to 10 pts)
  5. Value-pattern strength (regex-level signal)       (up to  5 pts)

Total is capped at 100. Classification bands (per product spec):
    >= 85           -> auto-mapped
    60 <= x < 85     -> suggested, requires review
    < 60            -> uncertain / unmapped

The engine is pure Python + pandas — no FastAPI/Spark dependency — so it can
be unit tested in isolation and reused by both the interactive review step
and any batch tooling.
"""
from __future__ import annotations

import re
import difflib
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from app.data_engine.canonical_schema import CANONICAL_SCHEMA, FieldType, ALL_FIELDS
from app.data_engine.synonyms import SYNONYMS, KEYWORDS

AUTO_MAP_THRESHOLD = 85
REVIEW_THRESHOLD = 60


def normalize_column_name(name: str) -> str:
    """Lowercase, strip, collapse punctuation/whitespace to single underscores."""
    s = str(name).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


_DATE_RE = re.compile(
    r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$|^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$"
)
_NUMERIC_RE = re.compile(r"^-?\$?\d[\d,]*\.?\d*%?$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_POSTAL_RE = re.compile(r"^\d{4,10}(-\d{3,4})?$")


def _sample_values(series: pd.Series, n: int = 25) -> list:
    non_null = series.dropna()
    if non_null.empty:
        return []
    sample = non_null.astype(str).str.strip()
    sample = sample[sample != ""]
    return sample.head(n).tolist()


def _datatype_signal(samples: list, field_type: FieldType) -> float:
    """Returns 0..1 fraction of samples consistent with the expected type."""
    if not samples:
        return 0.0
    hits = 0
    for v in samples:
        v = v.strip()
        if field_type == FieldType.DATE:
            ok = bool(_DATE_RE.match(v)) or _try_parse_date(v)
        elif field_type in (FieldType.CURRENCY, FieldType.SIGNED_CURRENCY,
                             FieldType.QUANTITY, FieldType.RATE):
            cleaned = v.replace("$", "").replace(",", "").replace("%", "")
            ok = _is_number(cleaned)
        elif field_type == FieldType.POSTAL:
            ok = bool(_POSTAL_RE.match(v))
        elif field_type == FieldType.IDENTIFIER:
            ok = bool(_ID_RE.match(v)) and len(v) <= 40
        else:  # TEXT / CATEGORY — basically anything non-numeric-looking is fine
            ok = True
        hits += 1 if ok else 0
    return hits / len(samples)


def _is_number(v: str) -> bool:
    try:
        float(v)
        return True
    except ValueError:
        return False


def _try_parse_date(v: str) -> bool:
    from app.data_engine.date_utils import is_parseable_date
    return is_parseable_date(v)


def _pattern_signal(samples: list, field_type: FieldType) -> float:
    """A stricter secondary check for a 'bonus' point beyond basic dtype fit."""
    if not samples:
        return 0.0
    if field_type == FieldType.IDENTIFIER:
        # IDs tend to have consistent length/pattern (e.g. CA-2016-152156)
        lengths = {len(v) for v in samples}
        return 1.0 if len(lengths) <= 3 else 0.3
    if field_type in (FieldType.CURRENCY, FieldType.SIGNED_CURRENCY):
        decimals = sum(1 for v in samples if "." in v)
        return decimals / len(samples)
    if field_type == FieldType.RATE:
        try:
            vals = [float(v.replace("%", "")) for v in samples]
            in_range = sum(1 for x in vals if 0 <= x <= 100)
            return in_range / len(vals)
        except ValueError:
            return 0.0
    return 0.5


@dataclass
class FieldCandidate:
    canonical_field: str
    confidence: float
    signals: dict = field(default_factory=dict)


@dataclass
class ColumnMappingSuggestion:
    source_column: str
    normalized: str
    best_field: Optional[str]
    confidence: float
    status: str  # "auto_mapped" | "review" | "unmapped"
    candidates: list  # list[FieldCandidate], sorted desc by confidence
    sample_values: list


@dataclass
class MappingResult:
    suggestions: list  # list[ColumnMappingSuggestion]
    conflicts: list    # list of dicts describing canonical fields with >1 confident source


def _name_signal(norm_col: str, canonical_field: str) -> tuple[float, float]:
    """Returns (exact_synonym_score[0..55], fuzzy_score[0..20])."""
    synonyms = SYNONYMS.get(canonical_field, [canonical_field])
    if norm_col in synonyms or norm_col == canonical_field:
        return 55.0, 20.0
    best_ratio = max(
        (difflib.SequenceMatcher(None, norm_col, syn).ratio() for syn in synonyms),
        default=0.0,
    )
    # Also compare directly to the canonical field name itself
    best_ratio = max(best_ratio, difflib.SequenceMatcher(None, norm_col, canonical_field).ratio())
    exact = 55.0 if best_ratio >= 0.97 else 0.0
    fuzzy = round(20.0 * best_ratio, 2) if exact == 0.0 else 0.0
    return exact, fuzzy


def _keyword_signal(norm_col: str, canonical_field: str) -> float:
    tokens = set(norm_col.split("_"))
    kw = KEYWORDS.get(canonical_field, set())
    if not tokens or not kw:
        return 0.0
    overlap = tokens & kw
    return round(10.0 * (len(overlap) / max(len(kw), 1)), 2)


def score_column_against_field(norm_col: str, samples: list, canonical_field: str) -> FieldCandidate:
    meta = CANONICAL_SCHEMA[canonical_field]
    exact, fuzzy = _name_signal(norm_col, canonical_field)
    keyword = 0.0 if exact > 0 else _keyword_signal(norm_col, canonical_field)
    dtype_frac = _datatype_signal(samples, meta["type"])
    dtype_score = round(10.0 * dtype_frac, 2)
    pattern_frac = _pattern_signal(samples, meta["type"]) if dtype_frac > 0.5 else 0.0
    pattern_score = round(5.0 * pattern_frac, 2)

    total = min(100.0, exact + fuzzy + keyword + dtype_score + pattern_score)
    return FieldCandidate(
        canonical_field=canonical_field,
        confidence=round(total, 1),
        signals={
            "name_exact": exact,
            "name_fuzzy": fuzzy,
            "keyword_overlap": keyword,
            "datatype_fit": dtype_score,
            "pattern_strength": pattern_score,
        },
    )


def suggest_mapping(df: pd.DataFrame) -> MappingResult:
    """
    Produce a ranked mapping suggestion for every source column in `df`.
    Does NOT mutate df. Pure suggestion — the caller (API layer) is
    responsible for persisting the user's confirmed mapping.
    """
    suggestions: list[ColumnMappingSuggestion] = []

    for col in df.columns:
        norm = normalize_column_name(col)
        samples = _sample_values(df[col])
        candidates = [
            score_column_against_field(norm, samples, cf) for cf in ALL_FIELDS
        ]
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        top = candidates[0] if candidates else None

        if top and top.confidence >= AUTO_MAP_THRESHOLD:
            status = "auto_mapped"
            best_field = top.canonical_field
        elif top and top.confidence >= REVIEW_THRESHOLD:
            status = "review"
            best_field = top.canonical_field
        else:
            status = "unmapped"
            best_field = None

        suggestions.append(
            ColumnMappingSuggestion(
                source_column=col,
                normalized=norm,
                best_field=best_field,
                confidence=top.confidence if top else 0.0,
                status=status,
                candidates=candidates[:5],
                sample_values=samples[:5],
            )
        )

    conflicts = _detect_conflicts(suggestions)
    return MappingResult(suggestions=suggestions, conflicts=conflicts)


def _detect_conflicts(suggestions: list[ColumnMappingSuggestion]) -> list[dict]:
    """Flag canonical fields that more than one source column confidently claims."""
    by_field: dict[str, list[str]] = {}
    for s in suggestions:
        if s.best_field and s.status in ("auto_mapped", "review"):
            by_field.setdefault(s.best_field, []).append(s.source_column)

    conflicts = []
    for canonical_field, cols in by_field.items():
        if len(cols) > 1:
            conflicts.append({
                "canonical_field": canonical_field,
                "competing_source_columns": cols,
                "message": (
                    f"Multiple source columns ({', '.join(cols)}) were matched to "
                    f"'{canonical_field}'. Please confirm which one is correct."
                ),
            })
    return conflicts


def apply_confirmed_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """
    mapping: {source_column: canonical_field}. Unmapped source columns are
    dropped from the canonical frame (they remain available in the raw/bronze
    copy — this function only produces the canonical-shaped view used for
    quality analysis and downstream cleaning).
    """
    inverse = {src: canon for src, canon in mapping.items() if canon}
    subset = df[list(inverse.keys())].copy()
    subset.rename(columns=inverse, inplace=True)
    return subset


def missing_required_fields(mapping: dict[str, str]) -> list[str]:
    from app.data_engine.canonical_schema import CORE_FIELDS
    mapped_canonical = set(v for v in mapping.values() if v)
    return [f for f in CORE_FIELDS if f not in mapped_canonical]


def missing_optional_fields(mapping: dict[str, str]) -> list[str]:
    from app.data_engine.canonical_schema import OPTIONAL_FIELDS, RECOMMENDED_FIELDS
    mapped_canonical = set(v for v in mapping.values() if v)
    return [f for f in (RECOMMENDED_FIELDS + OPTIONAL_FIELDS) if f not in mapped_canonical]
