from sqlalchemy import text
from sqlalchemy.orm import Session

from app.odds.market_normalizer import normalize_market_and_selection


def _get_columns(session: Session, table_name: str) -> set[str]:
    rows = session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = :table_name
            """
        ),
        {"table_name": table_name},
    ).fetchall()

    return {row[0] for row in rows}


def scan_market_availability(session: Session, limit: int = 50000) -> dict:
    columns = _get_columns(session, "match_odds")

    market_col = "market" if "market" in columns else "market_name"
    selection_col = (
        "selection"
        if "selection" in columns
        else "selection_name"
        if "selection_name" in columns
        else "label"
        if "label" in columns
        else "name"
    )

    odds_col = (
        "odds"
        if "odds" in columns
        else "odd"
        if "odd" in columns
        else "value"
        if "value" in columns
        else None
    )

    if not market_col or not selection_col:
        return {
            "status": "failed",
            "reason": "Could not detect market/selection columns in match_odds",
            "columns_found": sorted(columns),
        }

    query = f"""
        SELECT
            o.{market_col} AS market_name,
            o.{selection_col} AS selection_name,
            COUNT(*) AS rows_count
        FROM match_odds o
        GROUP BY o.{market_col}, o.{selection_col}
        ORDER BY rows_count DESC
        LIMIT :limit
    """

    rows = session.execute(text(query), {"limit": limit}).mappings().all()

    canonical_counts: dict[str, int] = {}
    unmatched: list[dict] = []

    for row in rows:
        market_name = row["market_name"]
        selection_name = row["selection_name"]
        count = int(row["rows_count"])

        result = normalize_market_and_selection(
            market_name=market_name,
            selection_name=selection_name,
        )

        if result.canonical_market:
            canonical_counts[result.canonical_market] = (
                canonical_counts.get(result.canonical_market, 0) + count
            )
        else:
            unmatched.append(
                {
                    "market_name": market_name,
                    "selection_name": selection_name,
                    "rows": count,
                    "reason": result.reason,
                }
            )

    return {
        "status": "ok",
        "detected_columns": {
            "market_col": market_col,
            "selection_col": selection_col,
            "odds_col": odds_col,
        },
        "matched_markets": dict(
            sorted(canonical_counts.items(), key=lambda item: item[1], reverse=True)
        ),
        "unmatched_examples": unmatched[:50],
    }