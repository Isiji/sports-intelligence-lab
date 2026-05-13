# backend/app/services/group_bookmaker_compatibility_service.py

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class GroupBookmakerCompatibilityService:
    """
    Bookmaker compatibility analysis for prediction groups.

    Default philosophy:
    - Do not force same-bookmaker grouping.
    - Same-bookmaker compatibility is optional intelligence.
    - Flexible grouping remains the production-safe default.
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
                "reason": "empty group",
                "predictions": [],
            }

        bookmaker_sets = []
        prediction_reports = []

        for prediction in predictions:
            available_bookmakers = self._available_bookmakers_for_prediction(
                match_id=prediction["match_id"],
                market=prediction["market"],
                selection=prediction["predicted_label"],
                allowed_bookmakers=allowed_bookmakers,
            )

            bookmaker_sets.append(set(available_bookmakers))

            prediction_reports.append(
                {
                    "prediction_id": prediction["prediction_id"],
                    "match_id": prediction["match_id"],
                    "league": prediction["league"],
                    "match": f"{prediction['home_team']} vs {prediction['away_team']}",
                    "market": prediction["market"],
                    "selection": prediction["predicted_label"],
                    "available_bookmakers": available_bookmakers,
                    "bookmaker_count": len(available_bookmakers),
                }
            )

        common_bookmakers = set.intersection(*bookmaker_sets) if bookmaker_sets else set()
        union_bookmakers = set.union(*bookmaker_sets) if bookmaker_sets else set()

        flexible_coverage = self._flexible_coverage(prediction_reports)

        if bookmaker_mode == "same":
            compatible = len(common_bookmakers) > 0
            reason = (
                "all picks available under at least one shared bookmaker"
                if compatible
                else "no single bookmaker supports every pick"
            )

        elif bookmaker_mode == "preferred":
            compatible = flexible_coverage["covered_predictions"] == len(predictions)
            reason = "flexible coverage allowed; preferred bookmaker can be handled later"

        elif bookmaker_mode == "country_safe":
            compatible = flexible_coverage["covered_predictions"] == len(predictions)
            reason = "country-safe bookmaker filtering applied" if allowed_bookmakers else (
                "country_safe mode requested but no allowed_bookmakers supplied"
            )

        else:
            compatible = flexible_coverage["covered_predictions"] == len(predictions)
            reason = "flexible bookmaker mode"

        return {
            "group_name": group_name,
            "bookmaker_mode": bookmaker_mode,
            "compatible": compatible,
            "reason": reason,
            "same_bookmaker_compatible": len(common_bookmakers) > 0,
            "common_bookmakers": sorted(common_bookmakers),
            "all_available_bookmakers": sorted(union_bookmakers),
            "flexible_coverage": flexible_coverage,
            "predictions": prediction_reports,
        }

    def _load_group_predictions(self, slate: str) -> dict[str, list[dict[str, Any]]]:
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
                    m.league,
                    m.home_team,
                    m.away_team,
                    m.kickoff_datetime
                FROM prediction_group_items pgi
                JOIN predictions p ON p.id = pgi.prediction_id
                JOIN matches m ON m.id = p.match_id
                WHERE pgi.slate = :slate
                ORDER BY pgi.group_name ASC, p.confidence DESC
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

        for item in prediction_reports:
            bookmakers = item["available_bookmakers"]

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
            "coverage_rate": round(covered / total, 4) if total else 0.0,
            "missing": missing,
            "bookmaker_usage": dict(
                sorted(
                    bookmaker_usage.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ),
        }