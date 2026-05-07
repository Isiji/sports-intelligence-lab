# backend/app/backtest/historical_value_backtest.py

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.backtest.settle import is_prediction_correct
from app.features.football_features import (
    MARKET_LABELS,
    MARKET_TARGETS,
    feature_columns,
    filter_training_frame_for_market,
    load_training_frame,
)


DEFAULT_STARTING_BANKROLL = 10000.0
DEFAULT_STAKE = 100.0


@dataclass
class HistoricalBet:
    match_id: int
    league: str
    home_team: str
    away_team: str
    market: str
    predicted_label: str
    confidence: float
    odds: float | None
    implied_probability: float | None
    value_score: float | None
    won: bool
    profit: float
    bankroll_after_bet: float


def run_historical_value_backtest(
    session: Session,
    market: str = "home_win",
    initial_train_size: int = 300,
    test_window_size: int = 50,
    min_confidence: float = 0.60,
    min_edge: float = 0.0,
    stake: float = DEFAULT_STAKE,
    starting_bankroll: float = DEFAULT_STARTING_BANKROLL,
    use_only_matches_with_odds: bool = False,
) -> dict:
    if market not in MARKET_TARGETS:
        raise ValueError(f"Unsupported market: {market}")

    df = load_training_frame(session)
    df = filter_training_frame_for_market(df, market)

    if df.empty:
        raise ValueError("No real training data found. Build features first.")

    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    minimum_required = initial_train_size + test_window_size

    if len(df) < minimum_required:
        raise ValueError(
            f"Need at least {minimum_required} finished matches for this backtest. "
            f"Available: {len(df)}"
        )

    target_column = MARKET_TARGETS[market]
    positive_label, negative_label = MARKET_LABELS[market]

    bankroll = starting_bankroll
    total_staked = 0.0
    total_profit = 0.0
    wins = 0
    losses = 0

    bets: list[HistoricalBet] = []
    windows = []

    start_test_index = initial_train_size

    while start_test_index + test_window_size <= len(df):
        train_df = df.iloc[:start_test_index].copy()
        test_df = df.iloc[
            start_test_index:start_test_index + test_window_size
        ].copy()

        if train_df[target_column].nunique() < 2:
            start_test_index += test_window_size
            continue

        model = _build_model()
        model.fit(
            train_df[feature_columns()].fillna(0.0),
            train_df[target_column].astype(int),
        )

        x_test = test_df[feature_columns()].fillna(0.0)
        probabilities = model.predict_proba(x_test)[:, 1]

        window_bets = 0
        window_wins = 0
        window_profit = 0.0

        for row_index, (_, row) in enumerate(test_df.iterrows()):
            probability = float(probabilities[row_index])

            if probability >= 0.5:
                predicted_label = positive_label
                confidence = probability
            else:
                predicted_label = negative_label
                confidence = 1 - probability

            if confidence < min_confidence:
                continue

            odds = _find_odds(
                session=session,
                match_id=int(row["match_id"]),
                market=market,
                selection=predicted_label,
            )

            implied_probability = None
            value_score = None

            if odds is not None:
                implied_probability = round(1 / odds, 4)
                value_score = round(confidence - implied_probability, 4)

            if use_only_matches_with_odds and odds is None:
                continue

            if value_score is not None and value_score < min_edge:
                continue

            safe_odds = odds if odds is not None else 2.0

            won = is_prediction_correct(
                predicted_label=predicted_label,
                home_goals=int(row["home_goals"]),
                away_goals=int(row["away_goals"]),
            )

            profit = _calculate_profit(
                won=won,
                odds=safe_odds,
                stake=stake,
            )

            bankroll += profit
            total_staked += stake
            total_profit += profit
            window_profit += profit
            window_bets += 1

            if won:
                wins += 1
                window_wins += 1
            else:
                losses += 1

            bets.append(
                HistoricalBet(
                    match_id=int(row["match_id"]),
                    league=str(row["league"]),
                    home_team=str(row["home_team"]),
                    away_team=str(row["away_team"]),
                    market=market,
                    predicted_label=predicted_label,
                    confidence=round(confidence, 4),
                    odds=round(safe_odds, 4),
                    implied_probability=implied_probability,
                    value_score=value_score,
                    won=won,
                    profit=round(profit, 2),
                    bankroll_after_bet=round(bankroll, 2),
                )
            )

        windows.append(
            {
                "train_size": len(train_df),
                "test_size": len(test_df),
                "test_start": str(test_df["kickoff_date"].min()),
                "test_end": str(test_df["kickoff_date"].max()),
                "bets": window_bets,
                "wins": window_wins,
                "hit_rate": round(window_wins / window_bets, 4)
                if window_bets
                else 0.0,
                "profit": round(window_profit, 2),
            }
        )

        start_test_index += test_window_size

    total_bets = len(bets)
    hit_rate = wins / total_bets if total_bets else 0.0
    roi = total_profit / total_staked if total_staked else 0.0

    return {
        "summary": {
            "market": market,
            "initial_train_size": initial_train_size,
            "test_window_size": test_window_size,
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
            "used_only_matches_with_odds": use_only_matches_with_odds,
            "note": "If odds were missing, fallback odds of 2.0 were used unless use_only_matches_with_odds=True.",
        },
        "windows": windows,
        "bets": [bet.__dict__ for bet in bets],
    }


def _build_model():
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                ),
            ),
        ]
    )


def _calculate_profit(
    won: bool,
    odds: float,
    stake: float,
) -> float:
    if won:
        return (stake * odds) - stake

    return -stake


def _find_odds(
    session: Session,
    match_id: int,
    market: str,
    selection: str,
) -> float | None:
    query = text(
        """
        SELECT odds
        FROM match_odds
        WHERE match_id = :match_id
          AND market = :market
          AND selection = :selection
        ORDER BY retrieved_at DESC
        LIMIT 1
        """
    )

    value = session.execute(
        query,
        {
            "match_id": match_id,
            "market": market,
            "selection": selection,
        },
    ).scalar()

    if value is None:
        return None

    return float(value)