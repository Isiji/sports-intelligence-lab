# backend/app/grouping/profitability_intelligence.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class IntelligenceConfig:
    min_sample_size: int = 20


def odds_band(odds: float | None) -> str:
    if odds is None:
        return "unknown"

    if odds < 1.30:
        return "below_1.30"
    if odds < 1.50:
        return "1.30_to_1.49"
    if odds < 1.80:
        return "1.50_to_1.79"
    if odds < 2.20:
        return "1.80_to_2.19"
    if odds < 3.00:
        return "2.20_to_2.99"

    return "3.00_plus"


def confidence_band(confidence: float | None) -> str:
    if confidence is None:
        return "unknown"

    if confidence < 0.60:
        return "below_0.60"
    if confidence < 0.65:
        return "0.60_to_0.64"
    if confidence < 0.70:
        return "0.65_to_0.69"
    if confidence < 0.75:
        return "0.70_to_0.74"
    if confidence < 0.80:
        return "0.75_to_0.79"
    if confidence < 0.85:
        return "0.80_to_0.84"
    if confidence < 0.90:
        return "0.85_to_0.89"

    return "0.90_plus"


def load_market_intelligence(
    session: Session,
    config: IntelligenceConfig | None = None,
) -> dict[str, dict[str, Any]]:
    cfg = config or IntelligenceConfig()

    query = text(
        """
        SELECT
            market,
            COUNT(*) AS sample_size,
            AVG(CASE WHEN profit > 0 THEN 1.0 ELSE 0.0 END) AS hit_rate,
            SUM(profit) / NULLIF(SUM(stake), 0) AS roi,
            AVG(odds) AS avg_odds,
            AVG(confidence) AS avg_confidence,
            AVG(value_score) AS avg_edge
        FROM historical_backtest_bets
        WHERE profit IS NOT NULL
          AND stake IS NOT NULL
          AND odds IS NOT NULL
          AND confidence IS NOT NULL
        GROUP BY market
        HAVING COUNT(*) >= :min_sample_size
        """
    )

    rows = session.execute(
        query,
        {"min_sample_size": cfg.min_sample_size},
    ).fetchall()

    return {
        row._mapping["market"]: dict(row._mapping)
        for row in rows
    }


def load_league_market_intelligence(
    session: Session,
    config: IntelligenceConfig | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    cfg = config or IntelligenceConfig()

    query = text(
        """
        SELECT
            league,
            market,
            COUNT(*) AS sample_size,
            AVG(CASE WHEN profit > 0 THEN 1.0 ELSE 0.0 END) AS hit_rate,
            SUM(profit) / NULLIF(SUM(stake), 0) AS roi,
            AVG(odds) AS avg_odds,
            AVG(confidence) AS avg_confidence,
            AVG(value_score) AS avg_edge
        FROM historical_backtest_bets
        WHERE league IS NOT NULL
          AND profit IS NOT NULL
          AND stake IS NOT NULL
          AND odds IS NOT NULL
          AND confidence IS NOT NULL
        GROUP BY league, market
        HAVING COUNT(*) >= :min_sample_size
        """
    )

    rows = session.execute(
        query,
        {"min_sample_size": cfg.min_sample_size},
    ).fetchall()

    output: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        data = dict(row._mapping)
        output[(data["league"], data["market"])] = data

    return output


def load_odds_band_intelligence(
    session: Session,
    config: IntelligenceConfig | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    cfg = config or IntelligenceConfig()

    query = text(
        """
        SELECT
            market,
            CASE
                WHEN odds < 1.30 THEN 'below_1.30'
                WHEN odds >= 1.30 AND odds < 1.50 THEN '1.30_to_1.49'
                WHEN odds >= 1.50 AND odds < 1.80 THEN '1.50_to_1.79'
                WHEN odds >= 1.80 AND odds < 2.20 THEN '1.80_to_2.19'
                WHEN odds >= 2.20 AND odds < 3.00 THEN '2.20_to_2.99'
                WHEN odds >= 3.00 THEN '3.00_plus'
                ELSE 'unknown'
            END AS odds_band,
            COUNT(*) AS sample_size,
            AVG(CASE WHEN profit > 0 THEN 1.0 ELSE 0.0 END) AS hit_rate,
            SUM(profit) / NULLIF(SUM(stake), 0) AS roi
        FROM historical_backtest_bets
        WHERE profit IS NOT NULL
          AND stake IS NOT NULL
          AND odds IS NOT NULL
        GROUP BY market, odds_band
        HAVING COUNT(*) >= :min_sample_size
        """
    )

    rows = session.execute(
        query,
        {"min_sample_size": cfg.min_sample_size},
    ).fetchall()

    output: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        data = dict(row._mapping)
        output[(data["market"], data["odds_band"])] = data

    return output


def load_confidence_band_intelligence(
    session: Session,
    config: IntelligenceConfig | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    cfg = config or IntelligenceConfig()

    query = text(
        """
        SELECT
            market,
            CASE
                WHEN confidence < 0.60 THEN 'below_0.60'
                WHEN confidence >= 0.60 AND confidence < 0.65 THEN '0.60_to_0.64'
                WHEN confidence >= 0.65 AND confidence < 0.70 THEN '0.65_to_0.69'
                WHEN confidence >= 0.70 AND confidence < 0.75 THEN '0.70_to_0.74'
                WHEN confidence >= 0.75 AND confidence < 0.80 THEN '0.75_to_0.79'
                WHEN confidence >= 0.80 AND confidence < 0.85 THEN '0.80_to_0.84'
                WHEN confidence >= 0.85 AND confidence < 0.90 THEN '0.85_to_0.89'
                WHEN confidence >= 0.90 THEN '0.90_plus'
                ELSE 'unknown'
            END AS confidence_band,
            COUNT(*) AS sample_size,
            AVG(CASE WHEN profit > 0 THEN 1.0 ELSE 0.0 END) AS hit_rate,
            SUM(profit) / NULLIF(SUM(stake), 0) AS roi
        FROM historical_backtest_bets
        WHERE profit IS NOT NULL
          AND stake IS NOT NULL
          AND confidence IS NOT NULL
        GROUP BY market, confidence_band
        HAVING COUNT(*) >= :min_sample_size
        """
    )

    rows = session.execute(
        query,
        {"min_sample_size": cfg.min_sample_size},
    ).fetchall()

    output: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        data = dict(row._mapping)
        output[(data["market"], data["confidence_band"])] = data

    return output