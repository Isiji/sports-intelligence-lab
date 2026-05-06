# backend/app/analysis/match_analysis.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_match_analysis(
    session: Session,
    match_id: int,
    slate: str = "demo",
):
    match_query = text(
        """
        SELECT
            m.id,
            m.league,
            m.kickoff_date,
            m.home_team,
            m.away_team,
            m.home_goals,
            m.away_goals,

            hs.shots_on_target AS home_sot,
            hs.corners AS home_corners,
            hs.possession AS home_possession,

            as1.shots_on_target AS away_sot,
            as1.corners AS away_corners,
            as1.possession AS away_possession

        FROM matches m

        JOIN team_match_stats hs
            ON hs.match_id = m.id
           AND hs.is_home = 1

        JOIN team_match_stats as1
            ON as1.match_id = m.id
           AND as1.is_home = 0

        WHERE m.id = :match_id
        """
    )

    match_row = session.execute(
        match_query,
        {"match_id": match_id},
    ).mappings().first()

    if not match_row:
        return None

    predictions_query = text(
        """
        SELECT
            p.market,
            p.predicted_label,
            p.confidence,
            p.odds,
            p.implied_probability,
            p.value_score,
            p.model_name

        FROM predictions p

        WHERE p.match_id = :match_id
          AND p.slate = :slate

        ORDER BY
            p.confidence DESC,
            p.value_score DESC NULLS LAST
        """
    )

    prediction_rows = session.execute(
        predictions_query,
        {
            "match_id": match_id,
            "slate": slate,
        },
    ).mappings().all()

    predictions = [dict(row) for row in prediction_rows]

    best_prediction = None

    if predictions:
        best_prediction = sorted(
            predictions,
            key=lambda item: (
                item.get("value_score") or 0,
                item["confidence"],
            ),
            reverse=True,
        )[0]

    home_form = _team_form(
        session=session,
        team=match_row["home_team"],
    )

    away_form = _team_form(
        session=session,
        team=match_row["away_team"],
    )

    h2h = _head_to_head(
        session=session,
        home_team=match_row["home_team"],
        away_team=match_row["away_team"],
    )

    risk_level = _risk_level(predictions)

    return {
        "match": dict(match_row),
        "best_prediction": best_prediction,
        "predictions": predictions,
        "home_form": home_form,
        "away_form": away_form,
        "head_to_head": h2h,
        "risk_level": risk_level,
    }


def _team_form(
    session: Session,
    team: str,
):
    query = text(
        """
        SELECT
            home_team,
            away_team,
            home_goals,
            away_goals,
            kickoff_date

        FROM matches

        WHERE (
            home_team = :team
            OR away_team = :team
        )
          AND home_goals IS NOT NULL
          AND away_goals IS NOT NULL

        ORDER BY kickoff_date DESC
        LIMIT 5
        """
    )

    rows = session.execute(
        query,
        {"team": team},
    ).mappings().all()

    games = []

    wins = 0
    draws = 0
    losses = 0

    goals_for = 0
    goals_against = 0

    for row in rows:
        is_home = row["home_team"] == team

        gf = row["home_goals"] if is_home else row["away_goals"]
        ga = row["away_goals"] if is_home else row["home_goals"]

        goals_for += gf
        goals_against += ga

        if gf > ga:
            result = "W"
            wins += 1
        elif gf < ga:
            result = "L"
            losses += 1
        else:
            result = "D"
            draws += 1

        games.append(
            {
                "opponent": (
                    row["away_team"]
                    if is_home
                    else row["home_team"]
                ),
                "result": result,
                "goals_for": gf,
                "goals_against": ga,
                "kickoff_date": row["kickoff_date"],
            }
        )

    total_games = max(len(rows), 1)

    return {
        "team": team,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for_avg": round(goals_for / total_games, 2),
        "goals_against_avg": round(goals_against / total_games, 2),
        "recent_games": games,
    }


def _head_to_head(
    session: Session,
    home_team: str,
    away_team: str,
):
    query = text(
        """
        SELECT
            home_team,
            away_team,
            home_goals,
            away_goals,
            kickoff_date

        FROM matches

        WHERE (
            (home_team = :home_team AND away_team = :away_team)
            OR
            (home_team = :away_team AND away_team = :home_team)
        )
          AND home_goals IS NOT NULL
          AND away_goals IS NOT NULL

        ORDER BY kickoff_date DESC
        LIMIT 10
        """
    )

    rows = session.execute(
        query,
        {
            "home_team": home_team,
            "away_team": away_team,
        },
    ).mappings().all()

    home_wins = 0
    away_wins = 0
    draws = 0

    total_goals = 0

    games = []

    for row in rows:
        hg = row["home_goals"]
        ag = row["away_goals"]

        total_goals += hg + ag

        if row["home_team"] == home_team:
            if hg > ag:
                home_wins += 1
            elif ag > hg:
                away_wins += 1
            else:
                draws += 1
        else:
            if ag > hg:
                home_wins += 1
            elif hg > ag:
                away_wins += 1
            else:
                draws += 1

        games.append(dict(row))

    total_games = max(len(rows), 1)

    return {
        "games_played": len(rows),
        "home_team_wins": home_wins,
        "away_team_wins": away_wins,
        "draws": draws,
        "average_goals": round(total_goals / total_games, 2),
        "recent_games": games,
    }


def _risk_level(predictions: list[dict]) -> str:
    if not predictions:
        return "UNKNOWN"

    avg_confidence = (
        sum(p["confidence"] for p in predictions)
        / len(predictions)
    )

    if avg_confidence >= 0.80:
        return "LOW"

    if avg_confidence >= 0.68:
        return "MEDIUM"

    return "HIGH"