from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.insights import InsightsResponse, InsightSchema, RecommendationSchema
from app.services import dataset_service
from app.analytics import analytics_service
from app.insights import insights_engine, recommendation_engine

router = APIRouter(prefix="/api/insights", tags=["Insights"])


@router.get("/{dataset_id}", response_model=InsightsResponse)
def get_insights(dataset_id: str, db: Session = Depends(get_db)):
    dataset_service.get_dataset_or_404(db, dataset_id)
    metrics = analytics_service.get_analytics(db, dataset_id)

    insights = insights_engine.generate_insights(metrics)
    recommendations = recommendation_engine.generate_recommendations(insights)

    return InsightsResponse(
        dataset_id=dataset_id,
        insights=[InsightSchema(id=i.id, metric=i.metric, insight=i.insight, severity=i.severity) for i in insights],
        recommendations=[
            RecommendationSchema(
                insight_id=r.insight_id, metric=r.metric, insight=r.insight,
                recommendation=r.recommendation, severity=r.severity, disclaimer=r.disclaimer,
            ) for r in recommendations
        ],
    )
