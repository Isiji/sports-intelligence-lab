# backend/app/intelligence/correlation_rules.py

from dataclasses import dataclass


@dataclass
class CorrelationResult:
    allowed: bool
    correlation_score: float
    reasons: list[str]


HIGH_CORRELATION_MARKETS = {
    frozenset({"btts_yes", "over_2_5_goals"}),
    frozenset({"home_win", "over_1_5_goals"}),
    frozenset({"away_win", "over_1_5_goals"}),
    frozenset({"under_2_5_goals", "btts_no"}),
    frozenset({"under_1_5_goals", "btts_no"}),
}


NEGATIVE_DIVERSIFICATION_MARKETS = {
    frozenset({"over_2_5_goals", "under_2_5_goals"}),
    frozenset({"home_win", "away_win"}),
    frozenset({"btts_yes", "btts_no"}),
}


def evaluate_group_correlation(
    existing_group: list[dict],
    candidate: dict,
) -> CorrelationResult:
    reasons: list[str] = []

    score = 0.0

    candidate_market = candidate["market"]

    candidate_home = candidate.get("home_team")
    candidate_away = candidate.get("away_team")

    candidate_league = candidate.get("league")

    for item in existing_group:
        existing_market = item["market"]

        existing_home = item.get("home_team")
        existing_away = item.get("away_team")

        existing_league = item.get("league")

        pair = frozenset({
            candidate_market,
            existing_market,
        })

        if pair in HIGH_CORRELATION_MARKETS:
            score += 35
            reasons.append(
                f"HIGH_MARKET_CORRELATION:{candidate_market}:{existing_market}"
            )

        if pair in NEGATIVE_DIVERSIFICATION_MARKETS:
            score += 50
            reasons.append(
                f"NEGATIVE_DIVERSIFICATION:{candidate_market}:{existing_market}"
            )

        same_team_exposure = (
            candidate_home in {existing_home, existing_away}
            or candidate_away in {existing_home, existing_away}
        )

        if same_team_exposure:
            score += 45
            reasons.append(
                "SAME_TEAM_EXPOSURE"
            )

        if candidate_league == existing_league:
            score += 10
            reasons.append(
                "LEAGUE_CONCENTRATION"
            )

    allowed = score < 50

    return CorrelationResult(
        allowed=allowed,
        correlation_score=score,
        reasons=reasons,
    )