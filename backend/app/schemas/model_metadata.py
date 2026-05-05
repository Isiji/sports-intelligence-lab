# backend/app/schemas/model_metadata.py

from pydantic import BaseModel


class ActiveModelMetadataResponse(BaseModel):
    market: str
    selected_model_name: str
    selected_accuracy: float
    feature_columns: list[str]