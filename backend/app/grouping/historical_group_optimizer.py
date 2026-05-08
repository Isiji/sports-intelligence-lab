# backend/app/grouping/historical_group_optimizer.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class GroupOptimizerConfig:
    group_size: int = 4
    max_groups: int = 10
    min_confidence: float = 0.60
    min_edge: float = 0.00
    min_odds: float = 1.25
    max_odds: float = 3.50
    min_market_roi: float = 0.00
    min_league_roi: float = 0.00
    min_sample_size: int = 20


def build_historical_best_groups(
    session: Session,
    slate: str | None = None,
    run_tag: str | None = None,
    config: GroupOptimizerConfig | None = None,
) -> list[dict[str, Any]]:
    cfg = config or GroupOptimizerConfig()

    params: dict[str, Any] = {
        "min_confidence": cfg.min_confidence,
        "min_edge": cfg.min_edge,
        "min_odds": cfg.min_odds,
        "max_odds": cfg.max_odds,
        "min_market_roi": cfg.min_market_roi,
        "min_league_roi": cfg.min_league_roi,
        "min_sample_size": cfg.min_sample_size,
        "limit": cfg.group_size * cfg.max_groups * 8,
    }

    extra_filters = []

    if slate:
        extra_filters.append("b.slate = :slate")
        params["slate"] = slate

    if run_tag:
        extra_filters.append("b.run_tag = :run_tag")
        params["run_tag"] = run_tag

    extra_sql = ""
    if extra_filters:
        extra_sql = " AND " + " AND ".join(extra_filters)

    query = text(
        f"""
        WITH market_perf AS (
            SELECT
                market,
                COUNT(*) AS sample_size,
                AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END) AS hit_rate,
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
        ),
        league_perf AS (
            SELECT
                league,
                market,
                COUNT(*) AS sample_size,
                AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END) AS hit_rate,
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
        ),
        odds_band_perf AS (
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
                AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END) AS hit_rate,
                SUM(profit) / NULLIF(SUM(stake), 0) AS roi
            FROM historical_backtest_bets
            WHERE profit IS NOT NULL
              AND stake IS NOT NULL
              AND odds IS NOT NULL
            GROUP BY market, odds_band
            HAVING COUNT(*) >= :min_sample_size
        ),
        candidates AS (
            SELECT
                b.id,
                b.match_id,
                b.slate,
                b.league,
                b.home_team,
                b.away_team,
                b.market,
                b.predicted_label,
                b.confidence,
                b.odds,
                b.implied_probability,
                b.value_score,
                b.profit,
                b.stake,
                b.run_tag,

                CASE
                    WHEN b.profit > 0 THEN 'win'
                    WHEN b.profit < 0 THEN 'loss'
                    ELSE 'push'
                END AS derived_result,

                CASE
                    WHEN b.odds < 1.30 THEN 'below_1.30'
                    WHEN b.odds >= 1.30 AND b.odds < 1.50 THEN '1.30_to_1.49'
                    WHEN b.odds >= 1.50 AND b.odds < 1.80 THEN '1.50_to_1.79'
                    WHEN b.odds >= 1.80 AND b.odds < 2.20 THEN '1.80_to_2.19'
                    WHEN b.odds >= 2.20 AND b.odds < 3.00 THEN '2.20_to_2.99'
                    WHEN b.odds >= 3.00 THEN '3.00_plus'
                    ELSE 'unknown'
                END AS odds_band,

                mp.roi AS market_roi,
                mp.hit_rate AS market_hit_rate,
                mp.sample_size AS market_sample_size,

                COALESCE(lp.roi, 0) AS league_roi,
                COALESCE(lp.hit_rate, 0) AS league_hit_rate,
                COALESCE(lp.sample_size, 0) AS league_sample_size,

                COALESCE(obp.roi, 0) AS odds_band_roi,
                COALESCE(obp.hit_rate, 0) AS odds_band_hit_rate,
                COALESCE(obp.sample_size, 0) AS odds_band_sample_size,

                (
                    (b.confidence * 0.30)
                    + (COALESCE(b.value_score, 0) * 0.25)
                    + (COALESCE(mp.roi, 0) * 0.20)
                    + (COALESCE(lp.roi, 0) * 0.15)
                    + (COALESCE(obp.roi, 0) * 0.10)
                ) AS selection_score

            FROM historical_backtest_bets b
            JOIN market_perf mp
                ON mp.market = b.market
            LEFT JOIN league_perf lp
                ON lp.market = b.market
               AND lp.league = b.league
            LEFT JOIN odds_band_perf obp
                ON obp.market = b.market
               AND obp.odds_band =
                    CASE
                        WHEN b.odds < 1.30 THEN 'below_1.30'
                        WHEN b.odds >= 1.30 AND b.odds < 1.50 THEN '1.30_to_1.49'
                        WHEN b.odds >= 1.50 AND b.odds < 1.80 THEN '1.50_to_1.79'
                        WHEN b.odds >= 1.80 AND b.odds < 2.20 THEN '1.80_to_2.19'
                        WHEN b.odds >= 2.20 AND b.odds < 3.00 THEN '2.20_to_2.99'
                        WHEN b.odds >= 3.00 THEN '3.00_plus'
                        ELSE 'unknown'
                    END

            WHERE b.confidence >= :min_confidence
              AND COALESCE(b.value_score, 0) >= :min_edge
              AND b.odds BETWEEN :min_odds AND :max_odds
              AND b.profit IS NOT NULL
              AND b.stake IS NOT NULL
              AND mp.roi >= :min_market_roi
              AND COALESCE(lp.roi, 0) >= :min_league_roi
              {extra_sql}
        )
        SELECT *
        FROM candidates
        ORDER BY selection_score DESC, confidence DESC, value_score DESC
        LIMIT :limit
        """
    )

    candidates = [dict(row._mapping) for row in session.execute(query, params).fetchall()]

    groups: list[dict[str, Any]] = []
    used_match_ids: set[int] = set()

    for group_number in range(1, cfg.max_groups + 1):
        group_items: list[dict[str, Any]] = []

        used_markets_in_group: set[str] = set()
        used_leagues_in_group: set[str] = set()

        for item in candidates:
            match_id = int(item["match_id"])

            if match_id in used_match_ids:
                continue

            market = item["market"]
            league = item.get("league") or "unknown"

            same_market_count = sum(1 for x in group_items if x["market"] == market)
            same_league_count = sum(1 for x in group_items if (x.get("league") or "unknown") == league)

            if same_market_count >= 2:
                continue

            if same_league_count >= 2:
                continue

            group_items.append(item)
            used_match_ids.add(match_id)
            used_markets_in_group.add(market)
            used_leagues_in_group.add(league)

            if len(group_items) == cfg.group_size:
                break

        if len(group_items) < cfg.group_size:
            break

        combined_odds = 1.0
        avg_confidence = 0.0
        avg_edge = 0.0
        avg_market_roi = 0.0
        avg_league_roi = 0.0
        avg_odds_band_roi = 0.0
        avg_selection_score = 0.0
        wins = 0
        losses = 0
        pushes = 0

        for item in group_items:
            combined_odds *= float(item["odds"])
            avg_confidence += float(item["confidence"] or 0)
            avg_edge += float(item["value_score"] or 0)
            avg_market_roi += float(item["market_roi"] or 0)
            avg_league_roi += float(item["league_roi"] or 0)
            avg_odds_band_roi += float(item["odds_band_roi"] or 0)
            avg_selection_score += float(item["selection_score"] or 0)

            if item["derived_result"] == "win":
                wins += 1
            elif item["derived_result"] == "loss":
                losses += 1
            else:
                pushes += 1

        size = len(group_items)

        groups.append(
            {
                "group_number": group_number,
                "group_size": size,
                "combined_odds": round(combined_odds, 3),
                "avg_confidence": round(avg_confidence / size, 4),
                "avg_edge": round(avg_edge / size, 4),
                "avg_market_roi": round(avg_market_roi / size, 4),
                "avg_league_roi": round(avg_league_roi / size, 4),
                "avg_odds_band_roi": round(avg_odds_band_roi / size, 4),
                "avg_selection_score": round(avg_selection_score / size, 4),
                "historical_group_won": wins == size,
                "legs_won": wins,
                "legs_lost": losses,
                "legs_pushed": pushes,
                "items": group_items,
            }
        )

    return groups