# backend/app/services/intelligence_rebuilder.py

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.db.models import (
    ConfidenceBandIntelligenceSnapshot,
    LeagueIntelligenceSnapshot,
    LeagueMarketIntelligenceSnapshot,
    MarketIntelligenceSnapshot,
    OddsBandIntelligenceSnapshot,
)


def calculate_recent_metrics(
    session: Session,
    run_tag: str,
    market: str | None = None,
    league: str | None = None,
    limit: int = 50,
):
    conditions = ["run_tag = :run_tag"]

    params = {
        "run_tag": run_tag,
        "limit": limit,
    }

    if market:
        conditions.append("market = :market")
        params["market"] = market

    if league:
        conditions.append("league = :league")
        params["league"] = league

    where_clause = " AND ".join(conditions)

    row = session.execute(
        text(
            f"""
            WITH recent AS (
                SELECT won, profit, stake
                FROM historical_backtest_bets
                WHERE {where_clause}
                ORDER BY id DESC
                LIMIT :limit
            )
            SELECT
                COUNT(*) AS bets,
                ROUND(AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END)::numeric, 4) AS recent_hit_rate,
                ROUND((SUM(profit) / NULLIF(SUM(stake), 0))::numeric, 4) AS recent_roi
            FROM recent
            """
        ),
        params,
    ).mappings().first()

    return {
        "recent_hit_rate": float(row["recent_hit_rate"] or 0) if row else 0.0,
        "recent_roi": float(row["recent_roi"] or 0) if row else 0.0,
    }


def _confidence_multiplier(score: float, floor: float = 0.35, cap: float = 1.15) -> float:
    return round(max(min(score / 100, cap), floor), 4)


def _market_allowed(bets: int, roi: float, hit_rate: float, score: float) -> bool:
    return (
        bets >= 20
        and score >= 18
        and roi > -0.25
        and hit_rate >= 0.25
    )


def _league_allowed(bets: int, roi: float, hit_rate: float, score: float) -> bool:
    return (
        bets >= 10
        and score >= 12
        and roi > -0.35
        and hit_rate >= 0.20
    )


def _league_market_allowed(bets: int, roi: float, hit_rate: float, score: float) -> bool:
    return (
        bets >= 5
        and score >= 10
        and roi > -0.40
        and hit_rate >= 0.20
    )


def _band_allowed(bets: int, roi: float, hit_rate: float, score: float) -> bool:
    return (
        bets >= 8
        and score >= 10
        and roi > -0.35
        and hit_rate >= 0.20
    )


def rebuild_market_intelligence(session: Session, run_tag: str):
    session.execute(delete(MarketIntelligenceSnapshot))

    rows = session.execute(
        text(
            """
            SELECT
                market,
                COUNT(*) AS bets,
                ROUND(AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END)::numeric, 4) AS hit_rate,
                ROUND((SUM(profit) / NULLIF(SUM(stake), 0))::numeric, 4) AS roi,
                ROUND(AVG(odds)::numeric, 4) AS avg_odds,
                ROUND(AVG(confidence)::numeric, 4) AS avg_confidence,
                ROUND(AVG(value_score)::numeric, 4) AS avg_value_score
            FROM historical_backtest_bets
            WHERE run_tag = :run_tag
            GROUP BY market
            """
        ),
        {"run_tag": run_tag},
    ).mappings().all()

    inserted = 0

    for row in rows:
        bets = int(row["bets"] or 0)
        hit_rate = float(row["hit_rate"] or 0)
        roi = float(row["roi"] or 0)
        avg_confidence = float(row["avg_confidence"] or 0)
        avg_value_score = float(row["avg_value_score"] or 0)

        survivability_score = round(
            (hit_rate * 35)
            + (max(roi, -1) * 30)
            + (avg_confidence * 20)
            + (avg_value_score * 15),
            4,
        )

        recent = calculate_recent_metrics(
            session=session,
            run_tag=run_tag,
            market=row["market"],
        )

        prediction_allowed = _market_allowed(
            bets=bets,
            roi=roi,
            hit_rate=hit_rate,
            score=survivability_score,
        )

        verdict = "SAFE"
        if not prediction_allowed:
            verdict = "BLOCKED"
        elif roi <= 0:
            verdict = "RISKY"
        elif hit_rate >= 0.60 and roi <= 0.05:
            verdict = "LOW_ODDS_TRAP"

        session.add(
            MarketIntelligenceSnapshot(
                sport="football",
                market=row["market"],
                bets=bets,
                hit_rate=hit_rate,
                roi=roi,
                avg_odds=float(row["avg_odds"] or 0),
                avg_confidence=avg_confidence,
                avg_value_score=avg_value_score,
                survivability_score=survivability_score,
                recent_roi=recent["recent_roi"],
                recent_hit_rate=recent["recent_hit_rate"],
                confidence_multiplier=_confidence_multiplier(survivability_score),
                prediction_allowed=prediction_allowed,
                verdict=verdict,
            )
        )

        inserted += 1

    session.commit()
    return {"markets_rebuilt": inserted}


