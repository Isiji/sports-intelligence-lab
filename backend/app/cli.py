from datetime import date

import typer

from app.backtest.evaluate import evaluate_slate_by_group
from app.backtest.settle import settle_and_score
from app.db.session import get_cli_session
from sqlalchemy import text
from app.utils.slate import resolve_slate
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
    ingest_odds_for_finished_matches,
)

from app.ml.predict_football import predict_all_football_markets
from app.ml.train_football import train_all_football_models
from app.ingest.football_stats_ingestion import (
    ingest_fixture_statistics,
    ingest_missing_statistics,
)
from app.backtest.profit_threshold_optimizer import (
    optimize_profit_thresholds,
    optimize_all_profit_thresholds,
)
# backend/app/cli.py

from app.reports.competition_coverage import build_competition_coverage_report
# backend/app/cli.py

from app.ingest.finished_match_updater import update_finished_matches
from app.reports.prediction_performance import build_prediction_performance_report
from app.services.elo_service import build_elo_ratings
from app.services.football_feature_builder import build_football_feature_cache
from app.backtest.value_backtest import run_value_backtest
from app.backtest.historical_value_backtest import run_historical_value_backtest
from app.backtest.market_profitability import (
    summarize_market_profitability,
)
# backend/app/cli.py imports to add

from app.analysis.backtest_cache_analytics import (
    ProfitabilityFilters,
    confidence_band_profitability_fast,
    league_profitability_fast,
    market_profitability_fast,
    odds_band_profitability_fast,
    optimize_profit_thresholds_fast,
)
from app.grouping.historical_group_optimizer import (
    GroupOptimizerConfig,
    build_historical_best_groups,
)

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

@app.command("feature-cache-status")
def feature_cache_status() -> None:
    with get_cli_session() as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM football_feature_snapshots")
        ).scalar()

    typer.echo({"cached_feature_rows": count})

@app.command("backtest-cache-status")
def backtest_cache_status() -> None:
    with get_cli_session() as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM historical_backtest_bets")
        ).scalar()

    typer.echo({"cached_backtest_bets": count})

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

@app.command("create-groups")
def create_groups_command(
    slate: str | None = typer.Option(None, "--slate"),
    min_confidence: float = typer.Option(0.65, "--min-confidence"),
    min_group_odds: float = typer.Option(3.0, "--min-group-odds"),
    require_odds: bool = typer.Option(False, "--require-odds"),
):
    """
    Create prediction groups for a slate.

    Uses profitability-aware portfolio grouping first.
    Falls back to confidence/value grouping if historical intelligence is not enough.
    """

    session = get_cli_session()

    try:
        selected_slate = resolve_slate(slate)

        summaries = group_predictions(
            session=session,
            slate=selected_slate,
            min_confidence=min_confidence,
            min_group_odds=min_group_odds,
            require_odds=require_odds,
        )

        print("\n=== GROUPS CREATED ===")
        print(f"Slate: {selected_slate}")

        for group_name, summary in summaries.items():
            print(f"\n{group_name}")
            print(summary)

    finally:
        session.close()
        
@app.command("ingest-odds-finished")
def ingest_odds_finished(
    limit: int = typer.Option(50, help="Number of finished matches to fetch odds for."),
    force: bool = typer.Option(False, help="Retry even if odds were already attempted/unavailable."),
) -> None:
    with get_cli_session() as session:
        result = ingest_odds_for_finished_matches(
            session=session,
            limit=limit,
            force=force,
        )

    typer.echo(result)


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
    force: bool = typer.Option(False, help="Retry even if odds were already attempted/unavailable."),
) -> None:
    with get_cli_session() as session:
        result = ingest_odds_for_upcoming_matches(
            session=session,
            limit=limit,
            force=force,
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
    force: bool = typer.Option(False, help="Retry even if stats were already attempted/unavailable."),
) -> None:
    with get_cli_session() as session:
        result = ingest_missing_statistics(
            session=session,
            limit=limit,
            force=force,
        )

    typer.echo(result)

