from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Match, TeamRating


INITIAL_ELO = 1500.0
K_FACTOR = 32.0
HOME_ADVANTAGE = 60.0


def build_elo_ratings(session: Session) -> dict:
    session.query(TeamRating).delete(synchronize_session=False)
    session.flush()

    matches = (
        session.query(Match)
        .filter(
            Match.is_finished == True,
            Match.home_goals.isnot(None),
            Match.away_goals.isnot(None),
            Match.home_team_id.isnot(None),
            Match.away_team_id.isnot(None),
        )
        .order_by(Match.kickoff_date.asc(), Match.id.asc())
        .all()
    )

    processed = 0

    for match in matches:
        process_match_elo(session, match)
        processed += 1

    session.commit()

    return {
        "processed_matches": processed,
        "message": "ELO ratings rebuilt successfully",
    }


def process_match_elo(session: Session, match: Match) -> None:
    home_rating = get_or_create_team_rating(session, match.home_team_id)
    away_rating = get_or_create_team_rating(session, match.away_team_id)

    home_new, away_new = calculate_new_elo(
        home_elo=home_rating.overall_elo,
        away_elo=away_rating.overall_elo,
        home_goals=match.home_goals,
        away_goals=match.away_goals,
    )

    home_attack, away_defense = update_attack_defense(
        attack_rating=home_rating.attack_elo,
        defense_rating=away_rating.defense_elo,
        goals_scored=match.home_goals,
    )

    away_attack, home_defense = update_attack_defense(
        attack_rating=away_rating.attack_elo,
        defense_rating=home_rating.defense_elo,
        goals_scored=match.away_goals,
    )

    update_team_record(
        rating=home_rating,
        new_elo=home_new,
        attack_elo=home_attack,
        defense_elo=home_defense,
        goals_for=match.home_goals,
        goals_against=match.away_goals,
        match_id=match.id,
    )

    update_team_record(
        rating=away_rating,
        new_elo=away_new,
        attack_elo=away_attack,
        defense_elo=away_defense,
        goals_for=match.away_goals,
        goals_against=match.home_goals,
        match_id=match.id,
    )


def get_or_create_team_rating(session: Session, team_id: int) -> TeamRating:
    rating = (
        session.query(TeamRating)
        .filter(TeamRating.team_id == team_id)
        .first()
    )

    if rating:
        return rating

    rating = TeamRating(team_id=team_id)
    session.add(rating)
    session.flush()

    return rating


def calculate_new_elo(
    home_elo: float,
    away_elo: float,
    home_goals: int,
    away_goals: int,
) -> tuple[float, float]:
    adjusted_home = home_elo + HOME_ADVANTAGE

    expected_home = 1 / (1 + 10 ** ((away_elo - adjusted_home) / 400))
    expected_away = 1 - expected_home

    if home_goals > away_goals:
        actual_home = 1.0
    elif home_goals < away_goals:
        actual_home = 0.0
    else:
        actual_home = 0.5

    actual_away = 1 - actual_home

    goal_margin = abs(home_goals - away_goals)
    margin_multiplier = 1 + min(goal_margin, 4) * 0.12

    new_home = home_elo + K_FACTOR * margin_multiplier * (actual_home - expected_home)
    new_away = away_elo + K_FACTOR * margin_multiplier * (actual_away - expected_away)

    return new_home, new_away


def update_attack_defense(
    attack_rating: float,
    defense_rating: float,
    goals_scored: int,
) -> tuple[float, float]:
    expected_goals = 1.35
    performance = goals_scored - expected_goals

    movement = max(min(performance * 10, 24), -24)

    new_attack = attack_rating + movement
    new_defense = defense_rating - movement

    return new_attack, new_defense


def update_team_record(
    rating: TeamRating,
    new_elo: float,
    attack_elo: float,
    defense_elo: float,
    goals_for: int,
    goals_against: int,
    match_id: int,
) -> None:
    old_elo = rating.overall_elo

    rating.form_elo = new_elo - old_elo
    rating.overall_elo = new_elo
    rating.attack_elo = attack_elo
    rating.defense_elo = defense_elo

    rating.matches_played += 1
    rating.goals_scored += goals_for
    rating.goals_conceded += goals_against

    if goals_for > goals_against:
        rating.wins += 1
    elif goals_for < goals_against:
        rating.losses += 1
    else:
        rating.draws += 1

    rating.last_match_id = match_id
    rating.updated_at = datetime.utcnow()