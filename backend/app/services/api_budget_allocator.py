# backend/app/services/api_budget_allocator.py

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiBudgetPlan:
    daily_limit: int
    safety_reserve: int
    usable_budget: int
    stats_budget: int
    odds_budget: int
    upcoming_odds_budget: int
    discovery_budget: int
    rebuild_budget: int


class ApiBudgetAllocator:
    """
    Production-safe daily API allocator.

    Default daily calls: 7000
    Keeps reserve so the system does not exhaust provider quota.
    """

    def __init__(
        self,
        daily_limit: int = 7000,
        safety_reserve: int = 700,
    ):
        self.daily_limit = daily_limit
        self.safety_reserve = safety_reserve

    def build_plan(self) -> ApiBudgetPlan:
        usable = max(self.daily_limit - self.safety_reserve, 0)

        stats_budget = int(usable * 0.30)
        odds_budget = int(usable * 0.40)
        upcoming_odds_budget = int(usable * 0.15)
        discovery_budget = int(usable * 0.10)
        rebuild_budget = usable - (
            stats_budget
            + odds_budget
            + upcoming_odds_budget
            + discovery_budget
        )

        return ApiBudgetPlan(
            daily_limit=self.daily_limit,
            safety_reserve=self.safety_reserve,
            usable_budget=usable,
            stats_budget=stats_budget,
            odds_budget=odds_budget,
            upcoming_odds_budget=upcoming_odds_budget,
            discovery_budget=discovery_budget,
            rebuild_budget=rebuild_budget,
        )