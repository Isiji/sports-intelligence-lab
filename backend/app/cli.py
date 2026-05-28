import typer

from datetime import date

from app.ingest.api_football_client import ApiFootballClient
from app.backtest.portfolio_profiles import run_portfolio_profiles
from app.backtest.evaluate import evaluate_slate_by_group
from app.backtest.settle import settle_and_score
from app.db.session import get_cli_session, SessionLocal
from sqlalchemy import text, select
from app.utils.slate import resolve_slate
from app.grouping.create_groups import group_predictions
from app.ingest.demo_results import simulate_demo_results
from app.ingest.demo_seed import seed_demo_data
from app.ingest.football_ingestion import (
    ingest_all_leagues_for_season,
    ingest_fixtures_for_date,
    ingest_fixtures_for_league_season,
)

from sqlalchemy import distinct
from app.db.models import Prediction
from app.services.execution_settlement_service import settle_execution_predictions

from app.services.ecosystem_stats_orchestrator import EcosystemStatsOrchestrator
from app.services.stats_coverage_service import (
    rebuild_stats_coverage,
    stats_coverage_report,
)
from app.services.live_group_validation_service import (
    validate_group_for_execution,
)

from app.services.prediction_market_timing_service import (
    analyze_prediction_timing,
)

from app.services.odds_survivability_service import (
    evaluate_odds_survivability,
)
from sqlalchemy import distinct, select
from app.db.models import Match, Prediction
from app.services.execution_settlement_service import settle_execution_predictions
from sqlalchemy import func, select
from app.db.models import Match, Prediction

from app.services.adaptive_stats_orchestrator import (
    AdaptiveStatsOrchestrator,
)
from app.intelligence.clv_analytics_service import (
    build_clv_analytics,
)

from app.services.bookmaker_richness_service import BookmakerRichnessService

from app.services.group_bookmaker_compatibility_service import (
    GroupBookmakerCompatibilityService,
)
from app.services.market_richness_service import MarketRichnessService
from app.odds.synonym_intelligence import (
    ensure_odds_synonym_table,
    rebuild_odds_synonym_intelligence,
    synonym_summary,
)
from app.services.execution_settlement_service import settle_execution_predictions

from app.services.overnight_pipeline_service import OvernightPipelineService
from app.db.session import get_cli_session
from app.services.match_flag_rebuild_service import rebuild_match_flags

from app.analysis.league_strength_report import build_league_strength_report

from app.services.league_odds_coverage_service import (
    league_odds_coverage_report,
    rebuild_league_odds_coverage,
)
from app.odds.market_quality_engine import calculate_market_quality, get_enabled_markets
from app.ingest.football_odds_ingestion import (
    ingest_odds_for_fixture,
    ingest_odds_for_upcoming_matches,
    ingest_odds_for_finished_matches,
    ingest_odds_for_prediction_slate,
    ingest_odds_priority,
    ingest_odds_rotation,
    ingest_odds_rich_leagues,
    ingest_odds_all_leagues_rotation,
    ingest_historical_odds_for_season,
)
from app.backtest.rolling_group_backtest import (
    rolling_group_backtest,
)
from app.backtest.cached_group_backtest import cached_group_backtest
from app.ml.predict_football import predict_all_football_markets
from app.ml.train_football import train_all_football_models
from app.ingest.football_stats_ingestion import (
    ingest_fixture_statistics,
    ingest_missing_statistics,
)

from app.backtest.calibration import (
    evaluate_cached_backtest_calibration,
    evaluate_cached_backtest_calibration_by_market,
    evaluate_confidence_calibration,
)

from app.services.league_cooldown_service import LeagueCooldownService
from app.db.models import Match
from app.ingest.football_stats_ingestion import ingest_fixture_statistics
from app.ingest.football_odds_ingestion import ingest_odds_for_fixture
from app.services.prediction_settlement_service import (
    settle_production_predictions,
)
from app.backtest.profit_threshold_optimizer import (
    optimize_profit_thresholds,
    optimize_all_profit_thresholds,
)

from app.services.adaptive_portfolio_relaxation_service import (
    AdaptivePortfolioRelaxationService,
)
from app.services.league_market_coverage_service import (
    league_market_coverage_report,
    rebuild_league_market_coverage,
)
from app.services.prediction_odds_backfill_service import (
    backfill_prediction_odds,
)
from app.services.intelligence_rebuilder import (
    rebuild_bookmaker_intelligence,
)
from app.services.daily_review_service import (
    daily_prediction_review,
)
from app.automation.daily_cycle import run_daily_cycle
from app.services.production_review_service import get_production_review
from app.ingest.football_odds_ingestion import (
    ingest_odds_for_prediction_slate,
)
from app.analysis.market_survivability_report import market_survivability_report
from app.analysis.odds_band_survivability_report import odds_band_survivability_report

from app.services.ecosystem_odds_orchestrator import (
    EcosystemOddsOrchestrator,
)

from app.services.orchestration_telemetry_service import (
    OrchestrationTelemetryService,
)
from app.reports.competition_coverage import build_competition_coverage_report
# backend/app/cli.py
from app.analysis.group_performance_report import build_group_performance_report

from app.backtest.historical_group_backtest import (
    run_historical_group_backtest,
)
from app.analysis.confidence_band_survivability_report import confidence_band_survivability_report
from app.analysis.league_survivability_report import league_survivability_report

