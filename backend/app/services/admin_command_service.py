# backend/app/services/admin_command_service.py

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AdminCommand:
    key: str
    label: str
    description: str
    commands: list[list[str]]
    api_safe_level: str = "safe"
    category: str = "General"
    timeout_seconds: int = 60 * 60


PROJECT_BACKEND_DIR = Path(__file__).resolve().parents[2]

ACTIVE_SEASON_FILE = PROJECT_BACKEND_DIR / "active_season.txt"
SEASON_TOKEN = "{active_season}"
DEFAULT_ACTIVE_SEASON = 2026
AVAILABLE_SEASONS = list(range(2022, 2033))


def get_active_season() -> int:
    if ACTIVE_SEASON_FILE.exists():
        raw = ACTIVE_SEASON_FILE.read_text(encoding="utf-8").strip()
        if raw.isdigit():
            season = int(raw)
            if season in AVAILABLE_SEASONS:
                return season

    return DEFAULT_ACTIVE_SEASON


def set_active_season(season: int) -> dict:
    if season not in AVAILABLE_SEASONS:
        return {
            "ok": False,
            "error": f"Invalid season {season}. Allowed seasons: {AVAILABLE_SEASONS}",
            "active_season": get_active_season(),
        }

    ACTIVE_SEASON_FILE.write_text(str(season), encoding="utf-8")

    return {
        "ok": True,
        "active_season": season,
        "available_seasons": AVAILABLE_SEASONS,
    }


def season_args() -> list[str]:
    return ["--season", SEASON_TOKEN]


def resolve_cli_args(cli_args: list[str]) -> list[str]:
    active = str(get_active_season())
    return [active if arg == SEASON_TOKEN else arg for arg in cli_args]


CORE_BACKTEST_MARKETS = [
    "home_win",
    "draw",
    "away_win",
    "over_2_5_goals",
    "under_2_5_goals",
    "btts_yes",
    "btts_no",
    "double_chance_1x",
    "double_chance_x2",
    "double_chance_12",
]

EXPANDED_BACKTEST_MARKETS = [
    *CORE_BACKTEST_MARKETS,
    "over_1_5_goals",
    "under_1_5_goals",
    "over_3_5_goals",
    "under_3_5_goals",
    "home_over_0_5_goals",
    "away_over_0_5_goals",
    "home_over_1_5_goals",
    "away_over_1_5_goals",
    "home_clean_sheet",
    "away_clean_sheet",
    "draw_no_bet_home",
    "draw_no_bet_away",
]


def _historical_backtest_commands(
    markets: list[str],
    *,
    limit: int,
    min_confidence: float,
    run_tag: str,
) -> list[list[str]]:
    return [
        [
            "historical-backtest-football",
            "--market",
            market,
            "--limit",
            str(limit),
            "--min-confidence",
            str(min_confidence),
            "--use-only-matches-with-odds",
            "--save-bets",
            "--run-tag",
            run_tag,
        ]
        for market in markets
    ]