@app.command("market-profitability")
def market_profitability(
    slate: str | None = typer.Option(None, help="Optional prediction slate filter."),
) -> None:
    """
    Analyze profitability by market and league.
    """

    from pprint import pprint

    with get_cli_session() as session:
        results = summarize_market_profitability(
            session=session,
            slate=slate,
        )

    typer.echo("\n========== BEST MARKETS ==========\n")
    pprint(results["best_markets"])

    typer.echo("\n========== WORST MARKETS ==========\n")
    pprint(results["worst_markets"])

    typer.echo("\n========== BEST LEAGUES ==========\n")
    pprint(results["best_leagues"])

    typer.echo("\n========== WORST LEAGUES ==========\n")
    pprint(results["worst_leagues"])

@app.command("optimize-profit-thresholds")
def optimize_profit_thresholds_command(
    market: str = typer.Option("over_2_5_goals", help="Market to optimize."),
    min_bets: int = typer.Option(5, help="Minimum bets required for a threshold combo."),
) -> None:
    from pprint import pprint

    with get_cli_session() as session:
        result = optimize_profit_thresholds(
            session=session,
            market=market,
            min_bets=min_bets,
        )

    typer.echo("\n========== RAW BACKTEST SUMMARY ==========\n")
    pprint(result["raw_summary"])

    typer.echo("\n========== BEST PROFIT THRESHOLDS ==========\n")
    pprint(result["best_thresholds"])

    typer.echo("\n========== WORST PROFIT THRESHOLDS ==========\n")
    pprint(result["worst_thresholds"])


@app.command("optimize-profit-thresholds-all")
def optimize_profit_thresholds_all_command(
    min_bets: int = typer.Option(5, help="Minimum bets required for a threshold combo."),
) -> None:
    from pprint import pprint

    with get_cli_session() as session:
        result = optimize_all_profit_thresholds(
            session=session,
            min_bets=min_bets,
        )

    typer.echo("\n========== BEST MARKET THRESHOLDS ==========\n")
    pprint(result["best_market_thresholds"])


@app.command("build-elo-ratings")
def build_elo_ratings_command() -> None:
    with get_cli_session() as session:
        result = build_elo_ratings(session)

    typer.echo(result)
    
@app.command("build-football-features")
def build_football_features_command() -> None:
    with get_cli_session() as session:
        result = build_football_feature_cache(session)

    typer.echo(result)
    
@app.command("backtest-football")
def backtest_football(
    slate: str = typer.Option("demo", help="Prediction slate name."),
    min_confidence: float = typer.Option(0.0, help="Minimum prediction confidence."),
    min_edge: float = typer.Option(0.0, help="Minimum value edge."),
    min_odds: float = typer.Option(1.0, help="Minimum odds."),
    max_odds: float = typer.Option(20.0, help="Maximum odds."),
    market: str | None = typer.Option(None, help="Optional market filter."),
    stake: float = typer.Option(100.0, help="Flat stake per bet."),
    bankroll: float = typer.Option(10000.0, help="Starting bankroll."),
) -> None:
    with get_cli_session() as session:
        result = run_value_backtest(
            session=session,
            slate=slate,
            min_confidence=min_confidence,
            min_edge=min_edge,
            min_odds=min_odds,
            max_odds=max_odds,
            market=market,
            flat_stake=stake,
            starting_bankroll=bankroll,
        )

    typer.echo("\n=== BACKTEST SUMMARY ===")
    typer.echo(result["summary"])

    typer.echo("\n=== SAMPLE BETS ===")
    for bet in result["bets"][:20]:
        typer.echo(bet)
        
        
