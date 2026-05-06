from datetime import date

import typer

from app.backtest.evaluate import evaluate_slate_by_group
from app.backtest.settle import settle_and_score
from app.db.session import get_cli_session
from app.grouping.create_groups import group_predictions
from app.ingest.demo_results import simulate_demo_results
from app.ingest.demo_seed import seed_demo_data
from app.ingest.football_ingestion import (
    ingest_all_leagues_for_season,
    ingest_fixtures_for_date,
    ingest_fixtures_for_league_season,
)
from app.ingest.football_odds_ingestion import (
    ingest_odds_for_fixture,
    ingest_odds_for_upcoming_matches,
)
from app.ml.predict_football import predict_all_football_markets
from app.ml.train_football import train_all_football_models
from app.ingest.football_stats_ingestion import (
    ingest_fixture_statistics,
    ingest_missing_statistics,
)
# backend/app/cli.py

from app.reports.competition_coverage import build_competition_coverage_report
# backend/app/cli.py

from app.ingest.finished_match_updater import update_finished_matches
from app.reports.prediction_performance import build_prediction_performance_report


app = typer.Typer()


@app.command("init-db")
def init_db() -> None:
    typer.echo(
        "Use Alembic migrations instead:\n"
        "alembic upgrade head"
    )


@app.command("seed-demo")
def seed_demo() -> None:
    with get_cli_session() as session:
        seed_demo_data(session)

    typer.echo("Demo football data seeded.")


@app.command("train-football")
def train_football() -> None:
    with get_cli_session() as session:
        train_all_football_models(session)

    typer.echo("All football models trained.")


@app.command("predict-football")
def predict_football(
    slate: str = typer.Option("demo", help="Prediction slate name."),
    limit: int = typer.Option(16, help="Number of upcoming matches to predict."),
) -> None:
    with get_cli_session() as session:
        count = predict_all_football_markets(
            session,
            slate=slate,
            limit=limit,
        )

    typer.echo(f"Inserted {count} football predictions.")

@app.command("prediction-performance-report")
def prediction_performance_report(
    slate: str | None = typer.Option(None, help="Optional slate name, for example demo."),
) -> None:
    with get_cli_session() as session:
        report = build_prediction_performance_report(
            session=session,
            slate=slate,
        )

    typer.echo("\n=== SUMMARY ===")
    typer.echo(report["summary"])

    typer.echo("\n=== MARKET PERFORMANCE ===")

    for row in report["markets"]:
        typer.echo(row)
        

@app.command("group-predictions")
def group_predictions_command(
    slate: str = typer.Option("demo", help="Prediction slate name."),
) -> None:
    with get_cli_session() as session:
        summaries = group_predictions(
            session=session,
            slate=slate,
        )

    for group_name, summary in summaries.items():
        typer.echo(f"{group_name}: {summary}")


@app.command("simulate-results")
def simulate_results(
    limit: int = typer.Option(20, help="Number of demo matches to settle."),
) -> None:
    with get_cli_session() as session:
        updated = simulate_demo_results(
            session=session,
            limit=limit,
        )

    typer.echo(f"Simulated results for {updated} demo matches.")


@app.command("settle")
def settle(
    slate: str = typer.Option("demo", help="Prediction slate name."),
) -> None:
    with get_cli_session() as session:
        run = settle_and_score(
            session=session,
            slate=slate,
        )

    typer.echo(
        f"Backtest run {run.id}: "
        f"accuracy={run.overall_accuracy}, "
        f"settled_predictions={run.settled_predictions}"
    )


@app.command("evaluate-groups")
def evaluate_groups(
    slate: str = typer.Option("demo", help="Prediction slate name."),
) -> None:
    with get_cli_session() as session:
        rows = evaluate_slate_by_group(
            session=session,
            slate=slate,
        )

    for row in rows:
        typer.echo(row)


@app.command("ingest-fixtures-date")
def ingest_fixtures_date(
    date_value: str = typer.Option(..., help="Date in YYYY-MM-DD format."),
) -> None:
    try:
        parsed_date = date.fromisoformat(date_value)
    except ValueError as exc:
        raise typer.BadParameter(
            "Invalid date format. Use YYYY-MM-DD, for example 2026-05-06."
        ) from exc

    with get_cli_session() as session:
        result = ingest_fixtures_for_date(
            session=session,
            date_value=parsed_date,
        )

    typer.echo(result)


@app.command("ingest-odds-match")
def ingest_odds_match(
    match_id: int = typer.Option(..., help="Internal match ID."),
) -> None:
    with get_cli_session() as session:
        result = ingest_odds_for_fixture(
            session=session,
            match_id=match_id,
        )

    typer.echo(result)


@app.command("ingest-odds-upcoming")
def ingest_odds_upcoming(
    limit: int = typer.Option(20, help="Number of upcoming matches to fetch odds for."),
) -> None:
    with get_cli_session() as session:
        result = ingest_odds_for_upcoming_matches(
            session=session,
            limit=limit,
        )

    typer.echo(result)
    
    
@app.command("ingest-league-season")
def ingest_league_season(
    league_id: int = typer.Option(..., help="API-Football league ID."),
    season: int = typer.Option(..., help="Season year, for example 2025."),
) -> None:
    with get_cli_session() as session:
        result = ingest_fixtures_for_league_season(
            session=session,
            league_id=league_id,
            season=season,
        )

    typer.echo(result)


@app.command("ingest-all-leagues-season")
def ingest_all_leagues_season(
    season: int = typer.Option(..., help="Season year, for example 2025."),
    max_leagues: int | None = typer.Option(
        None,
        help="Optional safety limit while testing.",
    ),
) -> None:
    with get_cli_session() as session:
        result = ingest_all_leagues_for_season(
            session=session,
            season=season,
            max_leagues=max_leagues,
        )

    typer.echo(result)
    
@app.command("ingest-match-stats")
def ingest_match_stats(
    match_id: int = typer.Option(...),
) -> None:
    with get_cli_session() as session:
        result = ingest_fixture_statistics(
            session=session,
            match_id=match_id,
        )

    typer.echo(result)


@app.command("competition-coverage-report")
def competition_coverage_report(
    limit: int = typer.Option(100, help="Number of competitions to show."),
) -> None:
    with get_cli_session() as session:
        report = build_competition_coverage_report(
            session=session,
            limit=limit,
        )

    typer.echo("\n=== SUMMARY ===")
    typer.echo(report["summary"])

    typer.echo("\n=== COMPETITIONS ===")

    for row in report["competitions"]:
        typer.echo(row)

# backend/app/cli.py

@app.command("update-finished-matches")
def update_finished_matches_command(
    limit: int = typer.Option(500, help="Number of unfinished matches to check."),
) -> None:
    with get_cli_session() as session:
        result = update_finished_matches(
            session=session,
            limit=limit,
        )

    typer.echo(result)


@app.command("ingest-missing-stats")
def ingest_missing_stats(
    limit: int = typer.Option(100),
) -> None:
    with get_cli_session() as session:
        result = ingest_missing_statistics(
            session=session,
            limit=limit,
        )

    typer.echo(result)


if __name__ == "__main__":
    app()