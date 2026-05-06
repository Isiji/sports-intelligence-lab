# backend/app/reports/match_report.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def search_matches(session: Session, query: str, limit: int = 20) -> list[dict]:
    q = f"%{query.lower().strip()}%"

    sql = text(
        """
        SELECT
            m.id AS match_id,
            m.kickoff_date,
            m.league,
            m.home_team,
            m.away_team,
            m.home_goals,
            m.away_goals,
            m.status,
            m.is_finished,
            m.has_stats,
            m.has_odds,
            COALESCE(c.name, m.league) AS competition,
            COALESCE(co.name, 'Unknown') AS country
        FROM matches m
        LEFT JOIN competitions c ON c.id = m.competition_id
        LEFT JOIN countries co ON co.id = c.country_id
        WHERE
            LOWER(m.home_team) LIKE :q
            OR LOWER(m.away_team) LIKE :q
            OR LOWER(m.league) LIKE :q
            OR LOWER(COALESCE(c.name, '')) LIKE :q
        ORDER BY m.kickoff_date DESC
        LIMIT :limit
        """
    )

    rows = session.execute(sql, {"q": q, "limit": limit}).mappings().all()
    return [dict(row) for row in rows]


def build_match_report(session: Session, match_id: int) -> dict:
    match_sql = text(
        """
        SELECT
            m.id AS match_id,
            m.kickoff_date,
            m.kickoff_datetime,
            m.league,
            m.home_team,
            m.away_team,
            m.home_goals,
            m.away_goals,
            m.status,
            m.round_name,
            m.is_finished,
            m.is_postponed,
            m.is_cancelled,
            m.has_stats,
            m.has_odds,
            COALESCE(c.name, m.league) AS competition,
            COALESCE(co.name, 'Unknown') AS country
        FROM matches m
        LEFT JOIN competitions c ON c.id = m.competition_id
        LEFT JOIN countries co ON co.id = c.country_id
        WHERE m.id = :match_id
        """
    )

    match = session.execute(match_sql, {"match_id": match_id}).mappings().first()

    if not match:
        raise ValueError("Match not found.")

    predictions = _match_predictions(session, match_id)
    stats = _match_stats(session, match_id)
    odds = _match_odds(session, match_id)
    h2h = _head_to_head(session, dict(match))
    recent_form = _recent_form(session, dict(match))

    return {
        "match": dict(match),
        "predictions": predictions,
        "best_prediction": _best_prediction(predictions),
        "team_stats": stats,
        "odds": odds,
        "head_to_head": h2h,
        "recent_form": recent_form,
        "reliability_notes": _reliability_notes(dict(match), predictions),
    }


def _match_predictions(session: Session, match_id: int) -> list[dict]:
    sql = text(
        """
        SELECT
            p.id AS prediction_id,
            p.slate,
            p.market,
            p.predicted_label,
            p.confidence,
            p.odds,
            p.implied_probability,
            p.value_score,
            p.created_at,
            CASE
                WHEN m.home_goals IS NULL OR m.away_goals IS NULL THEN 'PENDING'

                WHEN p.market = 'home_win'
                    THEN CASE WHEN (p.predicted_label = 'HOME_WIN') = (m.home_goals > m.away_goals)
                        THEN 'CORRECT' ELSE 'WRONG' END

                WHEN p.market = 'away_win'
                    THEN CASE WHEN (p.predicted_label = 'AWAY_WIN') = (m.away_goals > m.home_goals)
                        THEN 'CORRECT' ELSE 'WRONG' END

                WHEN p.market = 'draw'
                    THEN CASE WHEN (p.predicted_label = 'DRAW') = (m.home_goals = m.away_goals)
                        THEN 'CORRECT' ELSE 'WRONG' END

                WHEN p.market = 'double_chance_1x'
                    THEN CASE WHEN (p.predicted_label = 'DOUBLE_CHANCE_1X') = (m.home_goals >= m.away_goals)
                        THEN 'CORRECT' ELSE 'WRONG' END

                WHEN p.market = 'double_chance_x2'
                    THEN CASE WHEN (p.predicted_label = 'DOUBLE_CHANCE_X2') = (m.away_goals >= m.home_goals)
                        THEN 'CORRECT' ELSE 'WRONG' END

                WHEN p.market = 'double_chance_12'
                    THEN CASE WHEN (p.predicted_label = 'DOUBLE_CHANCE_12') = (m.home_goals != m.away_goals)
                        THEN 'CORRECT' ELSE 'WRONG' END

                WHEN p.market = 'over_2_5_goals'
                    THEN CASE WHEN (p.predicted_label = 'OVER_2_5') = ((m.home_goals + m.away_goals) > 2.5)
                        THEN 'CORRECT' ELSE 'WRONG' END

                WHEN p.market = 'under_2_5_goals'
                    THEN CASE WHEN (p.predicted_label = 'UNDER_2_5') = ((m.home_goals + m.away_goals) <= 2.5)
                        THEN 'CORRECT' ELSE 'WRONG' END

                WHEN p.market = 'btts_yes'
                    THEN CASE WHEN (p.predicted_label = 'BTTS_YES') = (m.home_goals > 0 AND m.away_goals > 0)
                        THEN 'CORRECT' ELSE 'WRONG' END

                WHEN p.market = 'btts_no'
                    THEN CASE WHEN (p.predicted_label = 'BTTS_NO') = (m.home_goals = 0 OR m.away_goals = 0)
                        THEN 'CORRECT' ELSE 'WRONG' END

                ELSE 'UNSUPPORTED_SETTLEMENT'
            END AS outcome_status
        FROM predictions p
        JOIN matches m ON m.id = p.match_id
        WHERE p.match_id = :match_id
        ORDER BY p.confidence DESC, p.value_score DESC NULLS LAST
        """
    )

    rows = session.execute(sql, {"match_id": match_id}).mappings().all()
    return [dict(row) for row in rows]