APPROVED_COMMANDS: dict[str, AdminCommand] = {
    # =====================================================
    # BASIC MAINTENANCE
    # =====================================================
    "rebuild_match_flags": AdminCommand(
        key="rebuild_match_flags",
        label="Rebuild Match Flags",
        category="Maintenance",
        description="Refresh finished/postponed/cancelled/training flags.",
        commands=[
            ["rebuild-match-flags"],
        ],
    ),

    "settle_finished_execution": AdminCommand(
        key="settle_finished_execution",
        label="Settle Finished Execution Predictions",
        category="Maintenance",
        description="Update results, rebuild flags, settle finished execution predictions, then refresh execution intelligence.",
        commands=[
            ["update-finished-matches", "--limit", "1000"],
            ["rebuild-match-flags"],
            ["settle-finished-execution-predictions"],
            ["rebuild-execution-market-intelligence"],
            ["production-review"],
        ],
    ),

    # =====================================================
    # DAILY / OVERNIGHT PRODUCTION
    # =====================================================
    "daily_safe_1000": AdminCommand(
        key="daily_safe_1000",
        label="Daily Safe Pipeline 1000",
        category="Production",
        description="Light daily production cycle: stats, odds, results, settlement, intelligence, review.",
        commands=[
            ["ingest-adaptive-stats", "--limit", "1000", *season_args()],
            ["rebuild-match-flags"],

            ["ingest-ecosystem-odds", "--limit", "1000", *season_args(), "--mode", "finished"],
            ["ingest-ecosystem-odds", "--limit", "1000", *season_args(), "--mode", "upcoming"],

            ["update-finished-matches", "--limit", "1000"],
            ["rebuild-match-flags"],
            ["settle-finished-execution-predictions"],

            ["rebuild-execution-market-intelligence"],
            ["rebuild-league-odds-coverage"],
            ["rebuild-league-market-coverage"],

            ["production-review"],
            ["daily-review"],
        ],
    ),

    "overnight_safe_3000": AdminCommand(
        key="overnight_safe_3000",
        label="Overnight Full Production Pipeline 3000",
        category="Production",
        description="Full overnight production flow: ingestion, odds, settlement, intelligence, features, predictions, groups, review.",
        commands=[
            ["ingest-adaptive-stats", "--limit", "3000", *season_args()],
            ["rebuild-match-flags"],

            ["ingest-ecosystem-odds", "--limit", "3000", *season_args(), "--mode", "finished"],
            ["ingest-ecosystem-odds", "--limit", "3000", *season_args(), "--mode", "upcoming"],

            ["update-finished-matches", "--limit", "1000"],
            ["rebuild-match-flags"],
            ["settle-finished-execution-predictions"],

            ["rebuild-market-intelligence"],
            ["rebuild-league-intelligence"],
            ["rebuild-league-market-intelligence"],
            ["rebuild-odds-band-intelligence"],
            ["rebuild-confidence-band-intelligence"],
            ["rebuild-league-odds-coverage"],
            ["rebuild-league-market-coverage"],
            ["rebuild-execution-market-intelligence"],
            ["rebuild-bookmaker-intelligence"],

            ["build-elo-ratings"],
            ["build-football-features"],

            ["predict-football", "--slate", "football_auto_latest", "--limit", "500", "--min-confidence", "0.55", "--require-odds"],
            ["backfill-prediction-odds", "--slate", "football_auto_latest", "--apply"],
            ["create-groups", "--slate", "football_auto_latest", "--profile", "AUTO_SAFE", "--require-odds", "--league-odds-filter-mode", "advisory"],

            ["production-review", "--slate", "football_auto_latest"],
            ["prediction-review-report", "--slate", "football_auto_latest", "--limit", "500", "--require-odds"],
            ["daily-review"],
        ],
        timeout_seconds=60 * 90,
    ),

    "official_overnight_service_dry_run": AdminCommand(
        key="official_overnight_service_dry_run",
        label="Official Overnight Service Dry Run",
        category="Production",
        description="Runs OvernightPipelineService without spending API calls.",
        commands=[
            ["run-overnight-pipeline", "--daily-api-limit", "7000", "--safety-reserve", "700", "--dry-run"],
        ],
    ),

    "official_overnight_service_live": AdminCommand(
        key="official_overnight_service_live",
        label="Official Overnight Service Live",
        category="Production",
        description="Runs the autonomous overnight service with API budget control.",
        commands=[
            ["run-overnight-pipeline", "--daily-api-limit", "7000", "--safety-reserve", "700"],
        ],
        timeout_seconds=60 * 90,
    ),

    # =====================================================
    # TRAINING
    # =====================================================
    "train_all_models_safe": AdminCommand(
        key="train_all_models_safe",
        label="Train All Models Safe",
        category="Training",
        description="Prepares finished matches, rebuilds features, then trains all football models.",
        commands=[
            ["update-finished-matches", "--limit", "1000"],
            ["rebuild-match-flags"],
            ["ingest-adaptive-stats", "--limit", "3000", *season_args()],
            ["rebuild-match-flags"],
            ["build-elo-ratings"],
            ["build-football-features"],
            ["train-football"],
            ["calibration-report", "--slate", "football_auto_latest"],
        ],
        timeout_seconds=60 * 120,
    ),

    "rebuild_features_only": AdminCommand(
        key="rebuild_features_only",
        label="Rebuild Features Only",
        category="Training",
        description="Rebuild ELO ratings and football feature cache without retraining.",
        commands=[
            ["update-finished-matches", "--limit", "1000"],
            ["rebuild-match-flags"],
            ["build-elo-ratings"],
            ["build-football-features"],
        ],
        timeout_seconds=60 * 90,
    ),

    # =====================================================
    # BACKTESTING
    # =====================================================
    "backtest_all_core_markets": AdminCommand(
        key="backtest_all_core_markets",
        label="Backtest All Core Markets",
        category="Backtesting",
        description="Historical backtest for main production and jackpot markets.",
        commands=[
            ["update-finished-matches", "--limit", "1000"],
            ["rebuild-match-flags"],
            ["build-elo-ratings"],
            ["build-football-features"],
            *_historical_backtest_commands(
                CORE_BACKTEST_MARKETS,
                limit=300,
                min_confidence=0.60,
                run_tag="admin_core_markets_latest",
            ),
            ["cached-calibration-by-market", "--run-tag", "admin_core_markets_latest", "--min-bets", "20"],
            ["portfolio-profile-backtest", "--run-tag", "admin_core_markets_latest"],
        ],
        timeout_seconds=60 * 180,
    ),

    "backtest_all_expanded_markets": AdminCommand(
        key="backtest_all_expanded_markets",
        label="Backtest All Expanded Markets",
        category="Backtesting",
        description="Bigger research backtest across core plus expanded bookmaker-rich markets.",
        commands=[
            ["update-finished-matches", "--limit", "1000"],
            ["rebuild-match-flags"],
            ["build-elo-ratings"],
            ["build-football-features"],
            *_historical_backtest_commands(
                EXPANDED_BACKTEST_MARKETS,
                limit=500,
                min_confidence=0.60,
                run_tag="admin_expanded_markets_latest",
            ),
            ["cached-calibration-by-market", "--run-tag", "admin_expanded_markets_latest", "--min-bets", "20"],
            ["portfolio-profile-backtest", "--run-tag", "admin_expanded_markets_latest"],
        ],
        timeout_seconds=60 * 240,
    ),

    "cached_group_backtest_safe": AdminCommand(
        key="cached_group_backtest_safe",
        label="Cached Group Backtest Safe",
        category="Backtesting",
        description="Fast group backtest using saved historical backtest bets.",
        commands=[
            ["cached-group-backtest", "--run-tag", "admin_core_markets_latest", "--profile", "SAFE_B_CURRENT_BEST", "--limit", "500"],
            ["cached-group-backtest", "--run-tag", "admin_core_markets_latest", "--profile", "SAFE_D_MORE_ROOM", "--limit", "500"],
            ["cached-group-backtest", "--run-tag", "admin_core_markets_latest", "--profile", "BALANCED_REFERENCE", "--limit", "500"],
        ],
        timeout_seconds=60 * 90,
    ),

    # =====================================================
    # INTELLIGENCE / PROFITABILITY
    # =====================================================
    "rebuild_all_intelligence": AdminCommand(
        key="rebuild_all_intelligence",
        label="Rebuild All Intelligence",
        category="Intelligence",
        description="Refreshes market, league, odds, confidence, coverage, execution, and bookmaker intelligence.",
        commands=[
            ["rebuild-market-intelligence"],
            ["rebuild-league-intelligence"],
            ["rebuild-league-market-intelligence"],
            ["rebuild-odds-band-intelligence"],
            ["rebuild-confidence-band-intelligence"],
            ["rebuild-league-odds-coverage"],
            ["rebuild-league-market-coverage"],
            ["rebuild-execution-market-intelligence"],
            ["rebuild-bookmaker-intelligence"],
            ["rebuild-odds-synonyms"],
            ["market-quality-report"],
            ["enabled-markets"],
        ],
        timeout_seconds=60 * 120,
    ),

    "profitability_reports_full": AdminCommand(
        key="profitability_reports_full",
        label="Profitability Reports Full",
        category="Intelligence",
        description="Runs fast profitability reports and threshold optimization.",
        commands=[
            ["market-profitability-fast", "--run-tag", "admin_core_markets_latest", "--limit", "100"],
            ["league-profitability-fast", "--run-tag", "admin_core_markets_latest", "--limit", "100"],
            ["odds-band-profitability-fast", "--run-tag", "admin_core_markets_latest"],
            ["confidence-band-profitability-fast", "--run-tag", "admin_core_markets_latest"],
            ["optimize-profit-thresholds-fast", "--run-tag", "admin_core_markets_latest", "--min-sample-size", "30"],
            ["market-survivability-report", "--run-tag", "admin_core_markets_latest", "--min-bets", "20"],
            ["league-survivability-report", "--run-tag", "admin_core_markets_latest", "--min-bets", "20"],
            ["odds-band-survivability-report", "--run-tag", "admin_core_markets_latest", "--min-bets", "20"],
            ["confidence-band-survivability-report", "--run-tag", "admin_core_markets_latest", "--min-bets", "20"],
        ],
        timeout_seconds=60 * 120,
    ),

    # =====================================================
    # FULL RESEARCH CYCLE
    # =====================================================
    "full_research_cycle": AdminCommand(
        key="full_research_cycle",
        label="Full Research Cycle",
        category="Research",
        description="Heavy cycle: prepare data, train models, backtest core markets, rebuild intelligence, run reports.",
        commands=[
            ["update-finished-matches", "--limit", "1000"],
            ["rebuild-match-flags"],
            ["ingest-adaptive-stats", "--limit", "3000", *season_args()],
            ["ingest-ecosystem-odds", "--limit", "3000", *season_args(), "--mode", "finished"],
            ["rebuild-match-flags"],

            ["build-elo-ratings"],
            ["build-football-features"],
            ["train-football"],

            *_historical_backtest_commands(
                CORE_BACKTEST_MARKETS,
                limit=300,
                min_confidence=0.60,
                run_tag="admin_full_research_latest",
            ),

            ["rebuild-market-intelligence", "--run-tag", "admin_full_research_latest"],
            ["rebuild-league-intelligence", "--run-tag", "admin_full_research_latest"],
            ["rebuild-league-market-intelligence", "--run-tag", "admin_full_research_latest"],
            ["rebuild-odds-band-intelligence", "--run-tag", "admin_full_research_latest"],
            ["rebuild-confidence-band-intelligence", "--run-tag", "admin_full_research_latest"],
            ["rebuild-execution-market-intelligence"],
            ["rebuild-bookmaker-intelligence"],

            ["cached-calibration-by-market", "--run-tag", "admin_full_research_latest", "--min-bets", "20"],
            ["portfolio-profile-backtest", "--run-tag", "admin_full_research_latest"],
            ["market-profitability-fast", "--run-tag", "admin_full_research_latest", "--limit", "100"],
            ["league-profitability-fast", "--run-tag", "admin_full_research_latest", "--limit", "100"],
            ["optimize-profit-thresholds-fast", "--run-tag", "admin_full_research_latest", "--min-sample-size", "30"],
        ],
        api_safe_level="heavy",
        timeout_seconds=60 * 300,
    ),

    # =====================================================
    # DIAGNOSTICS / REPORTS
    # =====================================================
    "diagnostics_full": AdminCommand(
        key="diagnostics_full",
        label="Diagnostics Full",
        category="Diagnostics",
        description="Checks data coverage, API waste, telemetry, bookmaker richness, and market richness.",
        commands=[
            ["data-coverage-report"],
            ["competition-coverage-report", "--limit", "100"],
            ["stats-coverage-report", *season_args(), "--limit", "100"],
            ["league-odds-coverage-report", "--limit", "100"],
            ["league-market-coverage-report", "--limit", "100"],
            ["api-waste-report", "--days", "3"],
            ["orchestration-telemetry-report", "--days", "3"],
            ["league-ingestion-waste-report", "--days", "3", "--limit", "50"],
            ["league-cooldown-report", "--days", "3", "--limit", "50"],
            ["market-richness-report", "--days", "7", "--limit", "100"],
            ["bookmaker-richness-report", "--days", "7", "--limit", "50"],
            ["odds-synonym-summary"],
            ["feature-cache-status"],
            ["backtest-cache-status"],
        ],
        timeout_seconds=60 * 90,
    ),
}


