# backend/app/schemas/calibration.py

from pydantic import BaseModel


class CalibrationBucketResponse(BaseModel):
    bucket: str
    total_predictions: int
    correct_predictions: int
    accuracy: float