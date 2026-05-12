# backend/app/odds/canonical_markets.py

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalMarket:
    key: str
    label: str
    family: str
    requires_line: bool = False
    enabled_by_default: bool = True


CANONICAL_MARKETS: dict[str, CanonicalMarket] = {
    # Match result
    "home_win": CanonicalMarket("home_win", "Home Win", "match_winner"),
    "draw": CanonicalMarket("draw", "Draw", "match_winner"),
    "away_win": CanonicalMarket("away_win", "Away Win", "match_winner"),

    # Double chance
    "double_chance_1x": CanonicalMarket("double_chance_1x", "Double Chance 1X", "double_chance"),
    "double_chance_x2": CanonicalMarket("double_chance_x2", "Double Chance X2", "double_chance"),
    "double_chance_12": CanonicalMarket("double_chance_12", "Double Chance 12", "double_chance"),

    # Draw no bet
    "draw_no_bet_home": CanonicalMarket("draw_no_bet_home", "Draw No Bet Home", "draw_no_bet"),
    "draw_no_bet_away": CanonicalMarket("draw_no_bet_away", "Draw No Bet Away", "draw_no_bet"),

    # BTTS
    "btts_yes": CanonicalMarket("btts_yes", "BTTS Yes", "btts"),
    "btts_no": CanonicalMarket("btts_no", "BTTS No", "btts"),
}


def _add_goal_totals() -> None:
    for line in ["0_5", "1_5", "2_5", "3_5", "4_5", "5_5"]:
        pretty = line.replace("_", ".")
        CANONICAL_MARKETS[f"over_{line}_goals"] = CanonicalMarket(
            f"over_{line}_goals", f"Over {pretty} Goals", "goals_total", True
        )
        CANONICAL_MARKETS[f"under_{line}_goals"] = CanonicalMarket(
            f"under_{line}_goals", f"Under {pretty} Goals", "goals_total", True
        )


def _add_team_totals() -> None:
    for side, label in [("home", "Home"), ("away", "Away")]:
        for line in ["0_5", "1_5", "2_5", "3_5"]:
            pretty = line.replace("_", ".")
            CANONICAL_MARKETS[f"{side}_over_{line}_goals"] = CanonicalMarket(
                f"{side}_over_{line}_goals",
                f"{label} Over {pretty} Goals",
                "team_goals_total",
                True,
            )
            CANONICAL_MARKETS[f"{side}_under_{line}_goals"] = CanonicalMarket(
                f"{side}_under_{line}_goals",
                f"{label} Under {pretty} Goals",
                "team_goals_total",
                True,
            )


def _add_corners() -> None:
    for line in ["6_5", "7_5", "8_5", "9_5", "10_5", "11_5", "12_5"]:
        pretty = line.replace("_", ".")
        CANONICAL_MARKETS[f"corners_over_{line}"] = CanonicalMarket(
            f"corners_over_{line}", f"Corners Over {pretty}", "corners_total", True
        )
        CANONICAL_MARKETS[f"corners_under_{line}"] = CanonicalMarket(
            f"corners_under_{line}", f"Corners Under {pretty}", "corners_total", True
        )


def _add_shots_on_target() -> None:
    for line in ["5_5", "6_5", "7_5", "8_5", "9_5", "10_5", "11_5"]:
        pretty = line.replace("_", ".")
        CANONICAL_MARKETS[f"shots_on_target_over_{line}"] = CanonicalMarket(
            f"shots_on_target_over_{line}",
            f"Shots On Target Over {pretty}",
            "shots_on_target_total",
            True,
        )
        CANONICAL_MARKETS[f"shots_on_target_under_{line}"] = CanonicalMarket(
            f"shots_on_target_under_{line}",
            f"Shots On Target Under {pretty}",
            "shots_on_target_total",
            True,
        )


def _add_first_half() -> None:
    for line in ["0_5", "1_5", "2_5"]:
        pretty = line.replace("_", ".")
        CANONICAL_MARKETS[f"first_half_over_{line}_goals"] = CanonicalMarket(
            f"first_half_over_{line}_goals",
            f"First Half Over {pretty} Goals",
            "first_half_goals_total",
            True,
        )
        CANONICAL_MARKETS[f"first_half_under_{line}_goals"] = CanonicalMarket(
            f"first_half_under_{line}_goals",
            f"First Half Under {pretty} Goals",
            "first_half_goals_total",
            True,
        )

    CANONICAL_MARKETS["first_half_home_win"] = CanonicalMarket(
        "first_half_home_win", "First Half Home Win", "first_half_result"
    )
    CANONICAL_MARKETS["first_half_draw"] = CanonicalMarket(
        "first_half_draw", "First Half Draw", "first_half_result"
    )
    CANONICAL_MARKETS["first_half_away_win"] = CanonicalMarket(
        "first_half_away_win", "First Half Away Win", "first_half_result"
    )


def _add_asian_handicap() -> None:
    lines = [
        "minus_2_5", "minus_2_25", "minus_2_0", "minus_1_75", "minus_1_5",
        "minus_1_25", "minus_1_0", "minus_0_75", "minus_0_5", "minus_0_25",
        "0_0",
        "plus_0_25", "plus_0_5", "plus_0_75", "plus_1_0", "plus_1_25",
        "plus_1_5", "plus_1_75", "plus_2_0", "plus_2_25", "plus_2_5",
    ]

    for side, label in [("home", "Home"), ("away", "Away")]:
        for line in lines:
            display = (
                line.replace("minus_", "-")
                .replace("plus_", "+")
                .replace("_", ".")
            )
            CANONICAL_MARKETS[f"asian_handicap_{side}_{line}"] = CanonicalMarket(
                f"asian_handicap_{side}_{line}",
                f"Asian Handicap {label} {display}",
                "asian_handicap",
                True,
            )


def _add_ht_ft() -> None:
    outcomes = {
        "home_home": "Home/Home",
        "home_draw": "Home/Draw",
        "home_away": "Home/Away",
        "draw_home": "Draw/Home",
        "draw_draw": "Draw/Draw",
        "draw_away": "Draw/Away",
        "away_home": "Away/Home",
        "away_draw": "Away/Draw",
        "away_away": "Away/Away",
    }

    for key, label in outcomes.items():
        CANONICAL_MARKETS[f"ht_ft_{key}"] = CanonicalMarket(
            f"ht_ft_{key}", f"HT/FT {label}", "ht_ft"
        )


def _add_exact_score() -> None:
    for home in range(0, 5):
        for away in range(0, 5):
            key = f"exact_score_{home}_{away}"
            CANONICAL_MARKETS[key] = CanonicalMarket(
                key, f"Exact Score {home}-{away}", "exact_score"
            )

    CANONICAL_MARKETS["exact_score_other"] = CanonicalMarket(
        "exact_score_other", "Exact Score Other", "exact_score"
    )


_add_goal_totals()
_add_team_totals()
_add_corners()
_add_shots_on_target()
_add_first_half()
_add_asian_handicap()
_add_ht_ft()
_add_exact_score()


def is_supported_market(market: str) -> bool:
    return market in CANONICAL_MARKETS


def get_market_family(market: str) -> str | None:
    item = CANONICAL_MARKETS.get(market)
    return item.family if item else None


def enabled_markets() -> list[str]:
    return [
        key for key, value in CANONICAL_MARKETS.items()
        if value.enabled_by_default
    ]

def supported_market_keys() -> list[str]:
    return sorted(CANONICAL_MARKETS.keys())