def rebuild_league_intelligence(session: Session, run_tag: str):
    session.execute(delete(LeagueIntelligenceSnapshot))

    rows = session.execute(
        text(
            """
            SELECT
                league,
                COUNT(*) AS bets,
                ROUND(AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END)::numeric, 4) AS hit_rate,
                ROUND((SUM(profit) / NULLIF(SUM(stake), 0))::numeric, 4) AS roi,
                ROUND(AVG(odds)::numeric, 4) AS avg_odds,
                ROUND(AVG(confidence)::numeric, 4) AS avg_confidence,
                ROUND(AVG(value_score)::numeric, 4) AS avg_value_score
            FROM historical_backtest_bets
            WHERE run_tag = :run_tag
              AND league IS NOT NULL
            GROUP BY league
            """
        ),
        {"run_tag": run_tag},
    ).mappings().all()

    inserted = 0

    for row in rows:
        bets = int(row["bets"] or 0)
        hit_rate = float(row["hit_rate"] or 0)
        roi = float(row["roi"] or 0)
        avg_confidence = float(row["avg_confidence"] or 0)
        avg_value_score = float(row["avg_value_score"] or 0)

        survivability_score = round(
            (hit_rate * 30)
            + (max(roi, -1) * 30)
            + (avg_confidence * 20)
            + (avg_value_score * 20),
            4,
        )

        recent = calculate_recent_metrics(
            session=session,
            run_tag=run_tag,
            league=row["league"],
        )

        prediction_allowed = _league_allowed(
            bets=bets,
            roi=roi,
            hit_rate=hit_rate,
            score=survivability_score,
        )

        safe_for_accumulators = (
            prediction_allowed
            and roi > 0
            and hit_rate >= 0.50
            and bets >= 15
        )

        verdict = "SAFE"
        if not prediction_allowed:
            verdict = "BLOCKED"
        elif roi <= 0:
            verdict = "CHAOTIC"
        elif avg_confidence >= 0.80 and roi <= 0.05:
            verdict = "FAKE_CONFIDENCE"

        session.add(
            LeagueIntelligenceSnapshot(
                sport="football",
                league=row["league"],
                bets=bets,
                hit_rate=hit_rate,
                roi=roi,
                avg_odds=float(row["avg_odds"] or 0),
                avg_confidence=avg_confidence,
                avg_value_score=avg_value_score,
                survivability_score=survivability_score,
                recent_roi=recent["recent_roi"],
                recent_hit_rate=recent["recent_hit_rate"],
                confidence_multiplier=_confidence_multiplier(survivability_score, floor=0.30, cap=1.10),
                stats_quality_score=hit_rate,
                safe_for_accumulators=safe_for_accumulators,
                prediction_allowed=prediction_allowed,
                verdict=verdict,
            )
        )

        inserted += 1

    session.commit()
    return {"leagues_rebuilt": inserted}


def rebuild_odds_band_intelligence(session: Session, run_tag: str):
    session.execute(delete(OddsBandIntelligenceSnapshot))

    rows = session.execute(
        text(
            """
            WITH banded AS (
                SELECT
                    market,
                    CASE
                        WHEN odds < 1.30 THEN '1.00-1.29'
                        WHEN odds < 1.50 THEN '1.30-1.49'
                        WHEN odds < 1.80 THEN '1.50-1.79'
                        WHEN odds < 2.20 THEN '1.80-2.19'
                        WHEN odds < 3.00 THEN '2.20-2.99'
                        WHEN odds < 5.00 THEN '3.00-4.99'
                        ELSE '5.00+'
                    END AS odds_band,
                    won,
                    profit,
                    stake
                FROM historical_backtest_bets
                WHERE run_tag = :run_tag
                  AND odds IS NOT NULL
            )
            SELECT
                market,
                odds_band,
                COUNT(*) AS bets,
                ROUND(AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END)::numeric, 4) AS hit_rate,
                ROUND((SUM(profit) / NULLIF(SUM(stake), 0))::numeric, 4) AS roi
            FROM banded
            GROUP BY market, odds_band
            """
        ),
        {"run_tag": run_tag},
    ).mappings().all()

    inserted = 0

    for row in rows:
        bets = int(row["bets"] or 0)
        hit_rate = float(row["hit_rate"] or 0)
        roi = float(row["roi"] or 0)

        survivability_score = round(
            (hit_rate * 55)
            + (max(roi, -1) * 45),
            4,
        )

        prediction_allowed = _band_allowed(
            bets=bets,
            roi=roi,
            hit_rate=hit_rate,
            score=survivability_score,
        )

        session.add(
            OddsBandIntelligenceSnapshot(
                market=row["market"],
                odds_band=row["odds_band"],
                bets=bets,
                hit_rate=hit_rate,
                roi=roi,
                survivability_score=survivability_score,
                confidence_multiplier=_confidence_multiplier(survivability_score, floor=0.30, cap=1.10),
                prediction_allowed=prediction_allowed,
                verdict="SAFE" if prediction_allowed and roi > 0 else "RISKY" if prediction_allowed else "BLOCKED",
            )
        )

        inserted += 1

    session.commit()
    return {"odds_band_rows": inserted}


