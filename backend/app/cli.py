from datetime import date

import typer

from app.backtest.evaluate import evaluate_slate_by_group
from app.backtest.settle import settle_and_score
from app.db.session import get_cli_session
from app.grouping.create_groups import group_predictions
from app.ingest.demo_results import simulate_demo_results
from app.ingest.demo_seed import seed_demo_data
from app.ingest.football_ingestion import ingest_fixtures_for_date
from app.ml.predict_football import predict_all_football_markets
from app.ml.train_football import train_all_football_models


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


if __name__ == "__main__":
    app()