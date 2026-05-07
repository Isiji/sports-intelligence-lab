# backend/app/features/market_feature_map.py

from app.features.football_features import feature_columns


RESULT_FEATURES = [
    "home_win_rate",
    "away_win_rate",
    "home_goal_diff",
    "away_goal_diff",
    "home_form_score",
    "away_form_score",
    "home_h2h_win_rate",
    "away_h2h_win_rate",
    "home_home_win_rate",
    "away_away_win_rate",
    "home_current_streak",
    "away_current_streak",
    "home_elo",
    "away_elo",
    "elo_diff",
    "home_elo_form",
    "away_elo_form",
    "elo_form_diff",
    "home_attack_elo",
    "away_attack_elo",
    "home_defense_elo",
    "away_defense_elo",
    "attack_defense_diff",
    "team_strength_diff",
    "league_home_win_rate",
    "league_away_win_rate",
    "league_draw_rate",
]

GOAL_FEATURES = [
    "home_goals_for_avg",
    "home_goals_against_avg",
    "away_goals_for_avg",
    "away_goals_against_avg",
    "home_btts_rate",
    "away_btts_rate",
    "home_over_2_5_rate",
    "away_over_2_5_rate",
    "home_clean_sheet_rate",
    "away_clean_sheet_rate",
    "home_failed_to_score_rate",
    "away_failed_to_score_rate",
    "home_attack_elo",
    "away_attack_elo",
    "home_defense_elo",
    "away_defense_elo",
    "attack_defense_diff",
    "team_strength_diff",
    "league_avg_goals",
    "league_btts_rate",
    "league_over_2_5_rate",
    "h2h_avg_goals",
    "h2h_over_2_5_rate",
]

CORNER_FEATURES = [
    "home_corner_avg",
    "away_corner_avg",
    "home_sot_avg",
    "away_sot_avg",
    "home_form_score",
    "away_form_score",
    "home_attack_elo",
    "away_attack_elo",
    "team_strength_diff",
    "league_avg_corners",
    "league_avg_sot",
]

SOT_FEATURES = [
    "home_sot_avg",
    "away_sot_avg",
    "home_corner_avg",
    "away_corner_avg",
    "home_goals_for_avg",
    "away_goals_for_avg",
    "home_attack_elo",
    "away_attack_elo",
    "home_defense_elo",
    "away_defense_elo",
    "attack_defense_diff",
    "team_strength_diff",
    "league_avg_sot",
    "league_avg_goals",
]


MARKET_FEATURES = {
    "home_win": RESULT_FEATURES,
    "away_win": RESULT_FEATURES,
    "draw": RESULT_FEATURES,
    "double_chance_1x": RESULT_FEATURES,
    "double_chance_x2": RESULT_FEATURES,
    "double_chance_12": RESULT_FEATURES,

    "over_1_5_goals": GOAL_FEATURES,
    "under_1_5_goals": GOAL_FEATURES,
    "over_2_5_goals": GOAL_FEATURES,
    "under_2_5_goals": GOAL_FEATURES,
    "over_3_5_goals": GOAL_FEATURES,
    "under_3_5_goals": GOAL_FEATURES,
    "btts_yes": GOAL_FEATURES,
    "btts_no": GOAL_FEATURES,
    "home_over_0_5_goals": GOAL_FEATURES,
    "away_over_0_5_goals": GOAL_FEATURES,
    "home_clean_sheet": GOAL_FEATURES,
    "away_clean_sheet": GOAL_FEATURES,

    "corners_over_8_5": CORNER_FEATURES,
    "shots_on_target_over_8_5": SOT_FEATURES,
}


def feature_columns_for_market(market: str) -> list[str]:
    selected = MARKET_FEATURES.get(market)

    if not selected:
        return feature_columns()

    allowed = set(feature_columns())

    return [
        col
        for col in selected
        if col in allowed
    ]