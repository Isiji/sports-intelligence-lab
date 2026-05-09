# backend/app/backtest/portfolio_analytics.py

from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Any


def build_portfolio_analytics(
    groups: list[dict[str, Any]],
    starting_bankroll: float = 10000.0,
) -> dict[str, Any]:
    if not groups:
        return {
            "summary": {
                "groups": 0,
                "starting_bankroll": starting_bankroll,
                "ending_bankroll": starting_bankroll,
                "profit": 0.0,
                "roi": 0.0,
                "max_drawdown": 0.0,
                "longest_losing_streak": 0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "volatility": 0.0,
            },
            "bankroll_curve": [],
            "tier_performance": [],
            "market_performance": [],
            "league_performance": [],
        }

    bankroll_curve = []
    peak_bankroll = starting_bankroll
    max_drawdown = 0.0

    profits = []
    stakes = []
    winning_profit = 0.0
    losing_profit = 0.0

    current_losing_streak = 0
    longest_losing_streak = 0

    tier_rows = defaultdict(lambda: {"groups": 0, "wins": 0, "profit": 0.0, "stake": 0.0})
    market_rows = defaultdict(lambda: {"groups": 0, "wins": 0, "profit": 0.0, "stake": 0.0})
    league_rows = defaultdict(lambda: {"groups": 0, "wins": 0, "profit": 0.0, "stake": 0.0})

    for group in groups:
        profit = float(group.get("profit") or 0.0)
        stake = float(group.get("stake") or 0.0)
        bankroll = float(group.get("bankroll") or starting_bankroll)
        outcome = str(group.get("outcome") or "unknown")
        tier = str(group.get("group_tier") or "UNKNOWN")

        profits.append(profit)
        stakes.append(stake)

        peak_bankroll = max(peak_bankroll, bankroll)
        drawdown = peak_bankroll - bankroll
        max_drawdown = max(max_drawdown, drawdown)

        if profit > 0:
            winning_profit += profit
            current_losing_streak = 0
        elif profit < 0:
            losing_profit += abs(profit)
            current_losing_streak += 1
            longest_losing_streak = max(longest_losing_streak, current_losing_streak)

        bankroll_curve.append(
            {
                "group": group.get("group"),
                "date": group.get("date"),
                "bankroll": round(bankroll, 2),
                "profit": round(profit, 2),
                "drawdown": round(drawdown, 2),
                "tier": tier,
                "outcome": outcome,
            }
        )

        tier_rows[tier]["groups"] += 1
        tier_rows[tier]["wins"] += 1 if outcome == "won" else 0
        tier_rows[tier]["profit"] += profit
        tier_rows[tier]["stake"] += stake

        for market in group.get("markets", []):
            market_rows[market]["groups"] += 1
            market_rows[market]["wins"] += 1 if outcome == "won" else 0
            market_rows[market]["profit"] += profit / max(len(group.get("markets", [])), 1)
            market_rows[market]["stake"] += stake / max(len(group.get("markets", [])), 1)

        for league in group.get("leagues", []):
            league_rows[league]["groups"] += 1
            league_rows[league]["wins"] += 1 if outcome == "won" else 0
            league_rows[league]["profit"] += profit / max(len(group.get("leagues", [])), 1)
            league_rows[league]["stake"] += stake / max(len(group.get("leagues", [])), 1)

    total_profit = sum(profits)
    total_staked = sum(stakes)
    ending_bankroll = starting_bankroll + total_profit

    def summarize(rows: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
        output = []

        for name, row in rows.items():
            groups_count = int(row["groups"])
            stake_total = float(row["stake"])
            profit_total = float(row["profit"])

            output.append(
                {
                    "name": name,
                    "groups": groups_count,
                    "wins": int(row["wins"]),
                    "hit_rate": round(row["wins"] / groups_count, 4) if groups_count else 0.0,
                    "profit": round(profit_total, 2),
                    "stake": round(stake_total, 2),
                    "roi": round(profit_total / stake_total, 4) if stake_total > 0 else 0.0,
                }
            )

        return sorted(output, key=lambda item: item["profit"], reverse=True)

    return {
        "summary": {
            "groups": len(groups),
            "starting_bankroll": round(starting_bankroll, 2),
            "ending_bankroll": round(ending_bankroll, 2),
            "profit": round(total_profit, 2),
            "roi": round(total_profit / total_staked, 4) if total_staked > 0 else 0.0,
            "total_staked": round(total_staked, 2),
            "max_drawdown": round(max_drawdown, 2),
            "max_drawdown_pct": round(max_drawdown / starting_bankroll, 4) if starting_bankroll > 0 else 0.0,
            "longest_losing_streak": longest_losing_streak,
            "profit_factor": round(winning_profit / losing_profit, 4) if losing_profit > 0 else 0.0,
            "expectancy": round(mean(profits), 2) if profits else 0.0,
            "volatility": round(pstdev(profits), 2) if len(profits) > 1 else 0.0,
        },
        "bankroll_curve": bankroll_curve,
        "tier_performance": summarize(tier_rows),
        "market_performance": summarize(market_rows),
        "league_performance": summarize(league_rows),
    }