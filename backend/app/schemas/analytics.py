from typing import Any, Dict

from pydantic import BaseModel


class AnalyticsResponse(BaseModel):
    dataset_id: str
    metrics: Dict[str, Any]
