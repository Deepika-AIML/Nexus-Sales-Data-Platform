from typing import List

from pydantic import BaseModel


class InsightSchema(BaseModel):
    id: str
    metric: str
    insight: str
    severity: str


class RecommendationSchema(BaseModel):
    insight_id: str
    metric: str
    insight: str
    recommendation: str
    severity: str
    disclaimer: str


class InsightsResponse(BaseModel):
    dataset_id: str
    insights: List[InsightSchema]
    recommendations: List[RecommendationSchema]
