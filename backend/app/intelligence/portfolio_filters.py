# backend/app/intelligence/portfolio_filters.py

from dataclasses import dataclass


@dataclass
class PortfolioFilterResult:
    allowed: bool
    reason: str
    risk_flags: list[str]
    risk_score: float


CHAOS_LEAGUES = {
    "Premier League",
    "Bundesliga",
    "League One",
    "Championship",
    "League Two",
    "Ligue 2",
    "Primeira Liga",
    "La Liga",
    "Primera Division",
    "3. Liga",
    "III Liga - Group 3",
    "National 2 - Group A",
}

FAKE_CONFIDENCE_LEAGUES = {
    "First League",
    "2. Division",
    "Liga Nacional",
    "1. Lig",
    "Segunda División",
    "Premiership",
    "Division 1",
    "Primera División RFEF - Group 2",
}

SAFE_LEAGUES = {
    "Serie B",
    "Ekstraklasa",
    "Regionalliga - Ost",
    "1st Division",
    "3. liga - CFL A",
    "4. liga - Divizie E",
    "1. Division",
    "II Liga - East",
}


SAFE_MARKET_CONFIDENCE_ZONES = {
    ("btts_no", "0.90+"),
    ("btts_yes", "0.90+"),
    ("under_2_5_goals", "0.80 - 0.89"),
    ("under_2_5_goals", "0.90+"),
    ("under_3_5_goals", "0.90+"),
    ("home_win", "0.90+"),
    ("double_chance_1x", "0.90+"),
    ("double_chance_12", "0.90+"),
    ("double_chance_x2", "0.60 - 0.69"),
    ("double_chance_x2", "0.80 - 0.89"),
}


BAD_MARKET_CONFIDENCE_ZONES = {
    ("double_chance_x2", "0.90+"),
    ("over_1_5_goals", "0.90+"),
    ("under_3_5_goals", "0.70 - 0.79"),
}


SAFE_MARKET_ODDS_ZONES = {
    ("home_win", "1.50 - 1.79"),
    ("under_2_5_goals", "1.50 - 1.79"),
    ("under_2_5_goals", "1.80 - 2.19"),
    ("under_3_5_goals", "1.00 - 1.29"),
    ("under_3_5_goals", "1.50 - 1.79"),
    ("double_chance_x2", "1.00 - 1.29"),
    ("double_chance_x2", "1.30 - 1.49"),
    ("btts_no", "2.20 - 2.99"),
    ("under_1_5_goals", "3.00 - 4.49"),
}


BAD_MARKET_ODDS_ZONES = {
    ("home_win", "2.20 - 2.99"),
    ("over_2_5_goals", "1.50 - 1.79"),
    ("over_2_5_goals", "1.80 - 2.19"),
    ("btts_yes", "1.80 - 2.19"),
    ("double_chance_1x", "1.00 - 1.29"),
    ("double_chance_12", "1.00 - 1.29"),
    ("over_1_5_goals", "1.00 - 1.29"),
}


def get_odds_band(odds: float | None) -> str:
    if odds is None:
        return "UNKNOWN"

    if odds < 1.30:
        return "1.00 - 1.29"

    if odds < 1.50:
        return "1.30 - 1.49"

    if odds < 1.80:
        return "1.50 - 1.79"

    if odds < 2.20:
        return "1.80 - 2.19"

    if odds < 3.00:
        return "2.20 - 2.99"

    if odds < 4.50:
        return "3.00 - 4.49"

    return "4.50+"


def get_confidence_band(confidence: float | None) -> str:
    if confidence is None:
        return "UNKNOWN"

    if confidence < 0.60:
        return "0.00 - 0.59"

    if confidence < 0.70:
        return "0.60 - 0.69"

    if confidence < 0.80:
        return "0.70 - 0.79"

    if confidence < 0.90:
        return "0.80 - 0.89"

    return "0.90+"


def evaluate_pick_for_portfolio(
    *,
    league: str | None,
    market: str,
    confidence: float | None,
    odds: float | None,
    value_score: float | None = None,
    strict: bool = True,
) -> PortfolioFilterResult:
    risk_flags: list[str] = []
    risk_score = 0.0

    selected_league = league or "UNKNOWN"
    odds_band = get_odds_band(odds)
    confidence_band = get_confidence_band(confidence)

    market_confidence_key = (market, confidence_band)
    market_odds_key = (market, odds_band)

    if selected_league in CHAOS_LEAGUES:
        risk_flags.append("CHAOS_LEAGUE")
        risk_score += 35

    if selected_league in FAKE_CONFIDENCE_LEAGUES:
        risk_flags.append("FAKE_CONFIDENCE_LEAGUE")
        risk_score += 40

    if selected_league in SAFE_LEAGUES:
        risk_flags.append("SAFE_LEAGUE")
        risk_score -= 15

    if market_confidence_key in BAD_MARKET_CONFIDENCE_ZONES:
        risk_flags.append("BAD_MARKET_CONFIDENCE_ZONE")
        risk_score += 35

    if market_odds_key in BAD_MARKET_ODDS_ZONES:
        risk_flags.append("BAD_MARKET_ODDS_ZONE")
        risk_score += 35

    if market_confidence_key in SAFE_MARKET_CONFIDENCE_ZONES:
        risk_flags.append("SAFE_MARKET_CONFIDENCE_ZONE")
        risk_score -= 20

    if market_odds_key in SAFE_MARKET_ODDS_ZONES:
        risk_flags.append("SAFE_MARKET_ODDS_ZONE")
        risk_score -= 20

    if odds is None:
        risk_flags.append("NO_ODDS")
        risk_score += 50

    elif odds > 3.00:
        risk_flags.append("HIGH_ODDS_VARIANCE")
        risk_score += 25

    elif odds < 1.20:
        risk_flags.append("VERY_LOW_ODDS")
        risk_score += 10

    if confidence is None:
        risk_flags.append("NO_CONFIDENCE")
        risk_score += 40

    elif confidence < 0.70:
        risk_flags.append("LOW_CONFIDENCE")
        risk_score += 20

    if value_score is not None:
        if value_score < 0:
            risk_flags.append("NEGATIVE_VALUE_SCORE")
            risk_score += 30
        elif value_score >= 0.20:
            risk_flags.append("STRONG_VALUE_SCORE")
            risk_score -= 10

    if strict:
        if "CHAOS_LEAGUE" in risk_flags:
            return PortfolioFilterResult(False, "Rejected: chaos league", risk_flags, risk_score)

        if "FAKE_CONFIDENCE_LEAGUE" in risk_flags:
            return PortfolioFilterResult(False, "Rejected: fake confidence league", risk_flags, risk_score)

        if "BAD_MARKET_CONFIDENCE_ZONE" in risk_flags:
            return PortfolioFilterResult(False, "Rejected: bad market confidence zone", risk_flags, risk_score)

        if "BAD_MARKET_ODDS_ZONE" in risk_flags:
            return PortfolioFilterResult(False, "Rejected: bad market odds zone", risk_flags, risk_score)

        if odds is None:
            return PortfolioFilterResult(False, "Rejected: missing odds", risk_flags, risk_score)

        if risk_score >= 35:
            return PortfolioFilterResult(False, "Rejected: risk score too high", risk_flags, risk_score)

    return PortfolioFilterResult(True, "Allowed", risk_flags, risk_score)