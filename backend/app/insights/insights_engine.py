"""
Insights engine (spec section 26).

Every insight here is derived from a number that `analytics_service`
actually computed in this same request — nothing is invented, and there
is no machine-learning forecasting (the spec is explicit: don't pretend to
forecast unless it's actually implemented and validated; Nexus V1 does not
implement forecasting, so none is claimed).

Each insight is returned as a `{metric, insight}` pair;
`recommendation_engine.py` takes the SAME insight list and proposes actions,
keeping "what we observed" and "what we suggest doing about it" as clearly
separate steps.

Currency is displayed in Indian Rupees (₹).
"""

from dataclasses import dataclass


@dataclass
class Insight:
    id: str
    metric: str        # the raw calculated fact
    insight: str       # what it means
    severity: str      # "positive" | "neutral" | "warning"


def generate_insights(analytics: dict) -> list[Insight]:
    insights: list[Insight] = []

    insights += _trend_insight(analytics.get("sales_trend", {}))
    insights += _category_insight(analytics.get("sales_by_category", {}))
    insights += _region_insight(analytics.get("sales_by_region", {}))
    insights += _margin_insight(analytics.get("profitability", {}))
    insights += _category_profit_insight(
        analytics.get("category_profitability", {})
    )
    insights += _discount_profit_insight(
        analytics.get("discount_analysis", {})
    )
    insights += _segment_insight(
        analytics.get("segment_analysis", {})
    )

    return insights


def _trend_insight(trend: dict) -> list[Insight]:
    if not trend.get("available") or len(trend.get("points", [])) < 2:
        return []

    points = trend["points"]
    last, prior = points[-1], points[-2]

    if prior["sales"] == 0:
        return []

    change_pct = round(
        100 * (last["sales"] - prior["sales"]) / prior["sales"],
        1,
    )

    direction = "declined" if change_pct < 0 else "grew"

    severity = (
        "warning"
        if change_pct < -10
        else ("positive" if change_pct > 10 else "neutral")
    )

    return [
        Insight(
            id="sales_trend_change",
            metric=(
                f"Sales {direction} {abs(change_pct)}% "
                f"from {prior['month']}/{prior['year']} "
                f"to {last['month']}/{last['year']} "
                f"(₹{prior['sales']:,.0f} -> ₹{last['sales']:,.0f})."
            ),
            insight=(
                f"The most recent period shows a "
                f"{'decline' if change_pct < 0 else 'increase'} "
                f"in total sales compared to the prior period."
            ),
            severity=severity,
        )
    ]


def _category_insight(cat: dict) -> list[Insight]:
    if not cat.get("available") or len(cat.get("categories", [])) < 2:
        return []

    cats = sorted(
        cat["categories"],
        key=lambda c: c["sales"],
        reverse=True,
    )

    top, bottom = cats[0], cats[-1]

    total = sum(c["sales"] for c in cats)

    share = round(
        100 * top["sales"] / total,
        1,
    ) if total else 0

    return [
        Insight(
            id="category_concentration",
            metric=(
                f"'{top['category']}' generated "
                f"₹{top['sales']:,.0f} in sales "
                f"({share}% of total), while "
                f"'{bottom['category']}' generated only "
                f"₹{bottom['sales']:,.0f}."
            ),
            insight=(
                f"Sales are concentrated in '{top['category']}'; "
                f"'{bottom['category']}' is the weakest-performing category."
            ),
            severity="neutral",
        )
    ]


def _region_insight(reg: dict) -> list[Insight]:
    if not reg.get("available") or len(reg.get("regions", [])) < 2:
        return []

    regions = sorted(
        reg["regions"],
        key=lambda r: r["sales"],
        reverse=True,
    )

    top, bottom = regions[0], regions[-1]

    return [
        Insight(
            id="region_spread",
            metric=(
                f"'{top['region']}' is the top-performing region "
                f"(₹{top['sales']:,.0f}); "
                f"'{bottom['region']}' is the lowest "
                f"(₹{bottom['sales']:,.0f})."
            ),
            insight=(
                f"There is a meaningful performance gap between "
                f"'{top['region']}' and '{bottom['region']}'."
            ),
            severity="neutral",
        )
    ]


def _margin_insight(profit: dict) -> list[Insight]:
    if (
        not profit.get("available")
        or profit.get("profit_margin_pct") is None
    ):
        return []

    margin = profit["profit_margin_pct"]

    severity = (
        "warning"
        if margin < 5
        else ("positive" if margin > 15 else "neutral")
    )

    return [
        Insight(
            id="overall_margin",
            metric=(
                f"Overall profit margin is {margin}% "
                f"(₹{profit['total_profit']:,.0f} profit)."
            ),
            insight=(
                "Margins are thin across the dataset."
                if margin < 5
                else (
                    "Margins are healthy across the dataset."
                    if margin > 15
                    else "Margins are moderate."
                )
            ),
            severity=severity,
        )
    ]


def _category_profit_insight(cat_profit: dict) -> list[Insight]:
    if not cat_profit.get("available"):
        return []

    negative = [
        c
        for c in cat_profit["categories"]
        if c["profit"] < 0
    ]

    if not negative:
        return []

    worst = min(
        negative,
        key=lambda c: c["profit"],
    )

    return [
        Insight(
            id="negative_margin_category",
            metric=(
                f"'{worst['category']}' has a negative total profit "
                f"of ₹{worst['profit']:,.0f} "
                f"on ₹{worst['sales']:,.0f} in sales."
            ),
            insight=(
                f"'{worst['category']}' is selling but losing "
                f"money overall."
            ),
            severity="warning",
        )
    ]


def _discount_profit_insight(disc: dict) -> list[Insight]:
    if not disc.get("available"):
        return []

    bands = [
        b
        for b in disc["bands"]
        if b["avg_profit"] is not None
    ]

    if len(bands) < 2:
        return []

    no_discount = next(
        (
            b
            for b in bands
            if b["discount_band"] == "No discount"
        ),
        None,
    )

    high_discount = next(
        (
            b
            for b in bands
            if b["discount_band"] == "40%+"
        ),
        None,
    )

    if (
        no_discount
        and high_discount
        and no_discount["avg_profit"]
        > high_discount["avg_profit"]
    ):
        return [
            Insight(
                id="discount_profit_correlation",
                metric=(
                    f"Average profit per line is "
                    f"₹{no_discount['avg_profit']:,.2f} "
                    f"with no discount vs. "
                    f"₹{high_discount['avg_profit']:,.2f} "
                    f"at 40%+ discount."
                ),
                insight=(
                    "Higher discount bands are associated with "
                    "lower average profit per order line."
                ),
                severity="warning",
            )
        ]

    return []


def _segment_insight(seg: dict) -> list[Insight]:
    if not seg.get("available") or len(seg.get("segments", [])) < 2:
        return []

    segments = sorted(
        seg["segments"],
        key=lambda s: s["sales"],
        reverse=True,
    )

    top = segments[0]

    total = sum(
        s["sales"]
        for s in segments
    )

    share = round(
        100 * top["sales"] / total,
        1,
    ) if total else 0

    return [
        Insight(
            id="segment_leader",
            metric=(
                f"The '{top['segment']}' segment contributes "
                f"₹{top['sales']:,.0f} "
                f"({share}% of total sales) "
                f"across {top['orders']} orders."
            ),
            insight=(
                f"'{top['segment']}' is the leading customer "
                f"segment by revenue."
            ),
            severity="neutral",
        )
    ]