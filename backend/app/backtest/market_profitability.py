# backend/app/backtest/market_profitability.py

from collections import defaultdict

from sqlalchemy.orm import Session

from app.backtest.historical_value_backtest import (
    run_historical_value_backtest,
)

MARKETS_TO_TEST = [
    "home_win",
    "away_win",
    "draw",
    "double_chance_1x",
    "double_chance_x2",
    "double_chance_12",
    "over_1_5_goals",
    "under_1_5_goals",
    "over_2_5_goals",
    "under_2_5_goals",
    "over_3_5_goals",
    "under_3_5_goals",
    "btts_yes",
    "btts_no",
]


def summarize_market_profitability(
    session: Session,
    slate: str | None = None,
) -> dict:

    market_results = []

    league_tracker = defaultdict(
        lambda: {
            "bets": 0,
            "wins": 0,
            "profit": 0.0,
            "staked": 0.0,
        }
    )

    confidence_tracker = defaultdict(
        lambda: {
            "bets": 0,
            "wins": 0,
            "profit": 0.0,
            "staked": 0.0,
        }
    )

    odds_tracker = defaultdict(
        lambda: {
            "bets": 0,
            "wins": 0,
            "profit": 0.0,
            "staked": 0.0,
        }
    )

    for market in MARKETS_TO_TEST:

        try:

            result = run_historical_value_backtest(
                session=session,
                market=market,
                initial_train_size=50,
                test_window_size=20,
                limit=300,
                min_confidence=0.60,
                min_edge=0.0,
                stake=100.0,
                starting_bankroll=10000.0,
                use_only_matches_with_odds=True,
            )

        except Exception as exc:

            print(f"[MARKET SKIPPED] {market}: {exc}")
            continue

        summary = result["summary"]

        market_results.append(
            {
                "market": market,
                "roi": summary["roi"],
                "profit": summary["profit"],
                "bets": summary["total_bets"],
                "hit_rate": summary["hit_rate"],
                "wins": summary["wins"],
                "losses": summary["losses"],
            }
        )

        for bet in result["bets"]:

            league = bet["league"]

            league_tracker[league]["bets"] += 1
            league_tracker[league]["profit"] += bet["profit"]
            league_tracker[league]["staked"] += 100

            if bet["won"]:
                league_tracker[league]["wins"] += 1

            confidence_band = _confidence_band(
                bet["confidence"]
            )

            confidence_tracker[confidence_band]["bets"] += 1
            confidence_tracker[confidence_band]["profit"] += bet["profit"]
            confidence_tracker[confidence_band]["staked"] += 100

            if bet["won"]:
                confidence_tracker[confidence_band]["wins"] += 1

            odds_band = _odds_band(
                bet["odds"]
            )

            odds_tracker[odds_band]["bets"] += 1
            odds_tracker[odds_band]["profit"] += bet["profit"]
            odds_tracker[odds_band]["staked"] += 100

            if bet["won"]:
                odds_tracker[odds_band]["wins"] += 1

    best_markets = sorted(
        market_results,
        key=lambda x: x["roi"],
        reverse=True,
    )[:10]

    worst_markets = sorted(
        market_results,
        key=lambda x: x["roi"],
    )[:10]

    best_leagues = _build_rankings(league_tracker, reverse=True)
    worst_leagues = _build_rankings(league_tracker, reverse=False)

    confidence_analysis = _build_rankings(
        confidence_tracker,
        reverse=True,
    )

    odds_analysis = _build_rankings(
        odds_tracker,
        reverse=True,
    )

    return {
        "best_markets": best_markets,
        "worst_markets": worst_markets,
        "best_leagues": best_leagues[:20],
        "worst_leagues": worst_leagues[:20],
        "confidence_analysis": confidence_analysis,
        "odds_analysis": odds_analysis,
    }


def _build_rankings(
    tracker: dict,
    reverse: bool = True,
):

    rows = []

    for key, values in tracker.items():

        bets = values["bets"]

        if bets < 5:
            continue

        profit = values["profit"]
        staked = values["staked"]

        roi = profit / staked if staked else 0.0

        hit_rate = (
            values["wins"] / bets
            if bets
            else 0.0
        )

        rows.append(
            {
                "name": key,
                "bets": bets,
                "wins": values["wins"],
                "profit": round(profit, 2),
                "roi": round(roi, 4),
                "hit_rate": round(hit_rate, 4),
            }
        )

    return sorted(
        rows,
        key=lambda x: x["roi"],
        reverse=reverse,
    )


def _confidence_band(
    confidence: float,
) -> str:

    if confidence < 0.60:
        return "<0.60"

    if confidence < 0.70:
        return "0.60-0.69"

    if confidence < 0.80:
        return "0.70-0.79"

    if confidence < 0.90:
        return "0.80-0.89"

    return "0.90+"


def _odds_band(
    odds: float,
) -> str:

    if odds < 1.5:
        return "<1.5"

    if odds < 2.0:
        return "1.5-1.99"

    if odds < 3.0:
        return "2.0-2.99"

    if odds < 5.0:
        return "3.0-4.99"

    return "5.0+"