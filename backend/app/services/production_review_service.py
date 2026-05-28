# backend/app/services/production_review_service.py

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.intelligence.exposure_control import (
    apply_exposure_controls,
)

from app.intelligence.pick_recommendation_engine import (
    build_recommendation_layer,
)

from app.services.production_pick_scoring_service import (
    score_pick_list,
)

from app.services.odds_survivability_service import (
    evaluate_odds_survivability,
)

from app.services.prediction_market_timing_service import (
    analyze_prediction_timing,
)


LOCAL_BOOKMAKERS = {
    "betika",
    "sportpesa",
    "odibets",
    "mozzart",
    "mozzartbet",
}


def _is_local_bookmaker(
    bookmaker: str | None,
) -> bool:

    if not bookmaker:
        return False

    return (
        bookmaker.lower().strip()
        in LOCAL_BOOKMAKERS
    )


def _local_realism_score(
    odds: float | None,
    bookmaker: str | None,
    market: str | None,
) -> float:

    score = 0.0

    if _is_local_bookmaker(bookmaker):
        score += 0.45

    if odds is not None:

        if 1.25 <= float(odds) <= 2.40:
            score += 0.40

        elif 2.40 < float(odds) <= 3.20:
            score += 0.20

        elif float(odds) > 4.50:
            score -= 0.25

    if market:

        if "asian_handicap" in market:
            score += 0.10

        if "exact_score" in market:
            score -= 0.40

    return round(
        max(0.0, min(score, 1.0)),
        4,
    )


def _build_market_alternatives(
    item: dict[str, Any],
) -> list[dict[str, Any]]:

    alternatives: list[dict[str, Any]] = []

    market = str(
        item.get("market") or ""
    )

    confidence = float(
        item.get("confidence") or 0.0
    )

    odds = item.get("odds")

    bookmaker = item.get(
        "odds_bookmaker"
    )

    if (
        market.startswith("asian_handicap")
    ):

        alternatives.extend(
            [
                {
                    "execution_market": market.replace(
                        "_1_5",
                        "_1_25",
                    ),
                    "execution_selection": item.get(
                        "predicted_label"
                    ),
                    "bookmaker": bookmaker,
                    "odds": odds,
                    "execution_score": round(
                        confidence * 100,
                        2,
                    ),
                    "local_realism_score": 0.82,
                    "match_quality": "nearby_local_line",
                },
                {
                    "execution_market": market.replace(
                        "_1_5",
                        "_0_75",
                    ),
                    "execution_selection": item.get(
                        "predicted_label"
                    ),
                    "bookmaker": bookmaker,
                    "odds": odds,
                    "execution_score": round(
                        confidence * 96,
                        2,
                    ),
                    "local_realism_score": 0.88,
                    "match_quality": "compressed_local_line",
                },
            ]
        )

    if (
        market == "home_win"
    ):

        alternatives.extend(
            [
                {
                    "execution_market": "draw_no_bet_home",
                    "execution_selection": "HOME",
                    "bookmaker": bookmaker,
                    "odds": odds,
                    "execution_score": round(
                        confidence * 92,
                        2,
                    ),
                    "local_realism_score": 0.94,
                    "match_quality": "safer_local_variant",
                },
                {
                    "execution_market": "double_chance_1x",
                    "execution_selection": "1X",
                    "bookmaker": bookmaker,
                    "odds": odds,
                    "execution_score": round(
                        confidence * 88,
                        2,
                    ),
                    "local_realism_score": 0.98,
                    "match_quality": "high_coverage_local_market",
                },
            ]
        )

    return alternatives


# backend/app/services/production_review_service.py
# REPLACE ONLY get_production_review()

