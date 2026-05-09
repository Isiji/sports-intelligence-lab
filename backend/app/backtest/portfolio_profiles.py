from __future__ import annotations

from itertools import product

from sqlalchemy.orm import Session

from app.backtest.cached_group_backtest import cached_group_backtest


PROFILE_CONFIGS = {
    "SAFE_A_LOW_ODDS": {
        "min_confidence": 0.90,
        "max_odds": 1.90,
        "max_group_odds": 4.0,
    },
    "SAFE_B_CURRENT_BEST": {
        "min_confidence": 0.90,
        "max_odds": 1.98,
        "max_group_odds": 4.5,
    },
    "SAFE_C_HIGHER_CONF": {
        "min_confidence": 0.92,
        "max_odds": 1.90,
        "max_group_odds": 4.5,
    },
    "SAFE_D_MORE_ROOM": {
        "min_confidence": 0.93,
        "max_odds": 2.20,
        "max_group_odds": 5.0,
    },
    "BALANCED_REFERENCE": {
        "min_confidence": 0.90,
        "max_odds": 2.50,
        "max_group_odds": 5.8,
    },
    "AGGRESSIVE_REFERENCE": {
        "min_confidence": 0.80,
        "max_odds": 3.00,
        "max_group_odds": 8.0,
    },
}

def run_portfolio_profiles(
    session: Session,
    run_tag: str,
):
    results = []

    for profile_name, config in PROFILE_CONFIGS.items():

        result = cached_group_backtest(
            session=session,
            run_tag=run_tag,
            min_confidence=config["min_confidence"],
            min_odds=1.20,
            max_odds=config["max_odds"],
            max_group_odds=config["max_group_odds"],
            use_intelligence_filters=True,
        )

        summary = result["summary"]
        analytics = result["analytics"]["summary"]

        results.append(
            {
                "profile": profile_name,
                "groups": summary["groups"],
                "hit_rate": summary["hit_rate"],
                "roi": summary["roi"],
                "profit": summary["total_profit"],
                "ending_bankroll": summary["ending_bankroll"],
                "max_drawdown": analytics["max_drawdown"],
                "volatility": analytics["volatility"],
                "profit_factor": analytics["profit_factor"],
                "expectancy": analytics["expectancy"],
            }
        )

    return sorted(
        results,
        key=lambda row: (
            row["roi"],
            row["profit_factor"],
            -row["max_drawdown"],
        ),
        reverse=True,
    )