# backend/app/cli.py

import typer

from app.db.base import Base
from app.db.session import engine, get_cli_session
from app.grouping.create_groups import group_predictions
from app.ingest.demo_seed import seed_demo_data
from app.ml.predict_football import predict_football_home_win
from app.ml.train_football import train_football_home_win_model


app = typer.Typer()


@app.command("init-db")
def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    typer.echo("Database initialized.")


@app.command("seed-demo")
def seed_demo() -> None:
    with get_cli_session() as session:
        seed_demo_data(session)

    typer.echo("Demo football data seeded.")


@app.command("train-football")
def train_football() -> None:
    with get_cli_session() as session:
        train_football_home_win_model(session)

    typer.echo("Football home-win model trained.")


@app.command("predict-football")
def predict_football(
    slate: str = typer.Option("demo", help="Prediction slate name."),
    limit: int = typer.Option(16, help="Number of upcoming matches to predict."),
) -> None:
    with get_cli_session() as session:
        count = predict_football_home_win(session, slate=slate, limit=limit)

    typer.echo(f"Inserted {count} football predictions.")


@app.command("group-predictions")
def group_predictions_command(
    slate: str = typer.Option("demo", help="Prediction slate name."),
) -> None:
    with get_cli_session() as session:
        averages = group_predictions(session, slate=slate)

    for group_name, average_confidence in averages.items():
        typer.echo(f"{group_name}: average confidence={average_confidence}")


if __name__ == "__main__":
    app()