def get_production_review(
    session: Session,
    slate: str | None = None,
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
) -> dict[str, Any]:

    from app.services.execution_market_intelligence_service import (
        get_execution_market_gate,
    )

    from app.db.models import (
        ExecutionMarketIntelligenceSnapshot,
    )

    selected_slate = (
        slate
        or f"football_{date.today().isoformat()}"
    )

    filters = ["p.slate = :slate"]

    params: dict[str, Any] = {
        "slate": selected_slate,
        "limit": limit,
    }

    if market:
        filters.append(
            "p.market = :market"
        )
        params["market"] = market

    if league:
        filters.append(
            "m.league = :league"
        )
        params["league"] = league

    if require_odds:
        filters.append(
            "p.odds IS NOT NULL"
        )

    where_clause = " AND ".join(
        filters
    )

    prediction_summary = session.execute(
        text(
            f"""
            SELECT
                COUNT(*) AS total_predictions,

                COUNT(
                    CASE
                    WHEN p.odds IS NOT NULL
                    THEN 1
                    END
                ) AS predictions_with_odds,

                AVG(p.confidence) AS avg_confidence,
                AVG(p.odds) AS avg_odds,
                AVG(p.value_score) AS avg_value_score

            FROM predictions p

            JOIN matches m
                ON m.id = p.match_id

            WHERE {where_clause}
            """
        ),
        params,
    ).mappings().first()

    ranked_picks = session.execute(
        text(
            f"""
            SELECT
                p.id AS prediction_id,
                p.match_id,

                m.league,
                m.home_team,
                m.away_team,
                m.kickoff_date,
                m.kickoff_datetime,

                p.market,
                p.predicted_label,

                p.confidence,
                p.odds,
                p.implied_probability,
                p.value_score,

                p.model_name,

                p.execution_market,
                p.execution_selection,
                p.execution_family,
                p.execution_line,

                p.execution_score,
                p.execution_ready,
                p.execution_reasons,
                p.market_alternatives,

                p.local_realism_score,
                p.survivability_score,
                p.bookmaker_locality,

                p.odds_bookmaker,
                p.odds_market,
                p.odds_selection,
                p.odds_match_quality,
                p.odds_retrieved_at

            FROM predictions p

            JOIN matches m
                ON m.id = p.match_id

            WHERE {where_clause}

            ORDER BY
                COALESCE(
                    p.execution_score,
                    0
                ) DESC,

                COALESCE(
                    p.local_realism_score,
                    0
                ) DESC,

                COALESCE(
                    p.value_score,
                    0
                ) DESC,

                p.confidence DESC

            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    enriched_ranked_picks = []

    execution_verdict_counts: dict[str, int] = {}

    for row in ranked_picks:

        item = dict(row)

        timing = analyze_prediction_timing(
            kickoff_value=(
                item.get(
                    "kickoff_datetime"
                )
                or item.get(
                    "kickoff_date"
                )
            )
        )

        execution_market = (
            item.get("execution_market")
            or item.get("market")
        )

        execution_gate = (
            get_execution_market_gate(
                session=session,
                execution_market=execution_market,
                sport="football",
            )
        )

        execution_snapshot = session.execute(
            text(
                """
                SELECT
                    execution_market,
                    settled_predictions,
                    wins,
                    losses,
                    hit_rate,
                    avg_odds,
                    roi,
                    survivability_score,
                    verdict,
                    prediction_allowed,
                    grouping_allowed,
                    reason
                FROM execution_market_intelligence_snapshots
                WHERE execution_market = :execution_market
                LIMIT 1
                """
            ),
            {
                "execution_market": execution_market,
            },
        ).mappings().first()

        verdict = execution_gate.verdict

        execution_verdict_counts[verdict] = (
            execution_verdict_counts.get(
                verdict,
                0,
            )
            + 1
        )

        survivability = (
            evaluate_odds_survivability(
                market=item["market"],
                bookmaker=item.get(
                    "odds_bookmaker"
                ),
                odds_retrieved_at=item.get(
                    "odds_retrieved_at"
                ),
                minutes_to_kickoff=(
                    timing.minutes_to_kickoff
                ),
            )
        )

        item["kickoff_eat"] = (
            timing.kickoff_eat
        )

        item["minutes_to_kickoff"] = (
            timing.minutes_to_kickoff
        )

        item["timing_status"] = (
            timing.timing_status
        )

        item["recommended_action"] = (
            timing.recommended_action
        )

        item["timing_reason"] = (
            timing.reason
        )

        item["survivability_score"] = (
            survivability.survivability_score
        )

        item["freshness_score"] = (
            survivability.freshness_score
        )

        item["persistence_score"] = (
            survivability.persistence_score
        )

        item["downgrade_risk_score"] = (
            survivability.downgrade_risk_score
        )

        item["stale_odds"] = (
            survivability.stale
        )

        item["bookmaker_locality"] = (
            "LOCAL"
            if _is_local_bookmaker(
                item.get(
                    "odds_bookmaker"
                )
            )
            else "GLOBAL"
        )

        item["execution_market_verdict"] = (
            execution_gate.verdict
        )

        item["execution_market_reason"] = (
            execution_gate.reason
        )

        item["execution_market_prediction_allowed"] = (
            execution_gate.prediction_allowed
        )

        item["execution_market_grouping_allowed"] = (
            execution_gate.grouping_allowed
        )

        item["execution_market_survivability"] = (
            execution_gate.survivability_score
        )

        item["execution_market_confidence_multiplier"] = (
            execution_gate.confidence_multiplier
        )

        if execution_snapshot:

            item["execution_market_roi"] = (
                float(
                    execution_snapshot.get("roi")
                    or 0.0
                )
            )

            item["execution_market_hit_rate"] = (
                float(
                    execution_snapshot.get(
                        "hit_rate"
                    )
                    or 0.0
                )
            )

            item["execution_market_avg_odds"] = (
                float(
                    execution_snapshot.get(
                        "avg_odds"
                    )
                    or 0.0
                )
            )

            item["execution_market_sample_size"] = (
                int(
                    execution_snapshot.get(
                        "settled_predictions"
                    )
                    or 0
                )
            )

            item["execution_market_wins"] = (
                int(
                    execution_snapshot.get(
                        "wins"
                    )
                    or 0
                )
            )

            item["execution_market_losses"] = (
                int(
                    execution_snapshot.get(
                        "losses"
                    )
                    or 0
                )
            )

        else:

            item["execution_market_roi"] = 0.0
            item["execution_market_hit_rate"] = 0.0
            item["execution_market_avg_odds"] = 0.0
            item["execution_market_sample_size"] = 0
            item["execution_market_wins"] = 0
            item["execution_market_losses"] = 0

        if (
            item.get(
                "local_realism_score"
            )
            is None
        ):
            item["local_realism_score"] = (
                _local_realism_score(
                    odds=item.get(
                        "odds"
                    ),
                    bookmaker=item.get(
                        "odds_bookmaker"
                    ),
                    market=item.get(
                        "market"
                    ),
                )
            )

        if (
            item.get(
                "execution_market"
            )
            is None
        ):
            item["execution_market"] = (
                item.get(
                    "odds_market"
                )
                or item.get(
                    "market"
                )
            )

        if (
            item.get(
                "execution_selection"
            )
            is None
        ):
            item["execution_selection"] = (
                item.get(
                    "odds_selection"
                )
                or item.get(
                    "predicted_label"
                )
            )

        if (
            item.get(
                "market_alternatives"
            )
            is None
        ):
            item["market_alternatives"] = (
                _build_market_alternatives(
                    item
                )
            )

        if (
            item.get(
                "execution_score"
            )
            is None
        ):
            base_score = (
                (
                    float(
                        item.get(
                            "confidence"
                        )
                        or 0.0
                    )
                    * 100
                )
                +
                (
                    float(
                        item.get(
                            "local_realism_score"
                        )
                        or 0.0
                    )
                    * 25
                )
                +
                (
                    float(
                        survivability.survivability_score
                        or 0.0
                    )
                    * 25
                )
            )

            item["execution_score"] = round(
                base_score,
                2,
            )

        item["execution_ready"] = (
            item["execution_score"]
            >= 55
            and not survivability.stale
            and timing.recommended_action
            != "AVOID"
            and execution_gate.grouping_allowed
        )

        enriched_ranked_picks.append(
            item
        )

    scored_ranked_picks = (
        score_pick_list(
            enriched_ranked_picks
        )
    )

    exposure_result = (
        apply_exposure_controls(
            picks=scored_ranked_picks,
        )
    )

    recommendation_layer = (
        build_recommendation_layer(
            exposure_result=(
                exposure_result
            ),
        )
    )

    production_health = {
        "production_ready": True,

        "execution_ready_picks": sum(
            1
            for item
            in scored_ranked_picks
            if item.get(
                "execution_ready"
            )
        ),

        "local_bookmaker_picks": sum(
            1
            for item
            in scored_ranked_picks
            if item.get(
                "bookmaker_locality"
            ) == "LOCAL"
        ),

        "stale_odds_picks": sum(
            1
            for item
            in scored_ranked_picks
            if item.get(
                "stale_odds"
            )
        ),

        "execution_market_breakdown": (
            execution_verdict_counts
        ),

        "core_production_picks": sum(
            1
            for item
            in scored_ranked_picks
            if item.get(
                "execution_market_verdict"
            ) == "CORE_PRODUCTION"
        ),

        "watchlist_picks": sum(
            1
            for item
            in scored_ranked_picks
            if item.get(
                "execution_market_verdict"
            ) == "WATCHLIST"
        ),

        "blocked_picks": sum(
            1
            for item
            in scored_ranked_picks
            if item.get(
                "execution_market_verdict"
            ) == "BLOCKED"
        ),
    }

    return {
        "slate": selected_slate,

        "filters": {
            "market": market,
            "league": league,
            "require_odds": require_odds,
            "limit": limit,
        },

        "summary": dict(
            prediction_summary or {}
        ),

        "production_health": (
            production_health
        ),

        "ranked_picks": (
            scored_ranked_picks
        ),

        "recommendations": (
            recommendation_layer
        ),

        "groups": (
            exposure_result.get(
                "groups",
                [],
            )
            if isinstance(
                exposure_result,
                dict,
            )
            else []
        ),
    }