def rebuild_confidence_band_intelligence(session: Session, run_tag: str):
    session.execute(delete(ConfidenceBandIntelligenceSnapshot))

    rows = session.execute(
        text(
            """
            WITH banded AS (
                SELECT
                    market,
                    CASE
                        WHEN confidence < 0.60 THEN '0.00-0.59'
                        WHEN confidence < 0.70 THEN '0.60-0.69'
                        WHEN confidence < 0.80 THEN '0.70-0.79'
                        WHEN confidence < 0.90 THEN '0.80-0.89'
                        ELSE '0.90+'
                    END AS confidence_band,
                    won,
                    profit,
                    stake
                FROM historical_backtest_bets
                WHERE run_tag = :run_tag
                  AND confidence IS NOT NULL
            )
            SELECT
                market,
                confidence_band,
                COUNT(*) AS bets,
                ROUND(AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END)::numeric, 4) AS hit_rate,
                ROUND((SUM(profit) / NULLIF(SUM(stake), 0))::numeric, 4) AS roi
            FROM banded
            GROUP BY market, confidence_band
            """
        ),
        {"run_tag": run_tag},
    ).mappings().all()

    inserted = 0

    for row in rows:
        bets = int(row["bets"] or 0)
        hit_rate = float(row["hit_rate"] or 0)
        roi = float(row["roi"] or 0)

        survivability_score = round(
            (hit_rate * 55)
            + (max(roi, -1) * 45),
            4,
        )

        prediction_allowed = _band_allowed(
            bets=bets,
            roi=roi,
            hit_rate=hit_rate,
            score=survivability_score,
        )

        verdict = "SAFE"
        if not prediction_allowed:
            verdict = "BLOCKED"
        elif roi <= 0:
            verdict = "RISKY"
        elif row["confidence_band"] == "0.90+" and roi <= 0.05:
            verdict = "FAKE_CONFIDENCE"

        session.add(
            ConfidenceBandIntelligenceSnapshot(
                market=row["market"],
                confidence_band=row["confidence_band"],
                bets=bets,
                hit_rate=hit_rate,
                roi=roi,
                survivability_score=survivability_score,
                confidence_multiplier=_confidence_multiplier(survivability_score, floor=0.30, cap=1.10),
                prediction_allowed=prediction_allowed,
                verdict=verdict,
            )
        )

        inserted += 1

    session.commit()
    return {"confidence_band_rows": inserted}


def rebuild_league_market_intelligence(session: Session, run_tag: str):
    session.execute(delete(LeagueMarketIntelligenceSnapshot))

    rows = session.execute(
        text(
            """
            SELECT
                league,
                market,
                COUNT(*) AS bets,
                ROUND(AVG(CASE WHEN won = true THEN 1.0 ELSE 0.0 END)::numeric, 4) AS hit_rate,
                ROUND((SUM(profit) / NULLIF(SUM(stake), 0))::numeric, 4) AS roi,
                ROUND(AVG(odds)::numeric, 4) AS avg_odds,
                ROUND(AVG(confidence)::numeric, 4) AS avg_confidence,
                ROUND(AVG(value_score)::numeric, 4) AS avg_value_score
            FROM historical_backtest_bets
            WHERE run_tag = :run_tag
              AND league IS NOT NULL
            GROUP BY league, market
            """
        ),
        {"run_tag": run_tag},
    ).mappings().all()

    inserted = 0

    for row in rows:
        bets = int(row["bets"] or 0)
        hit_rate = float(row["hit_rate"] or 0)
        roi = float(row["roi"] or 0)
        avg_confidence = float(row["avg_confidence"] or 0)
        avg_value_score = float(row["avg_value_score"] or 0)

        survivability_score = round(
            (hit_rate * 35)
            + (max(roi, -1) * 35)
            + (avg_confidence * 15)
            + (avg_value_score * 15),
            4,
        )

        recent = calculate_recent_metrics(
            session=session,
            run_tag=run_tag,
            market=row["market"],
            league=row["league"],
        )

        prediction_allowed = _league_market_allowed(
            bets=bets,
            roi=roi,
            hit_rate=hit_rate,
            score=survivability_score,
        )

        verdict = "SAFE"
        if not prediction_allowed:
            verdict = "BLOCKED"
        elif roi <= 0:
            verdict = "RISKY"
        elif hit_rate >= 0.60 and roi <= 0.05:
            verdict = "CONFIDENCE_TRAP"

        session.add(
            LeagueMarketIntelligenceSnapshot(
                sport="football",
                league=row["league"],
                market=row["market"],
                bets=bets,
                hit_rate=hit_rate,
                roi=roi,
                avg_odds=float(row["avg_odds"] or 0),
                avg_confidence=avg_confidence,
                avg_value_score=avg_value_score,
                survivability_score=survivability_score,
                recent_roi=recent["recent_roi"],
                recent_hit_rate=recent["recent_hit_rate"],
                confidence_multiplier=_confidence_multiplier(survivability_score, floor=0.30, cap=1.15),
                prediction_allowed=prediction_allowed,
                verdict=verdict,
            )
        )

        inserted += 1

    session.commit()
    return {"league_market_rows": inserted}