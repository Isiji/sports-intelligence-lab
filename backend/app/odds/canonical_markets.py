from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalMarket:
    key: str
    label: str
    family: str
    requires_line: bool = False
    enabled_by_default: bool = True


CANONICAL_MARKETS: dict[str, CanonicalMarket] = {
    "home_win": CanonicalMarket("home_win", "Home Win", "match_winner"),
    "draw": CanonicalMarket("draw", "Draw", "match_winner"),
    "away_win": CanonicalMarket("away_win", "Away Win", "match_winner"),

    "double_chance_1x": CanonicalMarket("double_chance_1x", "Double Chance 1X", "double_chance"),
    "double_chance_x2": CanonicalMarket("double_chance_x2", "Double Chance X2", "double_chance"),
    "double_chance_12": CanonicalMarket("double_chance_12", "Double Chance 12", "double_chance"),

    "btts_yes": CanonicalMarket("btts_yes", "BTTS Yes", "btts"),
    "btts_no": CanonicalMarket("btts_no", "BTTS No", "btts"),

    "over_1_5_goals": CanonicalMarket("over_1_5_goals", "Over 1.5 Goals", "goals_total", True),
    "under_1_5_goals": CanonicalMarket("under_1_5_goals", "Under 1.5 Goals", "goals_total", True),
    "over_2_5_goals": CanonicalMarket("over_2_5_goals", "Over 2.5 Goals", "goals_total", True),
    "under_2_5_goals": CanonicalMarket("under_2_5_goals", "Under 2.5 Goals", "goals_total", True),
    "over_3_5_goals": CanonicalMarket("over_3_5_goals", "Over 3.5 Goals", "goals_total", True),
    "under_3_5_goals": CanonicalMarket("under_3_5_goals", "Under 3.5 Goals", "goals_total", True),
}


def is_supported_market(market: str) -> bool:
    return market in CANONICAL_MARKETS


def supported_market_keys() -> list[str]:
    return sorted(CANONICAL_MARKETS.keys())