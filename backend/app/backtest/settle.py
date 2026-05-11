from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    BacktestRun,
    DynamicLeagueTier,
    LeagueIntelligenceSnapshot,
    Match,
    Prediction,
    PredictionOutcome,
)
from app.services.intelligence_rebuilder import (
    rebuild_confidence_band_intelligence,
    rebuild_league_intelligence,
    rebuild_league_market_intelligence,
    rebuild_market_intelligence,
    rebuild_odds_band_intelligence,
)


def settle_and_score(
    session: Session,
    slate: str,
) -> BacktestRun:
    predictions = list(
        session.scalars(
            select(Prediction).where(
                Prediction.slate == slate
            )
        )
    )

    if not predictions:
        raise ValueError(
            f"No predictions found for slate '{slate}'."
        )

    session.execute(
        delete(PredictionOutcome).where(
            PredictionOutcome.slate == slate
        )
    )

    correct = 0
    settled = 0

    model_name = predictions[0].model_name

    for prediction in predictions:
        match = session.get(
            Match,
            prediction.match_id,
        )

        if not match:
            continue

        if (
            match.home_goals is None
            or match.away_goals is None
        ):
            continue

        settled += 1

        won = is_prediction_correct(
            predicted_label=prediction.predicted_label,
            home_goals=match.home_goals,
            away_goals=match.away_goals,
        )

        if won:
            correct += 1

        profit = 0.0

        if prediction.odds:
            if won:
                profit = prediction.odds - 1
            else:
                profit = -1

        session.add(
            PredictionOutcome(
                prediction_id=prediction.id,
                match_id=prediction.match_id,
                slate=prediction.slate,
                league=match.league,
                market=prediction.market,
                predicted_label=prediction.predicted_label,
                confidence=prediction.confidence,
                odds=prediction.odds,
                implied_probability=prediction.implied_probability,
                value_score=prediction.value_score,
                won=won,
                profit=profit,
                settled_at=datetime.utcnow(),
            )
        )

    overall_accuracy = (
        correct / settled
        if settled
        else 0.0
    )

    run = BacktestRun(
        slate=slate,
        model_name=model_name,
        overall_accuracy=round(
            overall_accuracy,
            4,
        ),
        settled_predictions=settled,
    )

    session.add(run)

    session.commit()

    _rebuild_live_intelligence(session)

    rebuild_dynamic_league_tiers(session)

    session.refresh(run)

    return run


def rebuild_dynamic_league_tiers(
    session: Session,
):
    session.execute(
        delete(DynamicLeagueTier)
    )

    rows = list(
        session.scalars(
            select(LeagueIntelligenceSnapshot)
        )
    )

    for row in rows:
        score = float(
            row.survivability_score or 0
        )

        if score >= 45:
            tier = "VERY_STRONG"
        elif score >= 20:
            tier = "STRONG"
        else:
            tier = "WEAK"

        session.add(
            DynamicLeagueTier(
                league=row.league,
                tier=tier,
                strength_score=score,
                profitability_score=float(
                    row.roi or 0
                ),
                stats_quality_score=float(
                    row.stats_quality_score or 0
                ),
                odds_quality_score=float(
                    row.avg_odds or 0
                ),
                survivability_score=score,
                prediction_count=int(
                    row.bets or 0
                ),
            )
        )

    session.commit()


def _rebuild_live_intelligence(
    session: Session,
):
    run_tag = "live_predictions"

    rebuild_market_intelligence(
        session=session,
        run_tag=run_tag,
    )

    rebuild_league_intelligence(
        session=session,
        run_tag=run_tag,
    )

    rebuild_league_market_intelligence(
        session=session,
        run_tag=run_tag,
    )

    rebuild_odds_band_intelligence(
        session=session,
        run_tag=run_tag,
    )

    rebuild_confidence_band_intelligence(
        session=session,
        run_tag=run_tag,
    )


def normalize_label(label: str) -> str:
    return (
        label.strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
        .replace(".", "_")
    )


def is_prediction_correct(
    predicted_label: str,
    home_goals: int,
    away_goals: int,
):
    label = normalize_label(
        predicted_label
    )

    total_goals = (
        home_goals + away_goals
    )

    if label == "HOME_WIN":
        return home_goals > away_goals

    if label == "AWAY_WIN":
        return away_goals > home_goals

    if label == "DRAW":
        return home_goals == away_goals

    if label == "DOUBLE_CHANCE_1X":
        return home_goals >= away_goals

    if label == "DOUBLE_CHANCE_X2":
        return away_goals >= home_goals

    if label == "DOUBLE_CHANCE_12":
        return home_goals != away_goals

    if "OVER_1_5" in label:
        return total_goals > 1.5

    if "UNDER_1_5" in label:
        return total_goals < 1.5

    if "OVER_2_5" in label:
        return total_goals > 2.5

    if "UNDER_2_5" in label:
        return total_goals < 2.5

    if "OVER_3_5" in label:
        return total_goals > 3.5

    if "UNDER_3_5" in label:
        return total_goals < 3.5

    if label == "BTTS_YES":
        return (
            home_goals > 0
            and away_goals > 0
        )

    if label == "BTTS_NO":
        return (
            home_goals == 0
            or away_goals == 0
        )

    return False