@app.command("historical-backtest-football")
def historical_backtest_football(
    market: str = typer.Option("home_win", help="Market to backtest."),
    initial_train_size: int = typer.Option(300, help="Initial historical training size."),
    test_window_size: int = typer.Option(50, help="Rolling test window size."),
    limit: int = typer.Option(100, help="Maximum number of test matches to backtest."),
    min_confidence: float = typer.Option(0.60, help="Minimum confidence to place bet."),
    min_edge: float = typer.Option(0.0, help="Minimum value edge."),
    stake: float = typer.Option(100.0, help="Flat stake per bet."),
    bankroll: float = typer.Option(10000.0, help="Starting bankroll."),
    use_only_matches_with_odds: bool = typer.Option(
        False,
        help="Only backtest matches that have real odds.",
    ),
    save_bets: bool = typer.Option(
        False,
        help="Save historical backtest bets into cache.",
    ),
    run_tag: str = typer.Option(
        "default",
        help="Cache run label, for example overnight_2026_05_08.",
    ),
) -> None:
    with get_cli_session() as session:
        result = run_historical_value_backtest(
            session=session,
            market=market,
            initial_train_size=initial_train_size,
            test_window_size=test_window_size,
            limit=limit,
            min_confidence=min_confidence,
            min_edge=min_edge,
            stake=stake,
            starting_bankroll=bankroll,
            use_only_matches_with_odds=use_only_matches_with_odds,
            save_bets=save_bets,
            run_tag=run_tag,
        )

    typer.echo("\n=== HISTORICAL BACKTEST SUMMARY ===")
    typer.echo(result["summary"])

    typer.echo("\n=== WINDOWS ===")
    for row in result["windows"][:10]:
        typer.echo(row)

    typer.echo("\n=== SAMPLE BETS ===")
    for bet in result["bets"][:20]:
        typer.echo(bet)

# backend/app/cli.py commands to add


@app.command("market-profitability-fast")
def cli_market_profitability_fast(
    market: str | None = typer.Option(None),
    league: str | None = typer.Option(None),
    run_tag: str | None = typer.Option(None),
    min_confidence: float | None = typer.Option(None),
    min_edge: float | None = typer.Option(None),
    min_odds: float | None = typer.Option(None),
    max_odds: float | None = typer.Option(None),
    min_sample_size: int = typer.Option(20),
    limit: int = typer.Option(50),
):
    session = get_cli_session()
    try:
        filters = ProfitabilityFilters(
            market=market,
            league=league,
            run_tag=run_tag,
            min_confidence=min_confidence,
            min_edge=min_edge,
            min_odds=min_odds,
            max_odds=max_odds,
            min_sample_size=min_sample_size,
        )

        rows = market_profitability_fast(session, filters, limit=limit)

        print("\n=== MARKET PROFITABILITY FAST ===")
        for row in rows:
            print(row)

    finally:
        session.close()


@app.command("league-profitability-fast")
def cli_league_profitability_fast(
    market: str | None = typer.Option(None),
    league: str | None = typer.Option(None),
    run_tag: str | None = typer.Option(None),
    min_confidence: float | None = typer.Option(None),
    min_edge: float | None = typer.Option(None),
    min_odds: float | None = typer.Option(None),
    max_odds: float | None = typer.Option(None),
    min_sample_size: int = typer.Option(20),
    limit: int = typer.Option(100),
):
    session = get_cli_session()
    try:
        filters = ProfitabilityFilters(
            market=market,
            league=league,
            run_tag=run_tag,
            min_confidence=min_confidence,
            min_edge=min_edge,
            min_odds=min_odds,
            max_odds=max_odds,
            min_sample_size=min_sample_size,
        )

        rows = league_profitability_fast(session, filters, limit=limit)

        print("\n=== LEAGUE PROFITABILITY FAST ===")
        for row in rows:
            print(row)

    finally:
        session.close()


@app.command("odds-band-profitability-fast")
def cli_odds_band_profitability_fast(
    market: str | None = typer.Option(None),
    league: str | None = typer.Option(None),
    run_tag: str | None = typer.Option(None),
    min_confidence: float | None = typer.Option(None),
    min_edge: float | None = typer.Option(None),
    min_sample_size: int = typer.Option(20),
):
    session = get_cli_session()
    try:
        filters = ProfitabilityFilters(
            market=market,
            league=league,
            run_tag=run_tag,
            min_confidence=min_confidence,
            min_edge=min_edge,
            min_sample_size=min_sample_size,
        )

        rows = odds_band_profitability_fast(session, filters)

        print("\n=== ODDS BAND PROFITABILITY FAST ===")
        for row in rows:
            print(row)

    finally:
        session.close()


