from __future__ import annotations

from app.backtest.historical_value_backtest import run_historical_value_backtest
from app.features.football_features import MARKET_TARGETS
from sqlalchemy.orm import Session


CONFIDENCE_THRESHOLDS = [
    0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90
]

EDGE_THRESHOLDS = [
    -0.05, 0.00, 0.03, 0.05, 0.08, 0.10, 0.15
]

ODDS_RANGES = [
    (1.10, 1.29),
    (1.30, 1.49),
    (1.50, 1.79),
    (1.80, 2.19),
    (2.20, 2.99),
    (3.00, 4.99),
    (5.00, 20.00),
]


def optimize_profit_thresholds(
    session: Session,
    market: str,
    initial_train_size: int = 50,
    test_window_size: int = 20,
    limit: int = 300,
    stake: float = 100.0,
    min_bets: int = 5,
) -> dict:

    if market not in MARKET_TARGETS:
        raise ValueError(f"Unsupported market: {market}")

    raw_result = run_historical_value_backtest(
        session=session,
        market=market,
        initial_train_size=initial_train_size,
        test_window_size=test_window_size,
        limit=limit,
        min_confidence=0.50,
        min_edge=-0.10,
        stake=stake,
        starting_bankroll=10000.0,
        use_only_matches_with_odds=True,
    )

    bets = raw_result["bets"]

    results = []

    for confidence_threshold in CONFIDENCE_THRESHOLDS:
        for edge_threshold in EDGE_THRESHOLDS:
            for min_odds, max_odds in ODDS_RANGES:

                filtered_bets = []

                for bet in bets:
                    odds = bet.get("odds")
                    value_score = bet.get("value_score")
                    confidence = bet.get("confidence")

                    if odds is None:
                        continue

                    if value_score is None:
                        continue

                    if confidence < confidence_threshold:
                        continue

                    if value_score < edge_threshold:
                        continue

                    if not (min_odds <= odds <= max_odds):
                        continue

                    filtered_bets.append(bet)

                if len(filtered_bets) < min_bets:
                    continue

                wins = sum(1 for bet in filtered_bets if bet["won"])
                losses = len(filtered_bets) - wins
                profit = sum(float(bet["profit"]) for bet in filtered_bets)
                total_staked = len(filtered_bets) * stake

                roi = profit / total_staked if total_staked else 0.0
                hit_rate = wins / len(filtered_bets) if filtered_bets else 0.0

                results.append(
                    {
                        "market": market,
                        "confidence_threshold": confidence_threshold,
                        "edge_threshold": edge_threshold,
                        "min_odds": min_odds,
                        "max_odds": max_odds,
                        "bets": len(filtered_bets),
                        "wins": wins,
                        "losses": losses,
                        "hit_rate": round(hit_rate, 4),
                        "roi": round(roi, 4),
                        "profit": round(profit, 2),
                        "total_staked": round(total_staked, 2),
                    }
                )

    ranked = sorted(
        results,
        key=lambda row: (
            row["roi"],
            row["profit"],
            row["bets"],
        ),
        reverse=True,
    )

    return {
        "market": market,
        "raw_summary": raw_result["summary"],
        "best_thresholds": ranked[:20],
        "worst_thresholds": ranked[-20:],
        "total_combinations_tested": len(results),
    }


def optimize_all_profit_thresholds(
    session: Session,
    min_bets: int = 5,
) -> dict:

    all_results = []

    for market in MARKET_TARGETS.keys():
        try:
            result = optimize_profit_thresholds(
                session=session,
                market=market,
                min_bets=min_bets,
            )

            best = result["best_thresholds"]

            if not best:
                continue

            all_results.append(best[0])

        except Exception as exc:
            print(f"[OPTIMIZER SKIPPED] {market}: {exc}")

    ranked = sorted(
        all_results,
        key=lambda row: (
            row["roi"],
            row["profit"],
            row["bets"],
        ),
        reverse=True,
    )

    return {
        "best_market_thresholds": ranked,
    }