from app.ingest.finished_match_updater import update_finished_matches
from app.reports.prediction_performance import build_prediction_performance_report
from app.services.elo_service import build_elo_ratings
from app.services.football_feature_builder import build_football_feature_cache
from app.backtest.value_backtest import run_value_backtest
from app.backtest.historical_value_backtest import run_historical_value_backtest
from app.backtest.market_profitability import (
    summarize_market_profitability,
)
from app.ingest.football_odds_ingestion import (
    ingest_odds_priority,
    ingest_odds_rotation,
    ingest_odds_rich_leagues,
    ingest_odds_all_leagues_rotation,
)
from app.services.execution_market_intelligence_service import (
    rebuild_execution_market_intelligence,
)
from app.analysis.data_coverage_report import build_data_coverage_report
from app.backtest.portfolio_profiles import PROFILE_CONFIGS
# backend/app/cli.py imports to add
from app.analysis.test_portfolio_filters import test_portfolio_filters
from app.services.intelligence_rebuilder import (
    rebuild_league_intelligence,
    rebuild_market_intelligence,
    rebuild_odds_band_intelligence,
    rebuild_confidence_band_intelligence,
    rebuild_league_market_intelligence,
)
from app.analysis.live_rejection_report import (
    build_live_rejection_report,
)
from app.odds.availability_scanner import scan_market_availability
from app.odds.canonical_markets import supported_market_keys
from app.odds.odds_matcher import find_best_odds_for_prediction
from app.analysis.prediction_review_report import build_prediction_review_report
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
from app.services.intelligence_decay_service import (
    apply_league_decay,
    apply_league_market_decay,
    apply_market_decay,
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
    slate: str = typer.Option(
        "demo",
        help="Prediction slate name.",
    ),

    limit: int = typer.Option(
        16,
        help="Number of upcoming matches to predict.",
    ),

    min_confidence: float = typer.Option(
        0.55,
        "--min-confidence",
        help="Minimum confidence required to save prediction.",
    ),

    require_odds: bool = typer.Option(
        True,
        "--require-odds/--allow-missing-odds",
    ),
) -> None:
    with get_cli_session() as session:
        count = predict_all_football_markets(
            session=session,
            slate=slate,
            limit=limit,
            min_confidence=min_confidence,
            require_odds=require_odds,
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
@app.command("odds-band-survivability-report")
def odds_band_survivability_report_command(
    run_tag: str = typer.Option("research_all_v1"),
    min_bets: int = typer.Option(10),
):
    session = get_cli_session()

    try:
        odds_band_survivability_report(
            session=session,
            run_tag=run_tag,
            min_bets=min_bets,
        )
    finally:
        session.close()

@app.command("confidence-band-survivability-report")
def confidence_band_survivability_report_command(
    run_tag: str = typer.Option("research_all_v1"),
    min_bets: int = typer.Option(10),
):
    session = get_cli_session()

    try:
        confidence_band_survivability_report(
            session=session,
            run_tag=run_tag,
            min_bets=min_bets,
        )
    finally:
        session.close()

@app.command("rebuild-market-intelligence")
def rebuild_market_intelligence_command(
    run_tag: str = typer.Option("research_all_v1"),
):
    session = get_cli_session()

    try:
        result = rebuild_market_intelligence(
            session=session,
            run_tag=run_tag,
        )

        print(result)

    finally:
        session.close()


# backend/app/cli.py
# ADD COMMAND

@app.command("clv-analytics")
def clv_analytics():
    session = get_cli_session()

    try:
        result = build_clv_analytics(
            session=session,
        )

        print("\n=== CLV ANALYTICS ===")
        print(result)

    finally:
        session.close()

@app.command("rebuild-league-intelligence")
def rebuild_league_intelligence_command(
    run_tag: str = typer.Option("research_all_v1"),
):
    session = get_cli_session()

    try:
        result = rebuild_league_intelligence(
            session=session,
            run_tag=run_tag,
        )

        print(result)

    finally:
        session.close()


@app.command("rebuild-odds-band-intelligence")
def rebuild_odds_band_intelligence_command(
    run_tag: str = typer.Option("research_all_v1"),
):
    session = get_cli_session()

    try:
        result = rebuild_odds_band_intelligence(
            session=session,
            run_tag=run_tag,
        )

        print(result)

    finally:
        session.close()

@app.command("rebuild-league-intelligence")
def rebuild_league_intelligence_command(
    run_tag: str = typer.Option("research_all_v1"),
):
    session = get_cli_session()

    try:
        result = rebuild_league_intelligence(
            session=session,
            run_tag=run_tag,
        )

        print(result)

    finally:
        session.close()

@app.command("create-groups")
def create_groups_command(
    slate: str | None = typer.Option(None, "--slate"),

    min_confidence: float = typer.Option(
        0.65,
        "--min-confidence",
    ),

    min_group_odds: float = typer.Option(
        3.0,
        "--min-group-odds",
    ),
    
    league_odds_filter_mode: str = typer.Option(
        "strict",
        "--league-odds-filter-mode",
        help="strict, advisory, or off",
    ),
    
    use_intelligence_filters: bool = typer.Option(
        True,
        "--use-intelligence-filters/--no-intelligence-filters",
    ),

    require_odds: bool = typer.Option(
        False,
        "--require-odds",
    ),

    profile: str | None = typer.Option(
        None,
        "--profile",
    ),
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
            use_intelligence_filters=use_intelligence_filters,
            profile=profile,
            league_odds_filter_mode=league_odds_filter_mode,
        )

        print("\n=== GROUPS CREATED ===")
        print(f"Slate: {selected_slate}")

        if profile:
            print(f"Profile: {profile}")

        for group_name, summary in summaries.items():
            print(f"\n{group_name}")
            print(summary)

    finally:
        session.close()

@app.command("live-rejection-report")
def live_rejection_report(
    slate: str | None = typer.Option(None),
    profile: str | None = typer.Option("AUTO_SAFE"),
    require_odds: bool = typer.Option(True),
):
    session = get_cli_session()

    try:
        report = build_live_rejection_report(
            session=session,
            slate=slate,
            profile=profile,
            require_odds=require_odds,
        )

        print("\n=== LIVE REJECTION REPORT ===")
        print(report)

    finally:
        session.close()

@app.command("ingest-odds-finished")
def ingest_odds_finished(
    limit: int = typer.Option(50, help="Number of finished matches to fetch odds for."),
    force: bool = typer.Option(False, help="Retry even if odds were already attempted/unavailable."),
    season: int | None = typer.Option(None, "--season"),
    recent_hours: int | None = typer.Option(None, "--recent-hours"),
    max_age_days: int = typer.Option(14, "--max-age-days"),
    require_stats: bool = typer.Option(
        True,
        "--require-stats/--allow-no-stats",
    ),
    max_attempts: int = typer.Option(3, "--max-attempts"),
) -> None:
    with get_cli_session() as session:
        result = ingest_odds_for_finished_matches(
            session=session,
            limit=limit,
            force=force,
            season=season,
            recent_hours=recent_hours,
            max_age_days=max_age_days,
            require_stats=require_stats,
            max_attempts=max_attempts,
        )

    typer.echo(result)

@app.command("search-leagues")
def search_leagues(
    name: str = typer.Argument(...),
    season: int | None = typer.Option(None, "--season"),
):
    session = get_cli_session()

    try:
        client = ApiFootballClient(session=session)

        payload = client.search_leagues(
            search=name,
            season=season,
        )

        responses = payload.get("response", [])

        for item in responses:
            league = item.get("league") or {}
            country = item.get("country") or {}

            print(
                {
                    "league_id": league.get("id"),
                    "league_name": league.get("name"),
                    "type": league.get("type"),
                    "country": country.get("name"),
                }
            )

    finally:
        session.close()

@app.command("league-survivability-report")
def league_survivability_report_command(
    run_tag: str = typer.Option("research_all_v1"),
    min_bets: int = typer.Option(10),
):
    session = get_cli_session()

    try:
        league_survivability_report(
            session=session,
            run_tag=run_tag,
            min_bets=min_bets,
        )
    finally:
        session.close()

@app.command("test-portfolio-filters")
def test_portfolio_filters_command():
    test_portfolio_filters()

@app.command("rolling-group-backtest")
def rolling_group_backtest_cli(
    market: str = typer.Option(...),
    initial_train_size: int = typer.Option(100),
    test_window_size: int = typer.Option(20),
    limit: int = typer.Option(100),
    min_confidence: float = typer.Option(0.65),
    stake: float = typer.Option(100.0),
):
    session = get_cli_session()

    try:
        result = rolling_group_backtest(
            session=session,
            market=market,
            initial_train_size=initial_train_size,
            test_window_size=test_window_size,
            limit=limit,
            min_confidence=min_confidence,
            stake=stake,
        )

        print("\n=== ROLLING GROUP BACKTEST ===")
        print(result)

    finally:
        session.close()

@app.command("cached-group-backtest")
def cached_group_backtest_cli(
    run_tag: str | None = typer.Option(None),
    market: str | None = typer.Option(None),

    profile: str | None = typer.Option(
        None,
        help="Named portfolio profile.",
    ),

    min_confidence: float = typer.Option(0.60),
    min_edge: float | None = typer.Option(None),
    min_odds: float = typer.Option(1.0),
    max_odds: float = typer.Option(10.0),
    max_group_odds: float = typer.Option(5.8),

    group_size: int = typer.Option(4),
    stake: float = typer.Option(100.0),
    limit: int = typer.Option(100),
    max_same_league: int = typer.Option(2),

    use_intelligence_filters: bool = typer.Option(
        True,
        "--use-intelligence-filters/--no-intelligence-filters",
        help="Use DB-driven portfolio intelligence filters.",
    ),
):
    session = get_cli_session()

    try:
        if profile:
            profile_config = PROFILE_CONFIGS.get(profile)

            if not profile_config:
                raise typer.BadParameter(
                    f"Unknown profile: {profile}"
                )

            min_confidence = profile_config["min_confidence"]
            max_odds = profile_config["max_odds"]
            max_group_odds = profile_config["max_group_odds"]

        result = cached_group_backtest(
            session=session,
            run_tag=run_tag,
            market=market,
            min_confidence=min_confidence,
            min_edge=min_edge,
            min_odds=min_odds,
            max_odds=max_odds,
            max_group_odds=max_group_odds,
            group_size=group_size,
            stake=stake,
            limit=limit,
            max_same_league=max_same_league,
            use_intelligence_filters=use_intelligence_filters,
        )

        print("\n=== CACHED GROUP BACKTEST ===")
        print(result["summary"])
        print("\n=== PORTFOLIO ANALYTICS ===")
        print(result["analytics"]["summary"])

        print("\n=== GROUPS ===")
        for row in result["groups"]:
            print(row)

    finally:
        session.close()

@app.command("market-survivability-report")
def market_survivability_report_command(
    run_tag: str = typer.Option("research_all_v1"),
    min_bets: int = typer.Option(20),
):
    session = get_cli_session()

    try:
        market_survivability_report(
            session=session,
            run_tag=run_tag,
            min_bets=min_bets,
        )
    finally:
        session.close()

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

@app.command("group-performance-report")
def group_performance_report(
    slate: str | None = typer.Option(None, "--slate"),
    stake: float = typer.Option(100.0, "--stake"),
    show_picks: bool = typer.Option(False, "--show-picks"),
):
    session = get_cli_session()

    try:
        report = build_group_performance_report(
            session=session,
            slate=slate,
            stake=stake,
        )

        print("\n=== GROUP PERFORMANCE REPORT ===")
        print(f"Slate: {report['slate']}")
        print(f"Groups found: {report['groups_found']}")
        print(f"Stake per group: {report['stake_per_group']}")

        print("\n=== SUMMARY ===")
        print(report["summary"])

        for group in report["groups"]:
            print("\n" + "=" * 60)
            print(group["group_name"])
            print("=" * 60)
            print(f"Type: {group['group_type']}")
            print(f"Games: {group['games']}")
            print(f"Settled: {group['settled_games']}")
            print(f"Pending: {group['pending_games']}")
            print(f"Markets: {', '.join(group['markets_used'])}")
            print(f"Leagues: {', '.join(group['leagues_used'])}")
            print(f"Average confidence: {group['average_confidence']}")
            print(f"Average value score: {group['average_value_score']}")
            print(f"Total odds: {group['total_odds']}")
            print(f"Odds coverage: {group['odds_coverage']}")
            print(f"Outcome: {group['outcome']}")
            print(f"Profit: {group['profit']}")
            print(f"ROI: {group['roi']}")
            print(f"Reason: {group['reason']}")

            if show_picks:
                print("\nPicks:")
                for pick in group["picks"]:
                    print(pick)

    finally:
        session.close()


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
    
@app.command("league-strength-report")
def league_strength_report(
    limit: int = typer.Option(80),
):
    session = get_cli_session()

    try:
        report = build_league_strength_report(
            session=session,
            limit=limit,
        )

        print("\n=== GLOBAL DATA SUMMARY ===")
        print(report["summary"])

        print("\n=== LEAGUE STRENGTH REPORT ===")
        for row in report["leagues"]:
            print(row)

        print("\n=== MISSING ODDS PRIORITY ===")
        for row in report["missing_odds_priority"]:
            print(row)

    finally:
        session.close()

@app.command("daily-review")
def daily_review():
    session = get_cli_session()

    result = daily_prediction_review(
        session=session,
    )

    print("\n=== DAILY PRODUCTION REVIEW ===")

    print(result)

@app.command("prediction-review-report")
def prediction_review_report(
    slate: str | None = typer.Option(None, "--slate"),
    limit: int = typer.Option(80, "--limit"),
    require_odds: bool = typer.Option(
        False,
        "--require-odds",
    ),
):
    session = get_cli_session()

    try:
        report = build_prediction_review_report(
            session=session,
            slate=slate,
            limit=limit,
            require_odds=require_odds,
        )

        print("\n=== PREDICTION REVIEW REPORT ===")
        print(
            {
                "slate": report["slate"],
                "total_predictions_reviewed": report["total_predictions_reviewed"],
                "approved_predictions": report["approved_predictions"],
                "rejected_predictions": report["rejected_predictions"],
                "require_odds": report["require_odds"],
            }
        )

        print("\n=== PREDICTIONS ===")

        for item in report["predictions"]:
            print(
                {
                    "match_id": item["match_id"],
                    "league": item["league"],
                    "match": f"{item['home_team']} vs {item['away_team']}",
                    "kickoff": item["kickoff_date"],
                    "market": item["market"],
                    "pick": item["predicted_label"],
                    "confidence": float(item["confidence"] or 0.0),
                    "odds": (
                        float(item["odds"])
                        if item["odds"] is not None
                        else None
                    ),
                    "value_score": (
                        float(item["value_score"])
                        if item["value_score"] is not None
                        else None
                    ),
                    "portfolio_allowed": item["portfolio_allowed"],
                    "portfolio_tier": item["portfolio_tier"],
                    "portfolio_risk_score": item["portfolio_risk_score"],
                    "portfolio_reason": item["portfolio_reason"],
                    "portfolio_flags": item["portfolio_flags"],
                }
            )

    finally:
        session.close()
        
@app.command("production-review")
def production_review_command(
    slate: str | None = typer.Option(
        None,
        "--slate",
        help="Optional prediction slate.",
    ),
):
    with get_cli_session() as session:
        result = get_production_review(
            session=session,
            slate=slate,
        )

    print("\n=== PRODUCTION REVIEW ===")

    summary = result.get("summary") or {}

    print("\n=== SUMMARY ===")
    print(summary)

    picks = result.get("ranked_picks") or []

    print("\n=== EXECUTION PICKS ===")

    for item in picks:

        kickoff = item.get("kickoff_eat")
        timing_status = item.get("timing_status")
        action = item.get("recommended_action")
        survivability = item.get("survivability_score")
        stale_odds = bool(item.get("stale_odds"))

        alternatives = item.get("market_alternatives") or []

        execution_ready = item.get("execution_ready")

        if execution_ready is None:
            execution_ready = (
                survivability is not None
                and float(survivability) >= 0.40
                and not stale_odds
                and timing_status
                not in {
                    "LIVE_OR_FINISHED",
                    "TOO_CLOSE_TO_KICKOFF",
                }
            )

        print(
            {
                "match": (
                    f"{item.get('home_team')} vs "
                    f"{item.get('away_team')}"
                ),
                "league": item.get("league"),
                "kickoff_eat": kickoff,

                "model_market": item.get("market"),
                "model_pick": item.get("predicted_label"),
                "confidence": round(
                    float(item.get("confidence") or 0.0),
                    4,
                ),

                "execution_market": (
                    item.get("execution_market")
                    or item.get("odds_market")
                    or item.get("market")
                ),
                "execution_selection": (
                    item.get("execution_selection")
                    or item.get("odds_selection")
                    or item.get("predicted_label")
                ),
                "execution_family": item.get("execution_family"),
                "execution_line": item.get("execution_line"),

                "odds": item.get("odds"),
                "bookmaker": item.get("odds_bookmaker"),
                "bookmaker_locality": item.get("bookmaker_locality"),
                "odds_match_quality": item.get("odds_match_quality"),

                "value_score": item.get("value_score"),
                "local_realism_score": item.get("local_realism_score"),
                "execution_score": item.get("execution_score"),
                "survivability_score": survivability,

                "timing_status": timing_status,
                "recommended_action": action,
                "stale_odds": stale_odds,
                "execution_ready": execution_ready,

                "execution_reasons": item.get("execution_reasons") or [],

                "ranked_alternatives": [
                    {
                        "market": (
                            alt.get("execution_market")
                            or alt.get("market")
                        ),
                        "selection": (
                            alt.get("execution_selection")
                            or alt.get("selection")
                        ),
                        "bookmaker": (
                            alt.get("bookmaker")
                            or alt.get("odds_bookmaker")
                        ),
                        "odds": alt.get("odds"),
                        "execution_score": alt.get("execution_score"),
                        "local_realism_score": alt.get("local_realism_score"),
                        "match_quality": (
                            alt.get("match_quality")
                            or alt.get("odds_match_quality")
                        ),
                    }
                    for alt in alternatives[:8]
                ],
            }
        )

    groups = result.get("groups") or []

    if groups:

        print("\n=== GROUPS ===")

        for group in groups:
            print(group)
            
@app.command("rebuild-match-flags")
def rebuild_match_flags_command():
    session = get_cli_session()

    try:
        result = rebuild_match_flags(session=session)

        print("\n=== MATCH FLAGS REBUILT ===")
        print(result)

    finally:
        session.close()

@app.command("data-coverage-report")
def data_coverage_report():
    session = get_cli_session()

    try:
        report = build_data_coverage_report(session)

        print("\n=== DATA COVERAGE SUMMARY ===")
        print(report["summary"])

        print("\n=== WORST LEAGUES BY MISSING DATA ===")
        for row in report["by_league"]:
            print(row)

        print("\n=== UPDATE PRIORITY MATCHES ===")
        for row in report["update_priority"]:
            print(row)

    finally:
        session.close()

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
    season: int | None = typer.Option(None, "--season"),
    force: bool = typer.Option(False, help="Retry even if stats were already attempted/unavailable."),
) -> None:
    with get_cli_session() as session:
        result = ingest_missing_statistics(
            session=session,
            limit=limit,
            force=force,
            season=season,
        )

    typer.echo(result)

