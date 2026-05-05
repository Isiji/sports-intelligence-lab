# backend/app/ml/registry.py

from pathlib import Path
import json
from typing import Any


def save_model_metadata(
    metadata_path: Path,
    market: str,
    selected_model_name: str,
    selected_accuracy: float,
    feature_columns: list[str],
) -> None:
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = {
        "market": market,
        "selected_model_name": selected_model_name,
        "selected_accuracy": round(float(selected_accuracy), 4),
        "feature_columns": feature_columns,
    }

    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


def load_model_metadata(metadata_path: Path) -> dict[str, Any]:
    if not metadata_path.exists():
        return {
            "selected_model_name": "unknown_model",
            "selected_accuracy": 0.0,
            "feature_columns": [],
        }

    return json.loads(metadata_path.read_text(encoding="utf-8"))