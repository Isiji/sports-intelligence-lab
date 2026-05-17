# backend/app/backtest/settlement_engine.py

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettlementResult:
    status: str
    reason: str


def resolve_prediction_result(
    *,
    predicted_label: str,
    home_goals: int,
    away_goals: int,
) -> SettlementResult:
    label = predicted_label.upper().strip()

    home_win = home_goals > away_goals
    away_win = away_goals > home_goals
    draw = home_goals == away_goals

    total_goals = home_goals + away_goals

    btts_yes = home_goals > 0 and away_goals > 0
    btts_no = not btts_yes

    mapping = {
        "HOME_WIN": home_win,
        "AWAY_WIN": away_win,
        "DRAW": draw,

        "DOUBLE_CHANCE_1X": home_win or draw,
        "DOUBLE_CHANCE_X2": away_win or draw,
        "DOUBLE_CHANCE_12": home_win or away_win,

        "BTTS_YES": btts_yes,
        "BTTS_NO": btts_no,

        "OVER_1_5": total_goals > 1.5,
        "UNDER_1_5": total_goals < 1.5,

        "OVER_2_5": total_goals > 2.5,
        "UNDER_2_5": total_goals < 2.5,

        "OVER_3_5": total_goals > 3.5,
        "UNDER_3_5": total_goals < 3.5,

        "HOME_OVER_0_5": home_goals >= 1,
        "AWAY_OVER_0_5": away_goals >= 1,

        "HOME_CLEAN_SHEET": away_goals == 0,
        "AWAY_CLEAN_SHEET": home_goals == 0,
    }

    if label.startswith("ASIAN_HANDICAP_"):
        return _resolve_asian_handicap(
            label=label,
            home_goals=home_goals,
            away_goals=away_goals,
        )

    if label.startswith("NOT_"):
        base = label.replace("NOT_", "", 1)

        outcome = mapping.get(base)

        if outcome is None:
            return SettlementResult(
                status="VOID",
                reason=f"Unknown label: {label}",
            )

        return SettlementResult(
            status="WON" if not outcome else "LOST",
            reason=f"Inverted outcome for {label}",
        )

    outcome = mapping.get(label)

    if outcome is None:
        return SettlementResult(
            status="VOID",
            reason=f"Unknown label: {label}",
        )

    return SettlementResult(
        status="WON" if outcome else "LOST",
        reason=f"Resolved {label}",
    )


def _resolve_asian_handicap(
    *,
    label: str,
    home_goals: int,
    away_goals: int,
) -> SettlementResult:
    raw = label.replace("ASIAN_HANDICAP_", "")

    side, handicap = raw.rsplit("_", 1)

    handicap = handicap.replace("PLUS_", "+")
    handicap = handicap.replace("MINUS_", "-")
    handicap = handicap.replace("_", ".")

    try:
        handicap_value = float(handicap)
    except ValueError:
        return SettlementResult(
            status="VOID",
            reason=f"Invalid handicap format: {label}",
        )

    goal_difference = home_goals - away_goals

    if side == "HOME":
        adjusted = goal_difference + handicap_value
    else:
        adjusted = (-goal_difference) + handicap_value

    if adjusted > 0:
        return SettlementResult(
            status="WON",
            reason=f"Asian handicap won: {label}",
        )

    if adjusted == 0:
        return SettlementResult(
            status="PUSH",
            reason=f"Asian handicap push: {label}",
        )

    return SettlementResult(
        status="LOST",
        reason=f"Asian handicap lost: {label}",
    )