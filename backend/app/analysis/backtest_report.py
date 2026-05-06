# backend/app/analysis/backtest_report.py

from sqlalchemy.orm import Session

from app.analysis.weak_markets import get_weak_markets
from app.backtest.calibration import evaluate_confidence_calibration
from app.backtest.evaluate import evaluate_slate_by_group, evaluate_slate_by_market


def build_backtest_report(session: Session, slate: str = "demo") -> dict:
    market_report = evaluate_slate_by_market(session=session, slate=slate)
    group_report = evaluate_slate_by_group(session=session, slate=slate)
    calibration_report = evaluate_confidence_calibration(session=session, slate=slate)
    weak_markets = get_weak_markets(session=session)

    best_markets = sorted(
        market_report,
        key=lambda row: (row.get("accuracy") or 0, row.get("picks") or 0),
        reverse=True,
    )[:5]

    worst_markets = sorted(
        market_report,
        key=lambda row: (row.get("accuracy") or 0, row.get("picks") or 0),
    )[:5]

    return {
        "slate": slate,
        "summary": {
            "markets_tested": len(market_report),
            "groups_tested": len(group_report),
            "weak_markets_count": len(weak_markets),
        },
        "best_markets": best_markets,
        "worst_markets": worst_markets,
        "weak_markets": weak_markets,
        "market_report": market_report,
        "group_report": group_report,
        "calibration_report": calibration_report,
    }