@app.command("ingest-ecosystem-stats")
def ingest_ecosystem_stats(
    limit: int = typer.Option(300, "--limit"),
    season: int | None = typer.Option(None, "--season"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    session = get_cli_session()

    try:
        orchestrator = EcosystemStatsOrchestrator(
            session=session,
            limit=limit,
            season=season,
            force=force,
        )

        result = orchestrator.run()

        print("\n=== ECOSYSTEM STATS INGESTION ===")
        print(result)

    finally:
        session.close()


@app.command("rebuild-stats-coverage")
def rebuild_stats_coverage_command() -> None:
    session = get_cli_session()

    try:
        result = rebuild_stats_coverage(session=session)

        print("\n=== STATS COVERAGE REBUILT ===")
        print(result)

    finally:
        session.close()


@app.command("stats-coverage-report")
def stats_coverage_report_command(
    season: int | None = typer.Option(None, "--season"),
    limit: int = typer.Option(80, "--limit"),
) -> None:
    session = get_cli_session()

    try:
        result = stats_coverage_report(
            session=session,
            season=season,
            limit=limit,
        )

        print("\n=== STATS COVERAGE REPORT ===")
        print(result)

    finally:
        session.close()

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

@app.command("historical-group-backtest")
def historical_group_backtest(
    slate: str = typer.Option(...),
    stake: float = typer.Option(100.0),
):
    session = get_cli_session()

    try:
        result = run_historical_group_backtest(
            session=session,
            slate=slate,
            stake=stake,
        )

        print("\n=== HISTORICAL GROUP BACKTEST ===")
        print(result["summary"])

        print("\n=== GROUPS ===")

        for row in result["groups"]:
            print(row)

    finally:
        session.close()

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
        
@app.command("portfolio-profile-backtest")
def portfolio_profile_backtest(
    run_tag: str = typer.Option("research_all_v1"),
):
    session = get_cli_session()

    try:
        rows = run_portfolio_profiles(
            session=session,
            run_tag=run_tag,
        )

        print("\n=== PORTFOLIO PROFILE COMPARISON ===")

        for row in rows:
            print(row)

    finally:
        session.close()

@app.command("supported-markets")
def supported_markets():
    print("\n=== SUPPORTED CANONICAL MARKETS ===")
    for market in supported_market_keys():
        print(market)

# backend/app/cli.py
# ADD COMMANDS

@app.command("orchestration-telemetry-report")
def orchestration_telemetry_report(
    days: int = typer.Option(1, "--days"),
):
    session = get_cli_session()

    try:
        service = OrchestrationTelemetryService(session=session)
        report = service.build_report(days=days)

        print("\n=== ORCHESTRATION TELEMETRY REPORT ===")
        print(report)

    finally:
        session.close()


@app.command("api-waste-report")
def api_waste_report(
    days: int = typer.Option(1, "--days"),
):
    session = get_cli_session()

    try:
        service = OrchestrationTelemetryService(session=session)
        report = service.api_waste_report(days=days)

        print("\n=== API WASTE REPORT ===")
        print(report)

    finally:
        session.close()

# backend/app/cli.py
# ADD THIS COMMAND

@app.command("ingest-adaptive-stats")
def ingest_adaptive_stats_command(
    limit: int = typer.Option(
        300,
        help="Maximum matches to process.",
    ),

    season: int | None = typer.Option(
        None,
        help="Optional season filter.",
    ),

    league: str | None = typer.Option(
        None,
        "--league",
        help="Comma-separated league names.",
    ),

    force: bool = typer.Option(
        False,
        help="Force ingestion even if previously skipped.",
    ),
):

    leagues = []

    if league:
        leagues = [
            x.strip()
            for x in league.split(",")
            if x.strip()
        ]

    with SessionLocal() as session:

        orchestrator = AdaptiveStatsOrchestrator(
            session=session,
            limit=limit,
            season=season,
            leagues=leagues,
            force=force,
        )

        result = orchestrator.run()

        typer.echo("\n=== ADAPTIVE STATS INGESTION ===")

        for key, value in result.items():
            typer.echo(f"{key}: {value}")
            
@app.command("league-ingestion-waste-report")
def league_ingestion_waste_report(
    days: int = typer.Option(1, "--days"),
    limit: int = typer.Option(30, "--limit"),
):
    session = get_cli_session()

    try:
        service = OrchestrationTelemetryService(session=session)
        since_report = service.build_report(days=days)

        print("\n=== LEAGUE INGESTION WASTE REPORT ===")
        print(
            {
                "window_days": days,
                "league_waste": since_report["league_waste"][:limit],
            }
        )

    finally:
        session.close()


@app.command("league-cooldown-report")
def league_cooldown_report(
    days: int = typer.Option(3, "--days"),
    min_attempts: int = typer.Option(5, "--min-attempts"),
    limit: int = typer.Option(50, "--limit"),
):
    session = get_cli_session()

    try:
        service = LeagueCooldownService(
            session=session,
            lookback_days=days,
            min_attempts=min_attempts,
        )

        report = service.build_cooldown_report(limit=limit)

        print("\n=== LEAGUE COOLDOWN REPORT ===")
        print(report)

    finally:
        session.close()

@app.command("scan-market-availability")
def scan_market_availability_command(limit: int = 50000):
    session = get_cli_session()
    try:
        result = scan_market_availability(session=session, limit=limit)
        print("\n=== MARKET AVAILABILITY SCAN ===")
        print(result)
    finally:
        session.close()


@app.command("debug-odds-match")
def debug_odds_match(
    match_id: int,
    market: str,
):
    session = get_cli_session()
    try:
        match = session.execute(
            text(
                """
                SELECT id, home_team, away_team
                FROM matches
                WHERE id = :match_id
                """
            ),
            {"match_id": match_id},
        ).mappings().first()

        if not match:
            print({"matched": False, "reason": "match_not_found"})
            return

        result = find_best_odds_for_prediction(
            session=session,
            match_id=match_id,
            target_market=market,
            home_team=match["home_team"],
            away_team=match["away_team"],
        )

        print("\n=== ODDS MATCH DEBUG ===")
        print(result)
    finally:
        session.close()

@app.command("settle-execution-predictions")
def settle_execution_predictions_command(
    slate: str = typer.Option(..., "--slate"),
    stake: float = typer.Option(100.0, "--stake"),
    only_execution_ready: bool = typer.Option(
        True,
        "--only-execution-ready/--include-not-ready",
    ),
):
    session = get_cli_session()

    try:
        result = settle_execution_predictions(
            session=session,
            slate=slate,
            stake=stake,
            only_execution_ready=only_execution_ready,
        )

        print("\n=== EXECUTION SETTLEMENT ===")
        print(result)

    finally:
        session.close()

@app.command("ingest-historical-odds-season")
def ingest_historical_odds_season(
    season: int = typer.Option(...),
    limit: int = typer.Option(500),
    force: bool = typer.Option(False),
    max_attempts: int = typer.Option(3),
    require_stats: bool = typer.Option(True),
):
    with get_cli_session() as session:
        result = ingest_historical_odds_for_season(
            session=session,
            season=season,
            limit=limit,
            force=force,
            max_attempts=max_attempts,
            require_stats=require_stats,
        )

    typer.echo(result)

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

# backend/app/cli.py
# ADD COMMAND

@app.command("backfill-prediction-odds")
def backfill_prediction_odds_command(
    slate: str = typer.Option(..., "--slate"),
    only_missing: bool = typer.Option(
        True,
        "--only-missing/--include-existing",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run/--apply",
    ),
):
    session = get_cli_session()

    try:
        result = backfill_prediction_odds(
            session=session,
            slate=slate,
            only_missing=only_missing,
            dry_run=dry_run,
        )

        print("\n=== PREDICTION ODDS BACKFILL ===")
        print(result)

    finally:
        session.close()
        
# backend/app/cli.py
# ADD COMMAND

@app.command("market-richness-report")
def market_richness_report(
    days: int = typer.Option(7, "--days"),
    limit: int = typer.Option(50, "--limit"),
):
    session = get_cli_session()

    try:
        service = MarketRichnessService(
            session=session,
            lookback_days=days,
        )

        report = service.build_report(limit=limit)

        print("\n=== MARKET RICHNESS REPORT ===")
        print(report)

    finally:
        session.close()


@app.command("bookmaker-richness-report")
def bookmaker_richness_report(
    days: int = typer.Option(7, "--days"),
    limit: int = typer.Option(30, "--limit"),
):
    session = get_cli_session()

    try:
        service = BookmakerRichnessService(
            session=session,
            lookback_days=days,
        )

        report = service.build_report(limit=limit)

        print("\n=== BOOKMAKER RICHNESS REPORT ===")
        print(report)

    finally:
        session.close()

@app.command("rebuild-league-market-coverage")
def rebuild_league_market_coverage_command():
    session = get_cli_session()

    try:
        result = rebuild_league_market_coverage(
            session=session,
        )

        print("\n=== LEAGUE MARKET COVERAGE REBUILT ===")
        print(result)

    finally:
        session.close()


@app.command("league-market-coverage-report")
def league_market_coverage_report_command(
    limit: int = typer.Option(100, "--limit"),
    production_only: bool = typer.Option(
        False,
        "--production-only",
    ),
):
    session = get_cli_session()

    try:
        report = league_market_coverage_report(
            session=session,
            limit=limit,
            production_only=production_only,
        )

        print("\n=== LEAGUE MARKET COVERAGE SUMMARY ===")
        print(report["summary"])

        print("\n=== LEAGUE MARKET ROWS ===")

        for row in report["rows"]:
            print(row)

    finally:
        session.close()
        
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

@app.command("calibration-report")
def calibration_report(
    slate: str = typer.Option("demo"),
):
    session = get_cli_session()

    try:
        rows = evaluate_confidence_calibration(
            session=session,
            slate=slate,
        )

        print("\n=== CONFIDENCE CALIBRATION REPORT ===")
        print(f"Slate: {slate}")

        for row in rows:
            print(row)

    finally:
        session.close()


@app.command("cached-calibration-report")
def cached_calibration_report(
    run_tag: str = typer.Option("research_all_v1"),
    market: str | None = typer.Option(None),
):
    session = get_cli_session()

    try:
        rows = evaluate_cached_backtest_calibration(
            session=session,
            run_tag=run_tag,
            market=market,
        )

        print("\n=== CACHED BACKTEST CALIBRATION REPORT ===")
        print(f"Run tag: {run_tag}")
        print(f"Market: {market or 'all'}")

        for row in rows:
            print(row)

    finally:
        session.close()


@app.command("cached-calibration-by-market")
def cached_calibration_by_market(
    run_tag: str = typer.Option("research_all_v1"),
    min_bets: int = typer.Option(20),
):
    session = get_cli_session()

    try:
        rows = evaluate_cached_backtest_calibration_by_market(
            session=session,
            run_tag=run_tag,
            min_bets=min_bets,
        )

        print("\n=== CACHED CALIBRATION BY MARKET ===")
        print(f"Run tag: {run_tag}")

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

@app.command("rebuild-bookmaker-intelligence")
def rebuild_bookmaker_intelligence_command():
    session = get_cli_session()

    rebuild_bookmaker_intelligence(
        session=session,
    )

    print(
        "\n=== BOOKMAKER INTELLIGENCE REBUILT ==="
    )

@app.command("run-daily-cycle")
def run_daily_cycle_command(
    prediction_date: str | None = None,
    train_models: bool = typer.Option(False, "--train-models"),
    ingest_limit: int = typer.Option(500, "--ingest-limit"),
    odds_limit: int = typer.Option(500, "--odds-limit"),
    require_odds: bool = typer.Option(True, "--require-odds/--no-require-odds"),
):
    parsed_prediction_date = None

    if prediction_date:
        parsed_prediction_date = date.fromisoformat(prediction_date)

    result = run_daily_cycle(
        prediction_date=parsed_prediction_date,
        train_models=train_models,
        ingest_limit=ingest_limit,
        odds_limit=odds_limit,
        require_odds=require_odds,
    )

    print("\n=== DAILY PRODUCTION CYCLE SUMMARY ===")
    print(result)
    
# backend/app/cli.py
# ADD COMMAND

@app.command("settle-production-predictions")
def settle_production_predictions_command(
    slate: str = typer.Option(..., "--slate"),
    stake: float = typer.Option(100.0, "--stake"),
    rebuild_intelligence: bool = typer.Option(
        True,
        "--rebuild-intelligence/--no-rebuild-intelligence",
    ),
):
    session = get_cli_session()

    try:
        result = settle_production_predictions(
            session=session,
            slate=slate,
            stake=stake,
            rebuild_intelligence=rebuild_intelligence,
        )

        print("\n=== PRODUCTION PREDICTIONS SETTLED ===")
        print(result)

    finally:
        session.close()

@app.command("ingest-league-by-search")
def ingest_league_by_search(
    name: str = typer.Argument(...),
    season: int = typer.Option(..., "--season"),
    limit: int = typer.Option(5, "--limit"),
    status: str | None = typer.Option(None, "--status"),
):
    session = get_cli_session()

    try:
        client = ApiFootballClient(session=session)

        payload = client.search_leagues(
            search=name,
            season=season,
        )

        responses = payload.get("response", [])

        if not responses:
            print({"status": "not_found", "search": name, "season": season})
            return

        selected = []

        for item in responses[:limit]:
            league = item.get("league") or {}
            country = item.get("country") or {}

            league_id = league.get("id")
            league_name = league.get("name")

            if league_id is None:
                continue

            print(
                {
                    "selected_league_id": league_id,
                    "league_name": league_name,
                    "country": country.get("name"),
                    "season": season,
                }
            )

            result = ingest_fixtures_for_league_season(
                session=session,
                league_id=int(league_id),
                season=season,
                status=status,
            )

            selected.append(
                {
                    "league_id": league_id,
                    "league_name": league_name,
                    "result": result,
                }
            )

        print(
            {
                "status": "done",
                "search": name,
                "season": season,
                "leagues_ingested": selected,
            }
        )

    finally:
        session.close()

@app.command("find-leagues-season")
def find_leagues_season(
    keyword: str = typer.Argument(...),
    season: int = typer.Option(..., "--season"),
    limit: int = typer.Option(30, "--limit"),
):
    session = get_cli_session()

    try:
        client = ApiFootballClient(session=session)
        payload = client.get_leagues_by_season(season=season)

        rows = payload.get("response", [])
        keyword_lower = keyword.lower()

        matches = []

        for item in rows:
            league = item.get("league") or {}
            country = item.get("country") or {}

            league_name = league.get("name") or ""
            country_name = country.get("name") or ""

            haystack = f"{league_name} {country_name}".lower()

            if keyword_lower in haystack:
                matches.append(
                    {
                        "league_id": league.get("id"),
                        "league_name": league_name,
                        "type": league.get("type"),
                        "country": country_name,
                        "season": season,
                    }
                )

        print(
            {
                "keyword": keyword,
                "season": season,
                "matches_found": len(matches),
                "matches": matches[:limit],
            }
        )

    finally:
        session.close()

@app.command("search-db-leagues")
def search_db_leagues(
    keyword: str = typer.Argument(...),
    season: int | None = typer.Option(None, "--season"),
    limit: int = typer.Option(50, "--limit"),
):
    session = get_cli_session()

    try:
        sql = """
            SELECT
                league,
                season,
                COUNT(*) AS matches,
                COUNT(*) FILTER (WHERE has_stats = true) AS with_stats,
                COUNT(*) FILTER (WHERE has_odds = true) AS with_odds,
                MIN(kickoff_date) AS first_match,
                MAX(kickoff_date) AS last_match
            FROM matches
            WHERE LOWER(league) LIKE :keyword
        """

        params = {"keyword": f"%{keyword.lower()}%"}

        if season is not None:
            sql += " AND season = :season"
            params["season"] = season

        sql += """
            GROUP BY league, season
            ORDER BY season DESC, matches DESC
            LIMIT :limit
        """

        params["limit"] = limit

        rows = session.execute(text(sql), params).mappings().all()

        for row in rows:
            print(dict(row))

    finally:
        session.close()

@app.command("ingest-stats-league")
def ingest_stats_league(
    league: str = typer.Argument(...),
    season: int = typer.Option(..., "--season"),
    limit: int = typer.Option(500, "--limit"),
    force: bool = typer.Option(False, "--force"),
):
    session = get_cli_session()

    try:
        rows = session.scalars(
            select(Match)
            .where(
                Match.league == league,
                Match.season == season,
                Match.provider == "api-football",
                Match.provider_fixture_id.isnot(None),
                Match.is_finished.is_(True),
                Match.is_cancelled.is_(False),
                Match.is_postponed.is_(False),
                Match.home_goals.isnot(None),
                Match.away_goals.isnot(None),
            )
            .order_by(
                Match.has_stats.asc(),
                Match.kickoff_datetime.desc().nulls_last(),
            )
            .limit(limit)
        ).all()

        processed = 0
        skipped = 0
        unavailable = 0
        failed = 0
        sample = []

        for match in rows:
            try:
                result = ingest_fixture_statistics(
                    session=session,
                    match_id=match.id,
                    force=force,
                )

                if len(sample) < 10:
                    sample.append(result)

                if result.get("skipped"):
                    skipped += 1
                elif result.get("has_stats"):
                    processed += 1
                elif result.get("stats_unavailable"):
                    unavailable += 1

            except Exception as exc:
                failed += 1
                session.rollback()

                if "Daily API safety limit reached" in str(exc):
                    break

        print(
            {
                "league": league,
                "season": season,
                "matches_found": len(rows),
                "processed": processed,
                "skipped": skipped,
                "unavailable": unavailable,
                "failed": failed,
                "sample": sample,
            }
        )

    finally:
        session.close()

# backend/app/cli.py

@app.command("settle-finished-execution-predictions")
def settle_finished_execution_predictions_command(
    stake: float = typer.Option(100.0, "--stake"),
    only_execution_ready: bool = typer.Option(
        False,
        "--only-execution-ready/--include-not-ready",
    ),
):
    session = get_cli_session()

    try:
        slates = list(
            session.scalars(
                select(distinct(Prediction.slate))
                .join(Match, Match.id == Prediction.match_id)
                .where(Prediction.settled_at.is_(None))
                .where(Match.home_goals.isnot(None))
                .where(Match.away_goals.isnot(None))
                .where(
                    (Match.is_finished.is_(True))
                    | (Match.status.in_(["FT", "AET", "PEN", "finished", "Finished"]))
                )
                .order_by(Prediction.slate.asc())
            )
        )

        results = []

        for slate in slates:
            result = settle_execution_predictions(
                session=session,
                slate=slate,
                stake=stake,
                only_execution_ready=only_execution_ready,
            )
            results.append(result)

        print("\n=== SETTLED FINISHED EXECUTION PREDICTIONS ===")
        print(
            {
                "slates_checked": len(slates),
                "settled": sum(int(r.get("settled", 0)) for r in results),
                "skipped": sum(int(r.get("skipped", 0)) for r in results),
                "profit_loss": round(sum(float(r.get("profit_loss", 0)) for r in results), 2),
            }
        )

        print("\n=== BY SLATE ===")
        for row in results:
            print(row)

    finally:
        session.close()

@app.command("rebuild-execution-market-intelligence")
def rebuild_execution_market_intelligence_command(
    sport: str = typer.Option("football", "--sport"),
    min_settled: int = typer.Option(1, "--min-settled"),
):
    session = get_cli_session()

    try:
        result = rebuild_execution_market_intelligence(
            session=session,
            sport=sport,
            min_settled=min_settled,
        )

        print("\n=== EXECUTION MARKET INTELLIGENCE REBUILT ===")
        print(result)

    finally:
        session.close()

@app.command("ingest-odds-league")
def ingest_odds_league(
    league: str = typer.Argument(...),
    season: int = typer.Option(..., "--season"),
    limit: int = typer.Option(500, "--limit"),
    force: bool = typer.Option(False, "--force"),
    require_stats: bool = typer.Option(
        True,
        "--require-stats/--allow-no-stats",
    ),
):
    session = get_cli_session()

    try:
        conditions = [
            Match.league == league,
            Match.season == season,
            Match.provider == "api-football",
            Match.provider_fixture_id.isnot(None),
            Match.is_cancelled.is_(False),
            Match.is_postponed.is_(False),
            Match.has_odds.is_(False),
        ]

        if require_stats:
            conditions.append(Match.has_stats.is_(True))

        rows = session.scalars(
            select(Match)
            .where(*conditions)
            .order_by(
                Match.is_finished.desc(),
                Match.has_stats.desc(),
                Match.kickoff_datetime.desc().nulls_last(),
            )
            .limit(limit)
        ).all()

        processed = 0
        inserted = 0
        skipped = 0
        unavailable = 0
        failed = 0
        sample = []

        for match in rows:
            try:
                result = ingest_odds_for_fixture(
                    session=session,
                    match_id=match.id,
                    force=force,
                )

                if len(sample) < 10:
                    sample.append(result)

                if result.get("status") == "skipped":
                    skipped += 1
                    continue

                processed += 1
                inserted += int(result.get("records_inserted", 0) or 0)

                if result.get("odds_unavailable"):
                    unavailable += 1

            except Exception as exc:
                failed += 1
                session.rollback()

                if "Daily API safety limit reached" in str(exc):
                    break

        print(
            {
                "league": league,
                "season": season,
                "matches_found": len(rows),
                "processed": processed,
                "odds_inserted": inserted,
                "skipped": skipped,
                "unavailable": unavailable,
                "failed": failed,
                "sample": sample,
            }
        )

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

@app.command("init-odds-intelligence")
def init_odds_intelligence():
    session = get_cli_session()
    try:
        ensure_odds_synonym_table(session)
        print("\n=== ODDS INTELLIGENCE INITIALIZED ===")
        print({"status": "ok"})
    finally:
        session.close()


@app.command("rebuild-odds-synonyms")
def rebuild_odds_synonyms(limit: int = 100000):
    session = get_cli_session()
    try:
        result = rebuild_odds_synonym_intelligence(session=session, limit=limit)
        print("\n=== ODDS SYNONYM INTELLIGENCE REBUILT ===")
        print(result)
    finally:
        session.close()


@app.command("odds-synonym-summary")
def odds_synonym_summary():
    session = get_cli_session()
    try:
        result = synonym_summary(session)
        print("\n=== ODDS SYNONYM SUMMARY ===")
        print(result)
    finally:
        session.close()

# backend/app/cli.py
# ADD COMMAND

@app.command("group-bookmaker-compatibility")
def group_bookmaker_compatibility(
    slate: str = typer.Option(..., "--slate"),
    bookmaker_mode: str = typer.Option(
        "flexible",
        "--bookmaker-mode",
        help="flexible, same, preferred, or country_safe",
    ),
    allowed_bookmakers: str | None = typer.Option(
        None,
        "--allowed-bookmakers",
        help="Comma-separated bookmaker names, e.g. Bet365,1xBet",
    ),
):
    session = get_cli_session()

    try:
        allowed_list = None

        if allowed_bookmakers:
            allowed_list = [
                item.strip()
                for item in allowed_bookmakers.split(",")
                if item.strip()
            ]

        service = GroupBookmakerCompatibilityService(session=session)

        report = service.analyze_slate(
            slate=slate,
            bookmaker_mode=bookmaker_mode,
            allowed_bookmakers=allowed_list,
        )

        print("\n=== GROUP BOOKMAKER COMPATIBILITY ===")
        print(report)

    finally:
        session.close()


@app.command("adaptive-portfolio-relaxation")
def adaptive_portfolio_relaxation(
    slate: str = typer.Option(..., "--slate"),
):
    session = get_cli_session()

    try:
        service = AdaptivePortfolioRelaxationService(session=session)
        report = service.recommend(slate=slate)

        print("\n=== ADAPTIVE PORTFOLIO RELAXATION ===")
        print(report)

    finally:
        session.close()

@app.command("market-quality-report")
def market_quality_report():
    session = get_cli_session()
    try:
        result = calculate_market_quality(session)
        print("\n=== MARKET QUALITY REPORT ===")
        print(result)
    finally:
        session.close()


@app.command("enabled-markets")
def enabled_markets():
    session = get_cli_session()
    try:
        result = get_enabled_markets(session)
        print("\n=== ENABLED MARKETS ===")
        print(result)
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

@app.command("apply-market-decay")
def apply_market_decay_command():
    session = get_cli_session()

    try:
        result = apply_market_decay(session)

        print(result)

    finally:
        session.close()

@app.command("ingest-odds-slate")
def ingest_odds_slate_command(
    slate: str = typer.Option(..., "--slate"),
    force: bool = typer.Option(False, "--force"),
):
    session = get_cli_session()

    try:
        result = ingest_odds_for_prediction_slate(
            session=session,
            slate=slate,
            force=force,
        )

        print("\n=== INGEST ODDS FOR SLATE ===")
        print(result)

    finally:
        session.close()
        
# backend/app/cli.py
# ADD COMMANDS

@app.command("rebuild-league-odds-coverage")
def rebuild_league_odds_coverage_command(
    min_matches: int = typer.Option(10, "--min-matches"),
):
    session = get_cli_session()

    try:
        result = rebuild_league_odds_coverage(
            session=session,
            min_matches=min_matches,
        )

        print("\n=== LEAGUE ODDS COVERAGE REBUILT ===")
        print(result)

    finally:
        session.close()


@app.command("league-odds-coverage-report")
def league_odds_coverage_report_command(
    limit: int = typer.Option(80, "--limit"),
    production_only: bool = typer.Option(
        False,
        "--production-only",
    ),
):
    session = get_cli_session()

    try:
        report = league_odds_coverage_report(
            session=session,
            limit=limit,
            production_only=production_only,
        )

        print("\n=== LEAGUE ODDS COVERAGE SUMMARY ===")
        print(report["summary"])

        print("\n=== LEAGUES ===")
        for row in report["leagues"]:
            print(row)

    finally:
        session.close()
        
@app.command("apply-league-decay")
def apply_league_decay_command():
    session = get_cli_session()

    try:
        result = apply_league_decay(session)

        print(result)

    finally:
        session.close()

# backend/app/cli.py
# ADD COMMAND

@app.command("debug-prediction-bookmakers")
def debug_prediction_bookmakers(
    prediction_id: int = typer.Option(..., "--prediction-id"),
):
    session = get_cli_session()

    try:
        row = session.execute(
            text(
                """
                SELECT
                    p.id AS prediction_id,
                    p.match_id,
                    p.market,
                    p.predicted_label,
                    p.odds,
                    m.home_team,
                    m.away_team,
                    m.league
                FROM predictions p
                JOIN matches m ON m.id = p.match_id
                WHERE p.id = :prediction_id
                """
            ),
            {"prediction_id": prediction_id},
        ).mappings().first()

        print("\n=== PREDICTION ===")
        print(dict(row) if row else None)

        if not row:
            return

        odds_rows = session.execute(
            text(
                """
                SELECT
                    bookmaker,
                    market,
                    selection,
                    odds,
                    retrieved_at
                FROM match_odds
                WHERE match_id = :match_id
                ORDER BY market ASC, selection ASC, bookmaker ASC
                LIMIT 100
                """
            ),
            {"match_id": row["match_id"]},
        ).mappings().all()

        print("\n=== MATCH ODDS SAMPLE ===")
        for item in odds_rows:
            print(dict(item))

        exact_rows = session.execute(
            text(
                """
                SELECT
                    bookmaker,
                    market,
                    selection,
                    odds,
                    retrieved_at
                FROM match_odds
                WHERE match_id = :match_id
                  AND market = :market
                ORDER BY selection ASC, bookmaker ASC
                """
            ),
            {
                "match_id": row["match_id"],
                "market": row["market"],
            },
        ).mappings().all()

        print("\n=== SAME MARKET ODDS ===")
        for item in exact_rows:
            print(dict(item))

    finally:
        session.close()

@app.command("apply-league-market-decay")
def apply_league_market_decay_command():
    session = get_cli_session()

    try:
        result = apply_league_market_decay(session)

        print(result)

    finally:
        session.close()

# backend/app/cli.py

@app.command("ingest-odds-priority")
def ingest_odds_priority_command(
    limit: int = typer.Option(
        300,
        "--limit",
        help="Maximum matches to process.",
    ),
    max_attempts: int = typer.Option(
        3,
        "--max-attempts",
        help="Maximum odds attempts before cooldown.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
    ),
):
    """
    Production-safe priority odds ingestion.

    Prioritizes:
    - leagues already returning odds
    - upcoming fixtures
    - leagues near production maturity
    - stats-rich ecosystems
    """

    session = get_cli_session()

    try:
        result = ingest_odds_priority(
            session=session,
            limit=limit,
            force=force,
            max_attempts=max_attempts,
        )

        print("\n=== PRIORITY ODDS INGESTION ===")
        print(result)

    finally:
        session.close()

# backend/app/cli.py
# ADD COMMAND

@app.command("settle-all-execution-predictions")
def settle_all_execution_predictions_command(
    stake: float = typer.Option(100.0, "--stake"),
    update_finished_first: bool = typer.Option(
        True,
        "--update-finished-first/--skip-update-finished",
    ),
    update_limit: int = typer.Option(1000, "--update-limit"),
    only_execution_ready: bool = typer.Option(
        True,
        "--only-execution-ready/--include-not-ready",
    ),
):
    session = get_cli_session()

    try:
        finished_update = None

        if update_finished_first:
            finished_update = update_finished_matches(
                session=session,
                limit=update_limit,
            )

        slates = list(
            session.scalars(
                select(distinct(Prediction.slate))
                .where(Prediction.settled_at.is_(None))
                .order_by(Prediction.slate.asc())
            )
        )

        results = []

        for slate in slates:
            result = settle_execution_predictions(
                session=session,
                slate=slate,
                stake=stake,
                only_execution_ready=only_execution_ready,
            )
            results.append(result)

        total_settled = sum(int(r.get("settled", 0)) for r in results)
        total_skipped = sum(int(r.get("skipped", 0)) for r in results)
        total_profit = sum(float(r.get("profit_loss", 0.0)) for r in results)

        print("\n=== SETTLE ALL EXECUTION PREDICTIONS ===")
        print(
            {
                "finished_update": finished_update,
                "slates_checked": len(slates),
                "total_settled": total_settled,
                "total_skipped": total_skipped,
                "total_profit_loss": round(total_profit, 4),
                "stake": stake,
            }
        )

        print("\n=== BY SLATE ===")
        for row in results:
            print(row)

    finally:
        session.close()

# backend/app/cli.py
# ADD COMMAND

@app.command("update-predicted-finished-matches")
def update_predicted_finished_matches_command(
    limit: int = typer.Option(500, "--limit"),
):
    session = get_cli_session()

    try:
        rows = session.execute(
            select(Match.id)
            .join(Prediction, Prediction.match_id == Match.id)
            .where(Prediction.settled_at.is_(None))
            .where(Match.is_finished.is_(False))
            .where(Match.is_cancelled.is_(False))
            .where(Match.is_postponed.is_(False))
            .where(Match.kickoff_datetime < func.now())
            .distinct()
            .limit(limit)
        ).all()

        checked = 0
        results = []

        for row in rows:
            result = update_finished_matches(
                session=session,
                limit=1,
            )
            checked += 1
            results.append(result)

        print("\n=== UPDATE PREDICTED FINISHED MATCHES ===")
        print(
            {
                "candidate_predicted_matches": len(rows),
                "checked": checked,
                "sample_results": results[:10],
            }
        )

    finally:
        session.close()

@app.command("ingest-odds-rotation")
def ingest_odds_rotation_command(
    limit: int = typer.Option(
        300,
        "--limit",
    ),
    rotation_offset: int = typer.Option(
        0,
        "--rotation-offset",
    ),
    max_attempts: int = typer.Option(
        3,
        "--max-attempts",
    ),
    force: bool = typer.Option(
        False,
        "--force",
    ),
):
    """
    Rotational ingestion.

    Ensures lower-priority leagues still receive
    periodic odds attempts.
    """

    session = get_cli_session()

    try:
        result = ingest_odds_rotation(
            session=session,
            limit=limit,
            force=force,
            max_attempts=max_attempts,
            rotation_offset=rotation_offset,
        )

        print("\n=== ROTATION ODDS INGESTION ===")
        print(result)

    finally:
        session.close()


@app.command("ingest-ecosystem-odds")
def ingest_ecosystem_odds_command(
    limit: int = typer.Option(500, "--limit"),

    season: int | None = typer.Option(
        None,
        "--season",
    ),

    league: str | None = typer.Option(
        None,
        "--league",
        help="Comma-separated league names.",
    ),

    mode: str = typer.Option(
        "ecosystem",
        "--mode",
    ),

    force: bool = typer.Option(
        False,
        "--force",
    ),
):

    leagues = []

    if league:
        leagues = [
            x.strip()
            for x in league.split(",")
            if x.strip()
        ]

    session = get_cli_session()

    try:
        orchestrator = EcosystemOddsOrchestrator(
            session=session,
            limit=limit,
            season=season,
            leagues=leagues,
            mode=mode,
            force=force,
        )

        result = orchestrator.run()

        print("\n=== ECOSYSTEM ODDS INGESTION ===")
        print(result)

    finally:
        session.close()

@app.command("ingest-odds-rich-leagues")
def ingest_odds_rich_leagues_command(
    limit: int = typer.Option(
        300,
        "--limit",
    ),
    max_attempts: int = typer.Option(
        3,
        "--max-attempts",
    ),
    force: bool = typer.Option(
        False,
        "--force",
    ),
):
    """
    Aggressively expand odds coverage inside
    leagues already producing useful odds.
    """

    session = get_cli_session()

    try:
        result = ingest_odds_rich_leagues(
            session=session,
            limit=limit,
            force=force,
            max_attempts=max_attempts,
        )

        print("\n=== RICH LEAGUES ODDS INGESTION ===")
        print(result)

    finally:
        session.close()


@app.command("ingest-odds-all-leagues-rotation")
def ingest_odds_all_leagues_rotation_command(
    limit: int = typer.Option(
        500,
        "--limit",
    ),
    rotation_offset: int = typer.Option(
        0,
        "--rotation-offset",
    ),
    max_attempts: int = typer.Option(
        3,
        "--max-attempts",
    ),
    force: bool = typer.Option(
        False,
        "--force",
    ),
):
    """
    Full ecosystem rotational ingestion.

    Every league eventually gets odds attempts.
    No permanent exclusions.
    """

    session = get_cli_session()

    try:
        result = ingest_odds_all_leagues_rotation(
            session=session,
            limit=limit,
            force=force,
            max_attempts=max_attempts,
            rotation_offset=rotation_offset,
        )

        print("\n=== ALL LEAGUES ROTATION INGESTION ===")
        print(result)

    finally:
        session.close()


@app.command("run-overnight-pipeline")
def run_overnight_pipeline(
    daily_api_limit: int = 7000,
    safety_reserve: int = 700,
    dry_run: bool = False,
):
    """
    Run autonomous overnight production pipeline.
    """
    with get_cli_session() as session:
        service = OvernightPipelineService(
            session=session,
            daily_api_limit=daily_api_limit,
            safety_reserve=safety_reserve,
            dry_run=dry_run,
        )

        result = service.run()
        print(result)

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

@app.command("rebuild-confidence-band-intelligence")
def rebuild_confidence_band_intelligence_command(
    run_tag: str = typer.Option("research_all_v1"),
):
    session = get_cli_session()

    try:
        result = rebuild_confidence_band_intelligence(
            session=session,
            run_tag=run_tag,
        )

        print(result)

    finally:
        session.close()


@app.command("rebuild-league-market-intelligence")
def rebuild_league_market_intelligence_command(
    run_tag: str = typer.Option("research_all_v1"),
):
    session = get_cli_session()

    try:
        result = rebuild_league_market_intelligence(
            session=session,
            run_tag=run_tag,
        )

        print(result)

    finally:
        session.close()



if __name__ == "__main__":
    app()