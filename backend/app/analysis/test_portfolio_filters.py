# backend/app/analysis/test_portfolio_filters.py

from app.intelligence.portfolio_filters import evaluate_pick_for_portfolio


def test_portfolio_filters():
    examples = [
        {
            "league": "Serie B",
            "market": "under_2_5_goals",
            "confidence": 0.92,
            "odds": 1.75,
            "value_score": 0.22,
        },
        {
            "league": "Premier League",
            "market": "over_1_5_goals",
            "confidence": 0.94,
            "odds": 1.18,
            "value_score": 0.05,
        },
        {
            "league": "Championship",
            "market": "home_win",
            "confidence": 0.91,
            "odds": 1.65,
            "value_score": 0.18,
        },
        {
            "league": "Ekstraklasa",
            "market": "home_win",
            "confidence": 0.91,
            "odds": 1.62,
            "value_score": 0.19,
        },
    ]

    print("\n=== PORTFOLIO FILTER TEST ===\n")

    for item in examples:
        result = evaluate_pick_for_portfolio(**item)

        print(
            {
                "pick": item,
                "allowed": result.allowed,
                "reason": result.reason,
                "risk_flags": result.risk_flags,
                "risk_score": result.risk_score,
            }
        )