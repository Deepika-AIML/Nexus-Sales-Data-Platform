"""
Recommendation engine (spec section 27).

Takes the SAME `Insight` objects `insights_engine` produced — never
recomputes or invents new facts — and proposes a concrete next action for
each one that warrants it. Every recommendation ends with the same
validation disclaimer the spec requires: recommendations are based on the
available dataset and should be validated using business context.
"""
from dataclasses import dataclass

from app.insights.insights_engine import Insight

DISCLAIMER = "This recommendation is based on the available dataset and should be validated using business context."

_ACTION_BY_INSIGHT_ID = {
    "sales_trend_change": "Investigate what changed in the most recent period (marketing activity, seasonality, "
                           "inventory, pricing) that could explain the shift in sales.",
    "category_concentration": "Prioritize continued investment in the strongest category while reviewing "
                               "whether the weakest category needs repositioning, promotion, or retirement.",
    "region_spread": "Investigate the underperforming region's category mix and customer segments to identify "
                      "what the top region is doing differently.",
    "overall_margin": "Review pricing and discounting policy — thin margins across the dataset warrant a "
                       "cost/pricing review before scaling volume further.",
    "negative_margin_category": "Review pricing, discount levels, and cost structure for this category — "
                                 "it is generating sales but destroying profit.",
    "discount_profit_correlation": "Examine discount approval thresholds; the data suggests higher discount "
                                    "tiers are eroding profit per order.",
    "segment_leader": "Consider tailoring retention and upsell programs toward the leading segment, and "
                       "investigate why other segments contribute proportionally less.",
}


@dataclass
class Recommendation:
    insight_id: str
    metric: str
    insight: str
    recommendation: str
    severity: str
    disclaimer: str = DISCLAIMER


def generate_recommendations(insights: list[Insight]) -> list[Recommendation]:
    recs = []
    for i in insights:
        action = _ACTION_BY_INSIGHT_ID.get(i.id)
        if not action:
            continue
        recs.append(Recommendation(
            insight_id=i.id, metric=i.metric, insight=i.insight,
            recommendation=action, severity=i.severity,
        ))
    # Surface warnings first — they're the most actionable.
    recs.sort(key=lambda r: {"warning": 0, "neutral": 1, "positive": 2}.get(r.severity, 1))
    return recs
