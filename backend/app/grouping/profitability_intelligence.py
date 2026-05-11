# backend/app/grouping/profitability_intelligence.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class IntelligenceConfig:
    min_sample_size: int = 20

    historical_weight: float = 0.70
    live_weight: float = 0.30

    use_live_intelligence: bool = True


LIVE_RUN_TAG = "live_predictions"


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


# =====================================================
# HYBRID HELPERS
# =====================================================


def _merge_weighted_metrics(
    historical: dict[str, Any] | None,
    live: dict[str, Any] | None,
    historical_weight: float,
    live_weight: float,
) -> dict[str, Any]:
    if historical is None and live is None:
        return {}

    if historical is None:
        return dict(live)

    if live is None:
        return dict(historical)

    hist_sample = int(historical.get("sample_size") or 0)
    live_sample = int(live.get("sample_size") or 0)

    total_sample = hist_sample + live_sample

    dynamic_live_weight = live_weight

    # =====================================================
    # AUTO-BOOST LIVE WEIGHT AS LIVE DATA GROWS
    # =====================================================

    if live_sample >= 100:
        dynamic_live_weight = max(dynamic_live_weight, 0.45)

    if live_sample >= 250:
        dynamic_live_weight = max(dynamic_live_weight, 0.60)

    dynamic_hist_weight = max(
        1.0 - dynamic_live_weight,
        0.0,
    )

    def weighted(metric: str) -> float:
        hist_value = float(historical.get(metric) or 0.0)
        live_value = float(live.get(metric) or 0.0)

        return round(
            (
                hist_value * dynamic_hist_weight
                + live_value * dynamic_live_weight
            ),
            6,
        )

    merged = dict(historical)

    merged["sample_size"] = total_sample

    merged["historical_sample_size"] = hist_sample
    merged["live_sample_size"] = live_sample

    merged["historical_weight"] = dynamic_hist_weight
    merged["live_weight"] = dynamic_live_weight

    for metric in {
        "hit_rate",
        "roi",
        "avg_odds",
        "avg_confidence",
        "avg_edge",
    }:
        merged[metric] = weighted(metric)

    return merged


def _load_query_as_dict(
    session: Session,
    query: str,
    params: dict[str, Any],
    key_builder,
) -> dict:
    rows = session.execute(
        text(query),
        params,
    ).fetchall()

    output = {}

    for row in rows:
        data = dict(row._mapping)
        output[key_builder(data)] = data

    return output


# =====================================================
# MARKET INTELLIGENCE
# =====================================================


def load_market_intelligence(
    session: Session,
    config: IntelligenceConfig | None = None,
) -> dict[str, dict[str, Any]]:
    cfg = config or IntelligenceConfig()

    historical_query = """
        SELECT
            market,
            COUNT(*) AS sample_size,
            AVG(CASE WHEN profit > 0 THEN 1.0 ELSE 0.0 END) AS hit_rate,
            SUM(profit) / NULLIF(SUM(stake), 0) AS roi,
            AVG(odds) AS avg_odds,
            AVG(confidence) AS avg_confidence,
            AVG(value_score) AS avg_edge
        FROM historical_backtest_bets
        WHERE run_tag != :live_run_tag
          AND profit IS NOT NULL
          AND stake IS NOT NULL
          AND odds IS NOT NULL
          AND confidence IS NOT NULL
        GROUP BY market
        HAVING COUNT(*) >= :min_sample_size
    """

    live_query = """
        SELECT
            market,
            COUNT(*) AS sample_size,
            AVG(CASE WHEN profit > 0 THEN 1.0 ELSE 0.0 END) AS hit_rate,
            SUM(profit) / NULLIF(SUM(stake), 0) AS roi,
            AVG(odds) AS avg_odds,
            AVG(confidence) AS avg_confidence,
            AVG(value_score) AS avg_edge
        FROM historical_backtest_bets
        WHERE run_tag = :live_run_tag
          AND profit IS NOT NULL
          AND stake IS NOT NULL
          AND odds IS NOT NULL
          AND confidence IS NOT NULL
        GROUP BY market
    """

    historical = _load_query_as_dict(
        session=session,
        query=historical_query,
        params={
            "min_sample_size": cfg.min_sample_size,
            "live_run_tag": LIVE_RUN_TAG,
        },
        key_builder=lambda row: row["market"],
    )

    live = _load_query_as_dict(
        session=session,
        query=live_query,
        params={
            "live_run_tag": LIVE_RUN_TAG,
        },
        key_builder=lambda row: row["market"],
    )

    keys = set(historical.keys()) | set(live.keys())

    return {
        key: _merge_weighted_metrics(
            historical=historical.get(key),
            live=live.get(key),
            historical_weight=cfg.historical_weight,
            live_weight=cfg.live_weight,
        )
        for key in keys
    }


# =====================================================
# LEAGUE + MARKET INTELLIGENCE
# =====================================================


def load_league_market_intelligence(
    session: Session,
    config: IntelligenceConfig | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    cfg = config or IntelligenceConfig()

    query = """
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
    """

    return _load_query_as_dict(
        session=session,
        query=query,
        params={},
        key_builder=lambda row: (
            row["league"],
            row["market"],
        ),
    )


# =====================================================
# ODDS BAND INTELLIGENCE
# =====================================================


def load_odds_band_intelligence(
    session: Session,
    config: IntelligenceConfig | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    query = """
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
    """

    return _load_query_as_dict(
        session=session,
        query=query,
        params={},
        key_builder=lambda row: (
            row["market"],
            row["odds_band"],
        ),
    )


# =====================================================
# CONFIDENCE BAND INTELLIGENCE
# =====================================================


def load_confidence_band_intelligence(
    session: Session,
    config: IntelligenceConfig | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    query = """
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
    """

    return _load_query_as_dict(
        session=session,
        query=query,
        params={},
        key_builder=lambda row: (
            row["market"],
            row["confidence_band"],
        ),
    )