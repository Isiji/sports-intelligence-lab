Future ML Direction

The project will evolve from simple models to stronger pipelines:

Logistic Regression baseline
Random Forest
Gradient Boosting
XGBoost or LightGBM
Ensemble models
Probability calibration
Feature importance
Backtesting dashboard
Model versioning
Sport-specific models

Stage 1: Clean backend repo
Stage 2: PostgreSQL models + Alembic
Stage 3: Demo data pipeline
Stage 4: API-Football ingestion
Stage 5: Baseline football model
Stage 6: Better feature engineering
Stage 7: Prediction grouping
Stage 8: Backtesting engine
Stage 9: FastAPI dashboard endpoints
Stage 10: Frontend dashboard
Stage 11: Model upgrades
Stage 12: Basketball/Tennis/Cricket expansion

commands
python -m app.cli ingest-all-leagues-season --season 2025

python -m app.cli train-football

python -m app.cli build-elo-ratings

python -m app.cli build-football-features

python -m app.cli ingest-missing-stats --limit 20

python -m app.cli competition-coverage-report --limit 100

python -m app.cli update-finished-matches --limit 100

python -m app.cli backtest-football --slate demo

python -m app.cli historical-backtest-football

python -m app.cli historical-backtest-football --market home_win --use-only-matches-with-odds

python -m app.cli ingest-odds-finished --limit 5

python -m app.cli historical-group-backtest

python -m app.cli historical-group-backtest --slate football_2026-05-08

python -m app.cli create-groups

psql -U postgres -d sports_intelligence_lab

COMPETITIONS = [
    # =========================
    # INTERNATIONAL
    # =========================
    {
        "name": "FIFA World Cup",
        "type": "international",
        "country": "World",
        "confederation": "FIFA",
        "tier": 1,
    },
    {
        "name": "UEFA European Championship",
        "type": "international",
        "country": "Europe",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "Copa America",
        "type": "international",
        "country": "South America",
        "confederation": "CONMEBOL",
        "tier": 1,
    },
    {
        "name": "Africa Cup of Nations",
        "type": "international",
        "country": "Africa",
        "confederation": "CAF",
        "tier": 1,
    },
    {
        "name": "AFC Asian Cup",
        "type": "international",
        "country": "Asia",
        "confederation": "AFC",
        "tier": 1,
    },
    {
        "name": "CONCACAF Gold Cup",
        "type": "international",
        "country": "North America",
        "confederation": "CONCACAF",
        "tier": 1,
    },

    # =========================
    # UEFA CLUB COMPETITIONS
    # =========================
    {
        "name": "UEFA Champions League",
        "type": "continental",
        "country": "Europe",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "UEFA Europa League",
        "type": "continental",
        "country": "Europe",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "UEFA Europa Conference League",
        "type": "continental",
        "country": "Europe",
        "confederation": "UEFA",
        "tier": 2,
    },
    {
        "name": "UEFA Super Cup",
        "type": "super_cup",
        "country": "Europe",
        "confederation": "UEFA",
        "tier": 1,
    },

    # =========================
    # ENGLAND
    # =========================
    {
        "name": "Premier League",
        "type": "league",
        "country": "England",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "FA Cup",
        "type": "cup",
        "country": "England",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "EFL Cup",
        "type": "cup",
        "country": "England",
        "confederation": "UEFA",
        "tier": 2,
    },
    {
        "name": "FA Community Shield",
        "type": "super_cup",
        "country": "England",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "Championship",
        "type": "league",
        "country": "England",
        "confederation": "UEFA",
        "tier": 2,
    },
    {
        "name": "League One",
        "type": "league",
        "country": "England",
        "confederation": "UEFA",
        "tier": 3,
    },
    {
        "name": "League Two",
        "type": "league",
        "country": "England",
        "confederation": "UEFA",
        "tier": 4,
    },

    # =========================
    # SPAIN
    # =========================
    {
        "name": "La Liga",
        "type": "league",
        "country": "Spain",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "Copa del Rey",
        "type": "cup",
        "country": "Spain",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "Spanish Super Cup",
        "type": "super_cup",
        "country": "Spain",
        "confederation": "UEFA",
        "tier": 1,
    },

    # =========================
    # ITALY
    # =========================
    {
        "name": "Serie A",
        "type": "league",
        "country": "Italy",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "Coppa Italia",
        "type": "cup",
        "country": "Italy",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "Supercoppa Italiana",
        "type": "super_cup",
        "country": "Italy",
        "confederation": "UEFA",
        "tier": 1,
    },

    # =========================
    # GERMANY
    # =========================
    {
        "name": "Bundesliga",
        "type": "league",
        "country": "Germany",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "DFB Pokal",
        "type": "cup",
        "country": "Germany",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "DFL Super Cup",
        "type": "super_cup",
        "country": "Germany",
        "confederation": "UEFA",
        "tier": 1,
    },

    # =========================
    # FRANCE
    # =========================
    {
        "name": "Ligue 1",
        "type": "league",
        "country": "France",
        "confederation": "UEFA",
        "tier": 1,
    },
    {
        "name": "Coupe de France",
        "type": "cup",
        "country": "France",
        "confederation": "UEFA",
        "tier": 1,
    },

    # =========================
    # AFRICA CLUBS
    # =========================
    {
        "name": "CAF Champions League",
        "type": "continental",
        "country": "Africa",
        "confederation": "CAF",
        "tier": 1,
    },
    {
        "name": "CAF Confederation Cup",
        "type": "continental",
        "country": "Africa",
        "confederation": "CAF",
        "tier": 2,
    },

    # =========================
    # SOUTH AMERICA
    # =========================
    {
        "name": "Copa Libertadores",
        "type": "continental",
        "country": "South America",
        "confederation": "CONMEBOL",
        "tier": 1,
    },
    {
        "name": "Copa Sudamericana",
        "type": "continental",
        "country": "South America",
        "confederation": "CONMEBOL",
        "tier": 2,
    },

    # =========================
    # USA
    # =========================
    {
        "name": "Major League Soccer",
        "type": "league",
        "country": "USA",
        "confederation": "CONCACAF",
        "tier": 1,
    },
    {
        "name": "US Open Cup",
        "type": "cup",
        "country": "USA",
        "confederation": "CONCACAF",
        "tier": 1,
    },

    # =========================
    # SAUDI ARABIA
    # =========================
    {
        "name": "Saudi Pro League",
        "type": "league",
        "country": "Saudi Arabia",
        "confederation": "AFC",
        "tier": 1,
    },
    {
        "name": "King Cup",
        "type": "cup",
        "country": "Saudi Arabia",
        "confederation": "AFC",
        "tier": 1,
    },

    # =========================
    # KENYA
    # =========================
    {
        "name": "Kenyan Premier League",
        "type": "league",
        "country": "Kenya",
        "confederation": "CAF",
        "tier": 1,
    },
    {
        "name": "FKF Cup",
        "type": "cup",
        "country": "Kenya",
        "confederation": "CAF",
        "tier": 1,
    },
]