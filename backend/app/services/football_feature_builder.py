import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import FootballFeatureSnapshot
from app.features.football_features import _add_targets, feature_columns
from app.features.rolling_feature_engine import build_rolling_features

def build_football_feature_cache(session: Session) -> dict:
    query = text("""
        SELECT
            m.id AS match_id,
            m.kickoff_date,
            m.league,
            m.home_team,
            m.away_team,
            m.home_team_id,
            m.away_team_id,
            m.home_goals,
            m.away_goals,
            m.has_stats,

            COALESCE(hs.shots_on_target, 0) AS home_sot,
            COALESCE(hs.corners, 0) AS home_corners,
            COALESCE(hs.possession, 0) AS home_possession,
            COALESCE(hs.fouls, 0) AS home_fouls,
            COALESCE(hs.cards, 0) AS home_cards,
            COALESCE(hs.keeper_saves, 0) AS home_keeper_saves,

            COALESCE(as1.shots_on_target, 0) AS away_sot,
            COALESCE(as1.corners, 0) AS away_corners,
            COALESCE(as1.possession, 0) AS away_possession,
            COALESCE(as1.fouls, 0) AS away_fouls,
            COALESCE(as1.cards, 0) AS away_cards,
            COALESCE(as1.keeper_saves, 0) AS away_keeper_saves

        FROM matches m
        LEFT JOIN team_match_stats hs ON hs.match_id = m.id AND hs.is_home = 1
        LEFT JOIN team_match_stats as1 ON as1.match_id = m.id AND as1.is_home = 0
        WHERE m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
        ORDER BY m.kickoff_date ASC, m.id ASC
    """)

    df = pd.read_sql(query, session.bind)

    if df.empty:
        return {"processed": 0}

    df["kickoff_date"] = pd.to_datetime(df["kickoff_date"])
    
    df = build_rolling_features(df)

    for col in feature_columns():
        if col not in df.columns:
            df[col] = 0.0

    df = _add_targets(df)

    session.query(FootballFeatureSnapshot).delete()
    session.flush()

    inserted = 0

    for _, row in df.iterrows():
        payload = {}

        for col in feature_columns():
            payload[col] = float(row.get(col, 0.0) or 0.0)

        for target_col in [
            "target_home_win",
            "target_away_win",
            "target_draw",
            "target_double_chance_1x",
            "target_double_chance_x2",
            "target_double_chance_12",
            "target_over_1_5",
            "target_under_1_5",
            "target_over_2_5",
            "target_under_2_5",
            "target_over_3_5",
            "target_under_3_5",
            "target_btts_yes",
            "target_btts_no",
            "target_home_over_0_5",
            "target_away_over_0_5",
            "target_home_clean_sheet",
            "target_away_clean_sheet",
            "target_corners_over_8_5",
            "target_sot_over_8_5",
        ]:
            payload[target_col] = int(row.get(target_col, 0) or 0)

        session.add(
            FootballFeatureSnapshot(
                match_id=int(row["match_id"]),
                features_json=payload,
            )
        )

        inserted += 1

        if inserted % 2000 == 0:
            session.flush()
            print(f"cached {inserted} feature rows")

    session.commit()

    return {
        "processed": inserted,
        "message": "fast feature cache built",
    }