def list_admin_commands() -> list[dict]:
    return [
        {
            "key": item.key,
            "label": item.label,
            "description": item.description,
            "api_safe_level": item.api_safe_level,
            "category": item.category,
            "timeout_seconds": item.timeout_seconds,
            "steps": [
                "python -m app.cli " + " ".join(resolve_cli_args(command))
                for command in item.commands
            ],
        }
        for item in APPROVED_COMMANDS.values()
    ]


def run_admin_command(command_key: str) -> dict:
    command = APPROVED_COMMANDS.get(command_key)

    if command is None:
        return {
            "ok": False,
            "error": f"Unknown or unapproved admin command: {command_key}",
        }

    started = time.time()
    results = []

    for index, cli_args_template in enumerate(command.commands, start=1):
        cli_args = resolve_cli_args(cli_args_template)

        full_command = [
            sys.executable,
            "-m",
            "app.cli",
            *cli_args,
        ]
        
        step_started = time.time()

        try:
            process = subprocess.run(
                full_command,
                cwd=str(PROJECT_BACKEND_DIR),
                capture_output=True,
                text=True,
                timeout=command.timeout_seconds,
                shell=False,
            )

            step_result = {
                "step": index,
                "command": "python -m app.cli " + " ".join(cli_args),
                "return_code": process.returncode,
                "duration_seconds": round(time.time() - step_started, 2),
                "stdout": process.stdout[-12000:],
                "stderr": process.stderr[-12000:],
                "ok": process.returncode == 0,
            }

        except subprocess.TimeoutExpired as exc:
            step_result = {
                "step": index,
                "command": "python -m app.cli " + " ".join(cli_args),
                "return_code": -1,
                "duration_seconds": round(time.time() - step_started, 2),
                "stdout": (exc.stdout or "")[-12000:] if isinstance(exc.stdout, str) else "",
                "stderr": (exc.stderr or "")[-12000:] if isinstance(exc.stderr, str) else "",
                "ok": False,
                "error": f"Command timed out after {command.timeout_seconds} seconds.",
            }

        results.append(step_result)

        if not step_result["ok"]:
            return {
                "ok": False,
                "key": command.key,
                "label": command.label,
                "category": command.category,
                "duration_seconds": round(time.time() - started, 2),
                "failed_step": index,
                "results": results,
            }

    return {
        "ok": True,
        "key": command.key,
        "label": command.label,
        "category": command.category,
        "duration_seconds": round(time.time() - started, 2),
        "results": results,
    }