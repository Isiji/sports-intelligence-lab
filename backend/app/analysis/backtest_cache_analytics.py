# backend/app/analysis/backtest_cache_analytics.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


MIN_SAMPLE_SIZE = 20


@dataclass
class ProfitabilityFilters:
    market: str | None = None
    league: str | None = None
    run_tag: str | None = None
    min_confidence: float | None = None
    min_edge: float | None = None
    min_odds: float | None = None
    max_odds: float | None = None
    min_sample_size: int = MIN_SAMPLE_SIZE


def _where_clause(
    filters: ProfitabilityFilters,
    alias: str = "",
) -> tuple[str, dict[str, Any]]:
    prefix = f"{alias}." if alias else ""

    clauses = ["1=1"]
    params: dict[str, Any] = {}

    if filters.market:
        clauses.append(f"{prefix}market = :market")
        params["market"] = filters.market

    if filters.league:
        clauses.append(f"{prefix}league = :league")
        params["league"] = filters.league

    if filters.run_tag:
        clauses.append(f"{prefix}run_tag = :run_tag")
        params["run_tag"] = filters.run_tag

    if filters.min_confidence is not None:
        clauses.append(f"{prefix}confidence >= :min_confidence")
        params["min_confidence"] = filters.min_confidence

    if filters.min_edge is not None:
        clauses.append(f"{prefix}value_score >= :min_edge")
        params["min_edge"] = filters.min_edge

    if filters.min_odds is not None:
        clauses.append(f"{prefix}odds >= :min_odds")
        params["min_odds"] = filters.min_odds

    if filters.max_odds is not None:
        clauses.append(f"{prefix}odds <= :max_odds")
        params["max_odds"] = filters.max_odds

    return " AND ".join(clauses), params


def market_profitability_fast(
    session: Session,
    filters: ProfitabilityFilters,
    limit: int = 50,
) -> list[dict[str, Any]]:
    where_sql, params = _where_clause(filters)

    params["min_sample_size"] = filters.min_sample_size
    params["limit"] = limit

    query = text(
        f"""
        SELECT
            market,

            COUNT(*) AS bets,

            SUM(CASE WHEN won = true THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN won = false THEN 1 ELSE 0 END) AS losses,

            ROUND(
                AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END)::numeric,
                4
            ) AS hit_rate,

            ROUND(AVG(odds)::numeric, 3) AS avg_odds,

            ROUND(
                AVG(confidence)::numeric,
                4
            ) AS avg_confidence,

            ROUND(
                AVG(implied_probability)::numeric,
                4
            ) AS avg_implied_probability,

            ROUND(
                AVG(value_score)::numeric,
                4
            ) AS avg_edge,

            ROUND(
                SUM(stake)::numeric,
                2
            ) AS total_staked,

            ROUND(
                SUM(profit)::numeric,
                2
            ) AS total_profit,

            ROUND(
                (SUM(profit) / NULLIF(SUM(stake), 0))::numeric,
                4
            ) AS roi

        FROM historical_backtest_bets

        WHERE {where_sql}
          AND odds IS NOT NULL
          AND confidence IS NOT NULL
          AND profit IS NOT NULL
          AND stake IS NOT NULL

        GROUP BY market

        HAVING COUNT(*) >= :min_sample_size

        ORDER BY
            roi DESC,
            total_profit DESC,
            bets DESC

        LIMIT :limit
        """
    )

    return [
        dict(row._mapping)
        for row in session.execute(query, params).fetchall()
    ]


