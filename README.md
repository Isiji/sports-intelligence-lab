# Sports Intelligence Lab

Sports Intelligence Lab is a personal machine learning research project for sports prediction, confidence grouping, and backtesting.

The goal is to learn:

- Sports API integrations
- PostgreSQL data modeling
- Historical data collection
- Feature engineering
- Machine learning model training
- Confidence scoring
- Prediction grouping
- Backtesting and model evaluation
- FastAPI backend development
- Future frontend dashboard development

This is a research and learning project, not a commercial betting platform.

---

## Supported Sports Roadmap

### Phase 1
- Football

### Later Phases
- Basketball
- Tennis
- Cricket

---

## Football Markets v1

The first version focuses on simple research targets:

- Home win vs not home win
- Over 1.5 goals
- Over 2.5 goals
- Both teams to score
- Corners market later
- Cards market later
- Player markets later

---

## Core Features

- Fetch historical matches
- Fetch upcoming matches
- Fetch match statistics
- Store data in PostgreSQL
- Train football ML models
- Predict upcoming fixtures
- Generate confidence scores
- Group predictions into 4 research groups
- Backtest predictions after results are known
- Expose everything through FastAPI

---

## Prediction Grouping Logic

The system ranks predictions by confidence and creates four research groups:

```text
Group 1: highest average confidence
Group 2: second highest
Group 3: third highest
Group 4: fourth highest