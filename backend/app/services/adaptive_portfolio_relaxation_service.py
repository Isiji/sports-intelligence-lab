# backend/app/services/adaptive_portfolio_relaxation_service.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class RelaxationStep:
    name: str
    description: str
    league_odds_filter_mode: str
    use_intelligence_filters: bool
    min_confidence: float
    min_group_odds: float
    require_odds: bool
    profile: str | None


class AdaptivePortfolioRelaxationService:
    """
    Controlled fallback planner for portfolio creation.

    It does NOT disable safety blindly.
    It recommends a staged relaxation path when strict grouping creates 0 groups.

    Default philosophy:
    - strict first
    - advisory before off
    - require odds remains true
    - intelligence filters stay enabled unless explicitly escalated
    """

    STEPS: list[RelaxationStep] = [
        RelaxationStep(
            name="STRICT_SAFE",
            description="Original strict production mode.",
            league_odds_filter_mode="strict",
            use_intelligence_filters=True,
            min_confidence=0.65,
            min_group_odds=3.0,
            require_odds=True,
            profile=None,
        ),
        RelaxationStep(
            name="ADVISORY_LEAGUE_ODDS",
            description="Keep intelligence filters, but make league odds coverage advisory.",
            league_odds_filter_mode="advisory",
            use_intelligence_filters=True,
            min_confidence=0.65,
            min_group_odds=3.0,
            require_odds=True,
            profile=None,
        ),
        RelaxationStep(
            name="LOWER_CONFIDENCE_SAFE",
            description="Keep odds required and intelligence enabled, lower confidence slightly.",
            league_odds_filter_mode="advisory",
            use_intelligence_filters=True,
            min_confidence=0.60,
            min_group_odds=3.0,
            require_odds=True,
            profile=None,
        ),
        RelaxationStep(
            name="LOWER_GROUP_ODDS",
            description="Allow smaller safer groups when opportunities are scarce.",
            league_odds_filter_mode="advisory",
            use_intelligence_filters=True,
            min_confidence=0.60,
            min_group_odds=2.0,
            require_odds=True,
            profile=None,
        ),
        RelaxationStep(
            name="RESEARCH_ONLY_RELAXED",
            description="Research-only fallback. Still requires odds, but disables intelligence filters.",
            league_odds_filter_mode="advisory",
            use_intelligence_filters=False,
            min_confidence=0.60,
            min_group_odds=2.0,
            require_odds=True,
            profile=None,
        ),
    ]

    def __init__(self, session: Session):
        self.session = session

    def recommend(self, slate: str) -> dict[str, Any]:
        prediction_summary = self._prediction_summary(slate)
        rejection_summary = self._rejection_summary(slate)
        group_summary = self._group_summary(slate)

        recommended_step = self._select_recommended_step(
            prediction_summary=prediction_summary,
            group_summary=group_summary,
        )

        return {
            "slate": slate,
            "prediction_summary": prediction_summary,
            "group_summary": group_summary,
            "rejection_summary": rejection_summary,
            "recommended_step": recommended_step,
            "all_steps": [self._step_to_dict(step) for step in self.STEPS],
            "recommended_command": self._command_for_step(
                slate=slate,
                step_name=recommended_step["name"],
            ),
        }

    def _prediction_summary(self, slate: str) -> dict[str, Any]:
        row = self.session.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_predictions,
                    COUNT(DISTINCT match_id) AS unique_matches,
                    COUNT(*) FILTER (WHERE odds IS NOT NULL) AS predictions_with_odds,
                    COUNT(*) FILTER (WHERE confidence >= 0.65) AS confidence_65_plus,
                    COUNT(*) FILTER (WHERE confidence >= 0.60) AS confidence_60_plus,
                    ROUND(AVG(confidence)::numeric, 4) AS avg_confidence
                FROM predictions
                WHERE slate = :slate
                """
            ),
            {"slate": slate},
        ).mappings().first()

        return dict(row)

    def _group_summary(self, slate: str) -> dict[str, Any]:
        row = self.session.execute(
            text(
                """
                SELECT
                    COUNT(*) AS group_items,
                    COUNT(DISTINCT group_name) AS groups,
                    COUNT(DISTINCT prediction_id) AS grouped_predictions
                FROM prediction_group_items
                WHERE slate = :slate
                """
            ),
            {"slate": slate},
        ).mappings().first()

        return dict(row)

    def _rejection_summary(self, slate: str) -> dict[str, Any]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    m.league,
                    p.market,
                    COUNT(*) AS predictions,
                    COUNT(*) FILTER (WHERE p.odds IS NULL) AS missing_odds,
                    COUNT(*) FILTER (WHERE p.confidence < 0.65) AS below_65_confidence,
                    COUNT(*) FILTER (WHERE p.confidence >= 0.65) AS above_65_confidence
                FROM predictions p
                JOIN matches m ON m.id = p.match_id
                WHERE p.slate = :slate
                GROUP BY m.league, p.market
                ORDER BY predictions DESC
                LIMIT 50
                """
            ),
            {"slate": slate},
        ).mappings().all()

        return {
            "by_league_market": [dict(row) for row in rows],
        }

    def _select_recommended_step(
        self,
        prediction_summary: dict[str, Any],
        group_summary: dict[str, Any],
    ) -> dict[str, Any]:
        groups = int(group_summary.get("groups") or 0)

        if groups > 0:
            return {
                "name": "STRICT_SAFE",
                "reason": "groups already exist; no relaxation needed",
            }

        predictions_with_odds = int(prediction_summary.get("predictions_with_odds") or 0)
        confidence_65_plus = int(prediction_summary.get("confidence_65_plus") or 0)
        confidence_60_plus = int(prediction_summary.get("confidence_60_plus") or 0)

        if predictions_with_odds <= 0:
            return {
                "name": "NO_RELAXATION",
                "reason": "no predictions with odds; ingest more upcoming odds first",
            }

        if confidence_65_plus >= 4:
            return {
                "name": "ADVISORY_LEAGUE_ODDS",
                "reason": "enough high-confidence odds-backed predictions exist, but strict league odds coverage blocked groups",
            }

        if confidence_60_plus >= 4:
            return {
                "name": "LOWER_CONFIDENCE_SAFE",
                "reason": "not enough 0.65+ predictions, but enough 0.60+ odds-backed candidates exist",
            }

        if predictions_with_odds >= 4:
            return {
                "name": "LOWER_GROUP_ODDS",
                "reason": "odds-backed candidates exist, but strict confidence/group constraints are too tight",
            }

        return {
            "name": "NO_RELAXATION",
            "reason": "not enough odds-backed predictions; ingest more odds or increase prediction slate size",
        }

    def _command_for_step(self, slate: str, step_name: str) -> str:
        if step_name == "NO_RELAXATION":
            return (
                "python -m app.cli ingest-ecosystem-odds --limit 300; "
                f"python -m app.cli predict-football --slate {slate} --limit 80 --require-odds"
            )

        step = next(item for item in self.STEPS if item.name == step_name)

        intelligence_flag = (
            "--use-intelligence-filters"
            if step.use_intelligence_filters
            else "--no-intelligence-filters"
        )

        require_odds_flag = "--require-odds" if step.require_odds else ""

        profile_flag = f"--profile {step.profile}" if step.profile else ""

        return (
            f"python -m app.cli create-groups "
            f"--slate {slate} "
            f"--min-confidence {step.min_confidence} "
            f"--min-group-odds {step.min_group_odds} "
            f"--league-odds-filter-mode {step.league_odds_filter_mode} "
            f"{intelligence_flag} "
            f"{require_odds_flag} "
            f"{profile_flag}"
        ).strip()

    def _step_to_dict(self, step: RelaxationStep) -> dict[str, Any]:
        return {
            "name": step.name,
            "description": step.description,
            "league_odds_filter_mode": step.league_odds_filter_mode,
            "use_intelligence_filters": step.use_intelligence_filters,
            "min_confidence": step.min_confidence,
            "min_group_odds": step.min_group_odds,
            "require_odds": step.require_odds,
            "profile": step.profile,
        }