def league_profitability_fast(
    session: Session,
    filters: ProfitabilityFilters,
    limit: int = 100,
) -> list[dict[str, Any]]:
    where_sql, params = _where_clause(filters)

    params["min_sample_size"] = filters.min_sample_size
    params["limit"] = limit

    query = text(
        f"""
        SELECT
            league,
            market,

            COUNT(*) AS bets,

            SUM(CASE WHEN won = true THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN won = false THEN 1 ELSE 0 END) AS losses,

            ROUND(
                AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END)::numeric,
                4
            ) AS hit_rate,

            ROUND(AVG(odds)::numeric, 3) AS avg_odds,

            ROUND(
                AVG(confidence)::numeric,
                4
            ) AS avg_confidence,

            ROUND(
                AVG(value_score)::numeric,
                4
            ) AS avg_edge,

            ROUND(
                SUM(stake)::numeric,
                2
            ) AS total_staked,

            ROUND(
                SUM(profit)::numeric,
                2
            ) AS total_profit,

            ROUND(
                (SUM(profit) / NULLIF(SUM(stake), 0))::numeric,
                4
            ) AS roi

        FROM historical_backtest_bets

        WHERE {where_sql}
          AND league IS NOT NULL
          AND odds IS NOT NULL
          AND confidence IS NOT NULL
          AND profit IS NOT NULL
          AND stake IS NOT NULL

        GROUP BY league, market

        HAVING COUNT(*) >= :min_sample_size

        ORDER BY
            roi DESC,
            total_profit DESC,
            bets DESC

        LIMIT :limit
        """
    )

    return [
        dict(row._mapping)
        for row in session.execute(query, params).fetchall()
    ]


def odds_band_profitability_fast(
    session: Session,
    filters: ProfitabilityFilters,
) -> list[dict[str, Any]]:
    where_sql, params = _where_clause(filters)

    params["min_sample_size"] = filters.min_sample_size

    query = text(
        f"""
        WITH banded AS (
            SELECT
                *,

                CASE
                    WHEN odds < 1.30 THEN 'below_1.30'
                    WHEN odds >= 1.30 AND odds < 1.50 THEN '1.30_to_1.49'
                    WHEN odds >= 1.50 AND odds < 1.80 THEN '1.50_to_1.79'
                    WHEN odds >= 1.80 AND odds < 2.20 THEN '1.80_to_2.19'
                    WHEN odds >= 2.20 AND odds < 3.00 THEN '2.20_to_2.99'
                    WHEN odds >= 3.00 THEN '3.00_plus'
                    ELSE 'unknown'
                END AS odds_band

            FROM historical_backtest_bets

            WHERE {where_sql}
              AND odds IS NOT NULL
              AND confidence IS NOT NULL
              AND profit IS NOT NULL
              AND stake IS NOT NULL
        )

        SELECT
            odds_band,

            COUNT(*) AS bets,

            SUM(CASE WHEN won = true THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN won = false THEN 1 ELSE 0 END) AS losses,

            ROUND(
                AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END)::numeric,
                4
            ) AS hit_rate,

            ROUND(AVG(odds)::numeric, 3) AS avg_odds,

            ROUND(
                AVG(confidence)::numeric,
                4
            ) AS avg_confidence,

            ROUND(
                AVG(value_score)::numeric,
                4
            ) AS avg_edge,

            ROUND(
                SUM(stake)::numeric,
                2
            ) AS total_staked,

            ROUND(
                SUM(profit)::numeric,
                2
            ) AS total_profit,

            ROUND(
                (SUM(profit) / NULLIF(SUM(stake), 0))::numeric,
                4
            ) AS roi

        FROM banded

        GROUP BY odds_band

        HAVING COUNT(*) >= :min_sample_size

        ORDER BY
            roi DESC,
            total_profit DESC
        """
    )

    return [
        dict(row._mapping)
        for row in session.execute(query, params).fetchall()
    ]


def confidence_band_profitability_fast(
    session: Session,
    filters: ProfitabilityFilters,
) -> list[dict[str, Any]]:
    where_sql, params = _where_clause(filters)

    params["min_sample_size"] = filters.min_sample_size

    query = text(
        f"""
        WITH banded AS (
            SELECT
                *,

                CASE
                    WHEN confidence < 0.50 THEN 'below_0.50'
                    WHEN confidence >= 0.50 AND confidence < 0.60 THEN '0.50_to_0.59'
                    WHEN confidence >= 0.60 AND confidence < 0.70 THEN '0.60_to_0.69'
                    WHEN confidence >= 0.70 AND confidence < 0.80 THEN '0.70_to_0.79'
                    WHEN confidence >= 0.80 AND confidence < 0.90 THEN '0.80_to_0.89'
                    WHEN confidence >= 0.90 THEN '0.90_plus'
                    ELSE 'unknown'
                END AS confidence_band

            FROM historical_backtest_bets

            WHERE {where_sql}
              AND confidence IS NOT NULL
              AND odds IS NOT NULL
              AND profit IS NOT NULL
              AND stake IS NOT NULL
        )

        SELECT
            confidence_band,

            COUNT(*) AS bets,

            SUM(CASE WHEN won = true THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN won = false THEN 1 ELSE 0 END) AS losses,

            ROUND(
                AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END)::numeric,
                4
            ) AS hit_rate,

            ROUND(AVG(odds)::numeric, 3) AS avg_odds,

            ROUND(
                AVG(confidence)::numeric,
                4
            ) AS avg_confidence,

            ROUND(
                AVG(value_score)::numeric,
                4
            ) AS avg_edge,

            ROUND(
                SUM(stake)::numeric,
                2
            ) AS total_staked,

            ROUND(
                SUM(profit)::numeric,
                2
            ) AS total_profit,

            ROUND(
                (SUM(profit) / NULLIF(SUM(stake), 0))::numeric,
                4
            ) AS roi

        FROM banded

        GROUP BY confidence_band

        HAVING COUNT(*) >= :min_sample_size

        ORDER BY confidence_band
        """
    )

    return [
        dict(row._mapping)
        for row in session.execute(query, params).fetchall()
    ]