def _match_stats(session: Session, match_id: int) -> list[dict]:
    sql = text(
        """
        SELECT
            team,
            is_home,
            goals,
            corners,
            shots_on_target,
            possession,
            fouls,
            cards,
            keeper_saves
        FROM team_match_stats
        WHERE match_id = :match_id
        ORDER BY is_home DESC
        """
    )

    rows = session.execute(sql, {"match_id": match_id}).mappings().all()
    return [dict(row) for row in rows]


def _match_odds(session: Session, match_id: int) -> list[dict]:
    sql = text(
        """
        SELECT
            provider,
            bookmaker,
            market,
            selection,
            odds,
            retrieved_at
        FROM match_odds
        WHERE match_id = :match_id
        ORDER BY market, odds DESC
        """
    )

    rows = session.execute(sql, {"match_id": match_id}).mappings().all()
    return [dict(row) for row in rows]


def _head_to_head(session: Session, match: dict, limit: int = 10) -> list[dict]:
    sql = text(
        """
        SELECT
            id AS match_id,
            kickoff_date,
            league,
            home_team,
            away_team,
            home_goals,
            away_goals,
            status
        FROM matches
        WHERE
            id != :match_id
            AND home_goals IS NOT NULL
            AND away_goals IS NOT NULL
            AND (
                (home_team = :home_team AND away_team = :away_team)
                OR
                (home_team = :away_team AND away_team = :home_team)
            )
        ORDER BY kickoff_date DESC
        LIMIT :limit
        """
    )

    rows = session.execute(
        sql,
        {
            "match_id": match["match_id"],
            "home_team": match["home_team"],
            "away_team": match["away_team"],
            "limit": limit,
        },
    ).mappings().all()

    return [dict(row) for row in rows]


def _recent_form(session: Session, match: dict, limit: int = 8) -> dict:
    return {
        "home_team": _team_recent_matches(
            session=session,
            team=match["home_team"],
            before_date=match["kickoff_date"],
            limit=limit,
        ),
        "away_team": _team_recent_matches(
            session=session,
            team=match["away_team"],
            before_date=match["kickoff_date"],
            limit=limit,
        ),
    }


def _team_recent_matches(
    session: Session,
    team: str,
    before_date,
    limit: int,
) -> list[dict]:
    sql = text(
        """
        SELECT
            id AS match_id,
            kickoff_date,
            league,
            home_team,
            away_team,
            home_goals,
            away_goals,
            CASE
                WHEN home_team = :team AND home_goals > away_goals THEN 'W'
                WHEN away_team = :team AND away_goals > home_goals THEN 'W'
                WHEN home_goals = away_goals THEN 'D'
                ELSE 'L'
            END AS result
        FROM matches
        WHERE
            kickoff_date < :before_date
            AND home_goals IS NOT NULL
            AND away_goals IS NOT NULL
            AND (home_team = :team OR away_team = :team)
        ORDER BY kickoff_date DESC
        LIMIT :limit
        """
    )

    rows = session.execute(
        sql,
        {
            "team": team,
            "before_date": before_date,
            "limit": limit,
        },
    ).mappings().all()

    return [dict(row) for row in rows]


def _best_prediction(predictions: list[dict]) -> dict | None:
    if not predictions:
        return None

    return sorted(
        predictions,
        key=lambda row: (
            float(row.get("value_score") or 0),
            float(row.get("confidence") or 0),
        ),
        reverse=True,
    )[0]


def _reliability_notes(match: dict, predictions: list[dict]) -> list[str]:
    notes = []

    if not predictions:
        notes.append("No predictions have been generated for this match yet.")

    if not match.get("has_stats"):
        notes.append(
            "Real match statistics are not available yet, so corners and shots-on-target markets may be less reliable."
        )

    if not match.get("has_odds"):
        notes.append(
            "Odds are not available yet, so value-score analysis may be missing or limited."
        )

    if match.get("is_finished"):
        notes.append("This match is finished, so predictions can be settled against the final result.")
    else:
        notes.append("This match is not finished yet, so prediction outcomes are still pending.")

    return notes