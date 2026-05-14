from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class GroupBookmakerCompatibilityService:
    """
    Bookmaker compatibility analysis for prediction groups.

    Philosophy:
    - Use prediction-level bookmaker provenance first.
    - Fallback to odds discovery only if provenance missing.
    - Same-bookmaker grouping is OPTIONAL intelligence.
    - Flexible grouping remains production-safe default.
    """

    def __init__(self, session: Session):
        self.session = session

    def analyze_slate(
        self,
        slate: str,
        bookmaker_mode: str = "flexible",
        allowed_bookmakers: list[str] | None = None,
    ) -> dict[str, Any]:
        groups = self._load_group_predictions(slate=slate)

        analyzed_groups = []

        for group_name, predictions in groups.items():
            analyzed_groups.append(
                self.analyze_group(
                    group_name=group_name,
                    predictions=predictions,
                    bookmaker_mode=bookmaker_mode,
                    allowed_bookmakers=allowed_bookmakers,
                )
            )

        return {
            "slate": slate,
            "bookmaker_mode": bookmaker_mode,
            "allowed_bookmakers": allowed_bookmakers,
            "groups_analyzed": len(analyzed_groups),
            "groups": analyzed_groups,
        }

    def analyze_group(
        self,
        group_name: str,
        predictions: list[dict[str, Any]],
        bookmaker_mode: str = "flexible",
        allowed_bookmakers: list[str] | None = None,
    ) -> dict[str, Any]:
        if not predictions:
            return {
                "group_name": group_name,
                "compatible": False,
                "reason": "empty_group",
                "predictions": [],
            }

        bookmaker_sets = []
        prediction_reports = []

        for prediction in predictions:
            prediction_bookmaker = prediction.get("odds_bookmaker")

            # =====================================================
            # FAST PATH:
            # prediction already has bookmaker provenance
            # =====================================================

            if prediction_bookmaker:
                available_bookmakers = [prediction_bookmaker]

                bookmaker_source = "prediction_provenance"

            else:
                available_bookmakers = self._available_bookmakers_for_prediction(
                    match_id=prediction["match_id"],
                    market=prediction["market"],
                    selection=prediction["predicted_label"],
                    allowed_bookmakers=allowed_bookmakers,
                )

                bookmaker_source = "match_odds_discovery"

            bookmaker_sets.append(set(available_bookmakers))

            prediction_reports.append(
                {
                    "prediction_id": prediction["prediction_id"],
                    "match_id": prediction["match_id"],
                    "league": prediction["league"],
                    "match": f"{prediction['home_team']} vs {prediction['away_team']}",
                    "market": prediction["market"],
                    "selection": prediction["predicted_label"],
                    "confidence": prediction["confidence"],
                    "odds": prediction["odds"],
                    "value_score": prediction["value_score"],

                    # =====================================================
                    # ODDS TRACEABILITY
                    # =====================================================

                    "odds_bookmaker": prediction.get("odds_bookmaker"),
                    "odds_market": prediction.get("odds_market"),
                    "odds_selection": prediction.get("odds_selection"),
                    "odds_retrieved_at": prediction.get("odds_retrieved_at"),
                    "odds_match_quality": prediction.get("odds_match_quality"),

                    "bookmaker_source": bookmaker_source,
                    "available_bookmakers": available_bookmakers,
                    "bookmaker_count": len(available_bookmakers),
                }
            )

        common_bookmakers = (
            set.intersection(*bookmaker_sets)
            if bookmaker_sets
            else set()
        )

        union_bookmakers = (
            set.union(*bookmaker_sets)
            if bookmaker_sets
            else set()
        )

        flexible_coverage = self._flexible_coverage(prediction_reports)

        # =====================================================
        # SAME BOOKMAKER MODE
        # =====================================================

        if bookmaker_mode == "same":
            compatible = len(common_bookmakers) > 0

            reason = (
                "shared_bookmaker_found"
                if compatible
                else "no_shared_bookmaker_found"
            )

        # =====================================================
        # PREFERRED MODE
        # =====================================================

        elif bookmaker_mode == "preferred":
            compatible = (
                flexible_coverage["covered_predictions"]
                == len(predictions)
            )

            reason = (
                "preferred_bookmaker_mode"
            )

        # =====================================================
        # COUNTRY SAFE MODE
        # =====================================================

        elif bookmaker_mode == "country_safe":
            compatible = (
                flexible_coverage["covered_predictions"]
                == len(predictions)
            )

            reason = (
                "country_safe_bookmaker_filtering"
                if allowed_bookmakers
                else "country_safe_requested_without_filters"
            )

        # =====================================================
        # FLEXIBLE MODE
        # =====================================================

        else:
            compatible = (
                flexible_coverage["covered_predictions"]
                == len(predictions)
            )

            reason = "flexible_bookmaker_mode"

        return {
            "group_name": group_name,
            "bookmaker_mode": bookmaker_mode,
            "compatible": compatible,
            "reason": reason,

            # =====================================================
            # SAME BOOKMAKER ANALYSIS
            # =====================================================

            "same_bookmaker_compatible": len(common_bookmakers) > 0,
            "common_bookmakers": sorted(common_bookmakers),
            "all_available_bookmakers": sorted(union_bookmakers),

            # =====================================================
            # EXECUTION INTELLIGENCE
            # =====================================================

            "bookmaker_diversity": len(union_bookmakers),
            "prediction_count": len(predictions),

            "flexible_coverage": flexible_coverage,
            "predictions": prediction_reports,
        }

    def _load_group_predictions(
        self,
        slate: str,
    ) -> dict[str, list[dict[str, Any]]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    pgi.group_name,

                    p.id AS prediction_id,
                    p.match_id,

                    p.market,
                    p.predicted_label,

                    p.confidence,
                    p.odds,
                    p.value_score,

                    p.odds_bookmaker,
                    p.odds_market,
                    p.odds_selection,
                    p.odds_retrieved_at,
                    p.odds_match_quality,

                    m.league,
                    m.home_team,
                    m.away_team,
                    m.kickoff_datetime

                FROM prediction_group_items pgi

                JOIN predictions p
                    ON p.id = pgi.prediction_id

                JOIN matches m
                    ON m.id = p.match_id

                WHERE pgi.slate = :slate

                ORDER BY
                    pgi.group_name ASC,
                    p.confidence DESC
                """
            ),
            {"slate": slate},
        ).mappings().all()

        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for row in rows:
            groups[row["group_name"]].append(dict(row))

        return dict(groups)

    def _available_bookmakers_for_prediction(
        self,
        match_id: int,
        market: str,
        selection: str,
        allowed_bookmakers: list[str] | None = None,
    ) -> list[str]:
        params: dict[str, Any] = {
            "match_id": match_id,
            "market": market,
            "selection": selection,
        }

        bookmaker_filter = ""

        if allowed_bookmakers:
            bookmaker_filter = "AND bookmaker = ANY(:allowed_bookmakers)"
            params["allowed_bookmakers"] = allowed_bookmakers

        rows = self.session.execute(
            text(
                f"""
                SELECT DISTINCT bookmaker
                FROM match_odds

                WHERE match_id = :match_id
                  AND market = :market
                  AND selection = :selection
                  AND bookmaker IS NOT NULL

                  {bookmaker_filter}

                ORDER BY bookmaker ASC
                """
            ),
            params,
        ).mappings().all()

        return [row["bookmaker"] for row in rows]

    def _flexible_coverage(
        self,
        prediction_reports: list[dict[str, Any]],
    ) -> dict[str, Any]:
        covered = 0

        missing = []

        bookmaker_usage: dict[str, int] = defaultdict(int)

        provenance_predictions = 0
        rediscovered_predictions = 0

        for item in prediction_reports:
            bookmakers = item["available_bookmakers"]

            if item["bookmaker_source"] == "prediction_provenance":
                provenance_predictions += 1
            else:
                rediscovered_predictions += 1

            if bookmakers:
                covered += 1

                for bookmaker in bookmakers:
                    bookmaker_usage[bookmaker] += 1

            else:
                missing.append(
                    {
                        "prediction_id": item["prediction_id"],
                        "match_id": item["match_id"],
                        "market": item["market"],
                        "selection": item["selection"],
                        "match": item["match"],
                    }
                )

        total = len(prediction_reports)

        return {
            "total_predictions": total,
            "covered_predictions": covered,
            "missing_predictions": total - covered,

            "coverage_rate": (
                round(covered / total, 4)
                if total
                else 0.0
            ),

            # =====================================================
            # TRACEABILITY ANALYTICS
            # =====================================================

            "prediction_provenance_predictions": provenance_predictions,
            "rediscovered_predictions": rediscovered_predictions,

            "missing": missing,

            "bookmaker_usage": dict(
                sorted(
                    bookmaker_usage.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ),
        }