def optimize_profit_thresholds_fast(
    session: Session,
    market: str | None = None,
    league: str | None = None,
    run_tag: str | None = None,
    min_sample_size: int = 30,
) -> list[dict[str, Any]]:
    confidence_thresholds = [
        0.50,
        0.55,
        0.60,
        0.65,
        0.70,
        0.75,
        0.80,
        0.85,
        0.90,
    ]

    edge_thresholds = [
        -0.05,
        0.00,
        0.03,
        0.05,
        0.08,
        0.10,
        0.15,
    ]

    odds_ranges = [
        (1.20, 1.50),
        (1.30, 1.80),
        (1.50, 2.20),
        (1.80, 3.00),
        (2.00, 5.00),
    ]

    results: list[dict[str, Any]] = []

    for min_conf in confidence_thresholds:
        for min_edge in edge_thresholds:
            for min_odds, max_odds in odds_ranges:
                filters = ProfitabilityFilters(
                    market=market,
                    league=league,
                    run_tag=run_tag,
                    min_confidence=min_conf,
                    min_edge=min_edge,
                    min_odds=min_odds,
                    max_odds=max_odds,
                    min_sample_size=min_sample_size,
                )

                where_sql, params = _where_clause(filters)

                params["min_sample_size"] = min_sample_size

                query = text(
                    f"""
                    SELECT
                        COUNT(*) AS bets,

                        SUM(CASE WHEN won = true THEN 1 ELSE 0 END) AS wins,
                        SUM(CASE WHEN won = false THEN 1 ELSE 0 END) AS losses,

                        ROUND(
                            AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END)::numeric,
                            4
                        ) AS hit_rate,

                        ROUND(AVG(odds)::numeric, 3) AS avg_odds,

                        ROUND(
                            AVG(confidence)::numeric,
                            4
                        ) AS avg_confidence,

                        ROUND(
                            AVG(value_score)::numeric,
                            4
                        ) AS avg_edge,

                        ROUND(
                            SUM(stake)::numeric,
                            2
                        ) AS total_staked,

                        ROUND(
                            SUM(profit)::numeric,
                            2
                        ) AS total_profit,

                        ROUND(
                            (SUM(profit) / NULLIF(SUM(stake), 0))::numeric,
                            4
                        ) AS roi

                    FROM historical_backtest_bets

                    WHERE {where_sql}
                      AND odds IS NOT NULL
                      AND confidence IS NOT NULL
                      AND profit IS NOT NULL
                      AND stake IS NOT NULL

                    HAVING COUNT(*) >= :min_sample_size
                    """
                )

                row = session.execute(query, params).fetchone()

                if not row:
                    continue

                data = dict(row._mapping)

                if not data.get("bets"):
                    continue

                data.update(
                    {
                        "market": market or "ALL",
                        "league": league or "ALL",
                        "min_confidence": min_conf,
                        "min_edge": min_edge,
                        "min_odds": min_odds,
                        "max_odds": max_odds,
                    }
                )

                results.append(data)

    results.sort(
        key=lambda x: (
            float(x["roi"] or 0),
            float(x["total_profit"] or 0),
            int(x["bets"] or 0),
        ),
        reverse=True,
    )

    return results[:50]