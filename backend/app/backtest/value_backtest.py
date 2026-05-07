# backend/app/backtest/value_backtest.py

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.backtest.settle import is_prediction_correct


DEFAULT_STARTING_BANKROLL = 10000.0
DEFAULT_STAKE = 100.0


def run_value_backtest(
    session: Session,
    slate: str,
    min_confidence: float = 0.0,
    min_edge: float = 0.0,
    min_odds: float = 1.0,
    max_odds: float = 20.0,
    market: str | None = None,
    flat_stake: float = DEFAULT_STAKE,
    starting_bankroll: float = DEFAULT_STARTING_BANKROLL,
) -> dict:
    query = text(
        """
        SELECT
            p.id AS prediction_id,
            p.market,
            p.predicted_label,
            p.confidence,
            p.odds,
            p.implied_probability,
            p.value_score,

            m.id AS match_id,
            m.league,
            m.home_team,
            m.away_team,
            m.home_goals,
            m.away_goals,

            hs.corners AS home_corners,
            as1.corners AS away_corners,

            hs.shots_on_target AS home_sot,
            as1.shots_on_target AS away_sot

        FROM predictions p

        JOIN matches m
            ON m.id = p.match_id

        LEFT JOIN team_match_stats hs
            ON hs.match_id = m.id
            AND hs.is_home = 1

        LEFT JOIN team_match_stats as1
            ON as1.match_id = m.id
            AND as1.is_home = 0

        WHERE p.slate = :slate
          AND p.odds IS NOT NULL
          AND p.odds >= :min_odds
          AND p.odds <= :max_odds
          AND p.confidence >= :min_confidence
          AND COALESCE(p.value_score, 0) >= :min_edge
          AND m.home_goals IS NOT NULL
          AND m.away_goals IS NOT NULL
        """
    )

    rows = session.execute(
        query,
        {
            "slate": slate,
            "min_confidence": min_confidence,
            "min_edge": min_edge,
            "min_odds": min_odds,
            "max_odds": max_odds,
        },
    ).mappings().all()

    bankroll = starting_bankroll

    total_bets = 0
    wins = 0
    losses = 0

    total_profit = 0.0
    total_staked = 0.0

    bet_results = []

    for row in rows:
        if market and row["market"] != market:
            continue

        odds = float(row["odds"])

        won = is_prediction_correct(
            predicted_label=row["predicted_label"],
            home_goals=row["home_goals"],
            away_goals=row["away_goals"],
            home_corners=row["home_corners"],
            away_corners=row["away_corners"],
            home_sot=row["home_sot"],
            away_sot=row["away_sot"],
        )

        profit = calculate_bet_profit(
            won=won,
            odds=odds,
            stake=flat_stake,
        )

        bankroll += profit

        total_bets += 1
        total_staked += flat_stake
        total_profit += profit

        if won:
            wins += 1
        else:
            losses += 1

        bet_results.append(
            {
                "prediction_id": row["prediction_id"],
                "match_id": row["match_id"],
                "league": row["league"],
                "market": row["market"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "predicted_label": row["predicted_label"],
                "confidence": round(float(row["confidence"]), 4),
                "odds": odds,
                "edge": round(float(row["value_score"] or 0.0), 4),
                "won": won,
                "profit": round(profit, 2),
                "bankroll_after_bet": round(bankroll, 2),
            }
        )

    roi = 0.0

    if total_staked > 0:
        roi = total_profit / total_staked

    hit_rate = 0.0

    if total_bets > 0:
        hit_rate = wins / total_bets

    return {
        "summary": {
            "slate": slate,
            "market_filter": market,
            "starting_bankroll": round(starting_bankroll, 2),
            "ending_bankroll": round(bankroll, 2),
            "total_bets": total_bets,
            "wins": wins,
            "losses": losses,
            "hit_rate": round(hit_rate, 4),
            "roi": round(roi, 4),
            "profit": round(total_profit, 2),
            "total_staked": round(total_staked, 2),
            "min_confidence": min_confidence,
            "min_edge": min_edge,
        },
        "bets": bet_results,
    }


def calculate_bet_profit(
    won: bool,
    odds: float,
    stake: float,
) -> float:
    if won:
        return (stake * odds) - stake

    return -stake