@app.command("confidence-band-profitability-fast")
def cli_confidence_band_profitability_fast(
    market: str | None = typer.Option(None),
    league: str | None = typer.Option(None),
    run_tag: str | None = typer.Option(None),
    min_edge: float | None = typer.Option(None),
    min_sample_size: int = typer.Option(20),
):
    session = get_cli_session()
    try:
        filters = ProfitabilityFilters(
            market=market,
            league=league,
            run_tag=run_tag,
            min_edge=min_edge,
            min_sample_size=min_sample_size,
        )

        rows = confidence_band_profitability_fast(session, filters)

        print("\n=== CONFIDENCE BAND PROFITABILITY FAST ===")
        for row in rows:
            print(row)

    finally:
        session.close()


@app.command("optimize-profit-thresholds-fast")
def cli_optimize_profit_thresholds_fast(
    market: str | None = typer.Option(None),
    league: str | None = typer.Option(None),
    run_tag: str | None = typer.Option(None),
    min_sample_size: int = typer.Option(30),
):
    session = get_cli_session()
    try:
        rows = optimize_profit_thresholds_fast(
            session=session,
            market=market,
            league=league,
            run_tag=run_tag,
            min_sample_size=min_sample_size,
        )

        print("\n=== OPTIMIZED PROFIT THRESHOLDS FAST ===")
        for row in rows:
            print(row)

    finally:
        session.close()


@app.command("historical-best-groups")
def cli_historical_best_groups(
    slate: str | None = typer.Option(None),
    run_tag: str | None = typer.Option(None),
    group_size: int = typer.Option(4),
    max_groups: int = typer.Option(10),
    min_confidence: float = typer.Option(0.60),
    min_edge: float = typer.Option(0.00),
    min_odds: float = typer.Option(1.25),
    max_odds: float = typer.Option(3.50),
    min_market_roi: float = typer.Option(0.00),
    min_league_roi: float = typer.Option(0.00),
    min_sample_size: int = typer.Option(20),
):
    session = get_cli_session()
    try:
        config = GroupOptimizerConfig(
            group_size=group_size,
            max_groups=max_groups,
            min_confidence=min_confidence,
            min_edge=min_edge,
            min_odds=min_odds,
            max_odds=max_odds,
            min_market_roi=min_market_roi,
            min_league_roi=min_league_roi,
            min_sample_size=min_sample_size,
        )

        groups = build_historical_best_groups(
            session=session,
            slate=slate,
            run_tag=run_tag,
            config=config,
        )

        print("\n=== HISTORICAL BEST GROUPS ===")
        print(f"groups_found={len(groups)}")

        for group in groups:
            print("\n------------------------------")
            print(
                {
                    "group_number": group["group_number"],
                    "combined_odds": group["combined_odds"],
                    "avg_confidence": group["avg_confidence"],
                    "avg_edge": group["avg_edge"],
                    "avg_market_roi": group["avg_market_roi"],
                    "avg_league_roi": group["avg_league_roi"],
                    "historical_group_won": group["historical_group_won"],
                    "legs_won": group["legs_won"],
                    "legs_lost": group["legs_lost"],
                }
            )

            for item in group["items"]:
                print(
                    {
                        "match": f"{item['home_team']} vs {item['away_team']}",
                        "league": item["league"],
                        "market": item["market"],
                        "pick": item["predicted_label"],
                        "confidence": round(float(item["confidence"] or 0), 4),
                        "odds": float(item["odds"] or 0),
                        "edge": round(float(item["value_score"] or 0), 4),
                        "market_roi": round(float(item["market_roi"] or 0), 4),
                        "league_roi": round(float(item["league_roi"] or 0), 4),
                        "result": item["derived_result"],
                    }
                )

    finally:
        session.close()

if __name__ == "__main__":
    app()