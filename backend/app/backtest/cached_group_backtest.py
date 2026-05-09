from __future__ import annotations

from collections import Counter
from math import prod
from statistics import mean
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.intelligence.portfolio_filters import evaluate_pick_for_portfolio


def cached_group_backtest(
    session: Session,
    run_tag: str | None = None,
    market: str | None = None,
    min_confidence: float = 0.60,
    min_edge: float | None = None,
    min_odds: float = 1.0,
    max_odds: float = 10.0,
    group_size: int = 4,
    stake: float = 100.0,
    limit: int = 100,
    max_same_league: int = 2,
    max_group_odds: float = 5.8,
    use_intelligence_filters: bool = False,
) -> dict[str, Any]:
    filters = [
        "hbb.confidence >= :min_confidence",
        "hbb.odds IS NOT NULL",
        "hbb.odds >= :min_odds",
        "hbb.odds <= :max_odds",
    ]

    params: dict[str, Any] = {
        "min_confidence": min_confidence,
        "min_odds": min_odds,
        "max_odds": max_odds,
        "limit": limit * group_size * 10,
    }

    if run_tag:
        filters.append("hbb.run_tag = :run_tag")
        params["run_tag"] = run_tag

    if market:
        filters.append("hbb.market = :market")
        params["market"] = market

    if min_edge is not None:
        filters.append("hbb.value_score >= :min_edge")
        params["min_edge"] = min_edge

    where_sql = " AND ".join(filters)

    rows = session.execute(
        text(
            f"""
            SELECT
                hbb.id,
                hbb.run_tag,
                hbb.match_id,
                hbb.league,
                hbb.home_team,
                hbb.away_team,
                m.kickoff_date,
                hbb.market,
                hbb.predicted_label,
                hbb.confidence,
                hbb.odds,
                hbb.value_score,
                hbb.won,
                hbb.profit,
                hbb.stake
            FROM historical_backtest_bets hbb
            JOIN matches m
                ON m.id = hbb.match_id
            WHERE {where_sql}
            ORDER BY
                m.kickoff_date ASC,
                hbb.confidence DESC,
                hbb.value_score DESC,
                hbb.odds ASC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    raw_candidates = [dict(row) for row in rows]

    candidates: list[dict[str, Any]] = []
    rejected_by_intelligence = 0
    rejection_reasons: Counter[str] = Counter()

    for bet in raw_candidates:
        if use_intelligence_filters:
            result = evaluate_pick_for_portfolio(
                session=session,
                league=bet.get("league"),
                market=str(bet["market"]),
                confidence=float(bet["confidence"]) if bet.get("confidence") is not None else None,
                odds=float(bet["odds"]) if bet.get("odds") is not None else None,
                value_score=float(bet["value_score"]) if bet.get("value_score") is not None else None,
                strict=True,
            )

            bet["portfolio_allowed"] = result.allowed
            bet["portfolio_filter_reason"] = result.reason
            bet["portfolio_risk_flags"] = result.risk_flags
            bet["portfolio_risk_score"] = result.risk_score

            if not result.allowed:
                rejected_by_intelligence += 1
                rejection_reasons[result.reason] += 1
                continue

        candidates.append(bet)

    bets_by_date: dict[str, list[dict[str, Any]]] = {}

    for bet in candidates:
        date_key = str(bet["kickoff_date"])
        bets_by_date.setdefault(date_key, []).append(bet)

    groups: list[list[dict[str, Any]]] = []
    used_match_ids: set[int] = set()

    skipped_group_odds = 0

    for _, day_bets in bets_by_date.items():
        current_group: list[dict[str, Any]] = []
        league_counts: Counter[str] = Counter()

        for bet in day_bets:
            match_id = int(bet["match_id"])
            league = str(bet["league"] or "unknown")

            if match_id in used_match_ids:
                continue

            if league_counts[league] >= max_same_league:
                continue

            test_group = current_group + [bet]
            test_odds = prod(float(item["odds"]) for item in test_group)

            if test_odds > max_group_odds:
                continue

            current_group.append(bet)
            used_match_ids.add(match_id)
            league_counts[league] += 1

            if len(current_group) == group_size:
                groups.append(current_group)
                current_group = []
                league_counts = Counter()

            if len(groups) >= limit:
                break

        if len(groups) >= limit:
            break

    bankroll = 10000.0
    won_groups = 0
    lost_groups = 0
    total_profit = 0.0

    group_reports = []

    display_index = 1

    for group in groups:
        odds_values = [float(bet["odds"]) for bet in group]
        total_odds = round(prod(odds_values), 4)

        if total_odds > max_group_odds:
            skipped_group_odds += 1
            continue

        group_won = all(bool(bet["won"]) for bet in group)

        if group_won:
            won_groups += 1
            profit = round(stake * (total_odds - 1), 2)
            outcome = "won"
        else:
            lost_groups += 1
            profit = -stake
            outcome = "lost"

        bankroll += profit
        total_profit += profit

        group_reports.append(
            {
                "group": display_index,
                "date": str(group[0]["kickoff_date"]),
                "outcome": outcome,
                "games": len(group),
                "markets": sorted({bet["market"] for bet in group}),
                "leagues": sorted({bet["league"] for bet in group}),
                "average_confidence": round(
                    mean(float(bet["confidence"]) for bet in group),
                    4,
                ),
                "average_value_score": round(
                    mean(float(bet["value_score"] or 0.0) for bet in group),
                    4,
                ),
                "average_risk_score": round(
                    mean(float(bet.get("portfolio_risk_score") or 0.0) for bet in group),
                    4,
                ),
                "risk_flags": sorted(
                    {
                        flag
                        for bet in group
                        for flag in bet.get("portfolio_risk_flags", [])
                    }
                ),
                "total_odds": total_odds,
                "profit": profit,
                "bankroll": round(bankroll, 2),
            }
        )

        display_index += 1

    total_groups = len(group_reports)

    return {
        "summary": {
            "source": "historical_backtest_bets",
            "run_tag": run_tag,
            "market": market,
            "groups": total_groups,
            "won_groups": won_groups,
            "lost_groups": lost_groups,
            "hit_rate": round(won_groups / total_groups, 4) if total_groups else 0.0,
            "total_profit": round(total_profit, 2),
            "roi": round(total_profit / (total_groups * stake), 4) if total_groups else 0.0,
            "ending_bankroll": round(bankroll, 2),
            "group_size": group_size,
            "max_same_league": max_same_league,
            "market_limit": market or "none",
            "same_day_grouping": True,
            "max_group_odds": max_group_odds,
            "use_intelligence_filters": use_intelligence_filters,
            "raw_candidates": len(raw_candidates),
            "approved_candidates": len(candidates),
            "rejected_by_intelligence": rejected_by_intelligence,
            "rejection_reasons": dict(rejection_reasons),
            "skipped_group_odds": skipped_group_odds,
        },
        "groups": group_reports,
    }