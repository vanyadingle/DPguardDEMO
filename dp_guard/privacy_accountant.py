"""Privacy Policy Plane — privacy budget tracking and filtering."""

from __future__ import annotations

from dataclasses import dataclass

from dp_guard.exceptions import PrivacyBudgetExceededError
from dp_guard.types import MetricQuery, OrchestrationPlan


@dataclass
class PrivacyBudgetState:
    """Snapshot of the privacy accountant state."""

    epsilon_total: float
    epsilon_spent: float
    epsilon_remaining: float
    query_count: int


class PrivacyAccountant:
    """
    Privacy filter / odometer for adaptive LLM-driven query patterns.

    Before any telemetry read, verifies that the requested ε does not exceed
    the remaining budget ε_tot.
    """

    def __init__(self, epsilon_total: float) -> None:
        """
        Initialize the privacy accountant.

        Args:
            epsilon_total: Total privacy budget ε_tot for the time window.
        """
        if epsilon_total <= 0:
            raise ValueError("epsilon_total must be positive")
        self._epsilon_total = epsilon_total
        self._epsilon_spent = 0.0
        self._query_count = 0

    @property
    def epsilon_remaining(self) -> float:
        """Return remaining privacy budget."""
        return self._epsilon_total - self._epsilon_spent

    @property
    def epsilon_total(self) -> float:
        """Return configured total privacy budget."""
        return self._epsilon_total

    def check_budget(self, requested_epsilon: float) -> None:
        """
        Privacy filter: verify budget before executing a query.

        Args:
            requested_epsilon: Privacy cost ε for the upcoming release.

        Raises:
            PrivacyBudgetExceededError: If requested ε exceeds remaining budget.
            ValueError: If requested_epsilon is non-positive.
        """
        if requested_epsilon <= 0:
            raise ValueError("requested_epsilon must be positive")
        if requested_epsilon - self.epsilon_remaining > 1e-9:
            raise PrivacyBudgetExceededError(
                requested_epsilon=requested_epsilon,
                remaining_epsilon=self.epsilon_remaining,
            )

    def check_plan_budget(self, plan: OrchestrationPlan) -> None:
        """
        Verify that the cumulative cost of a plan fits the remaining budget.

        Args:
            plan: LLM-proposed orchestration plan.

        Raises:
            PrivacyBudgetExceededError: If plan cost exceeds remaining budget.
        """
        total_cost = sum(query.epsilon for query in plan.queries)
        if total_cost - self.epsilon_remaining > 1e-9:
            raise PrivacyBudgetExceededError(
                requested_epsilon=total_cost,
                remaining_epsilon=self.epsilon_remaining,
            )

    def charge(self, query: MetricQuery) -> None:
        """
        Deduct privacy cost after a successful DP release.

        Args:
            query: Executed metric query with its ε cost.
        """
        self.check_budget(query.epsilon)
        self._epsilon_spent += query.epsilon
        self._query_count += 1

    def get_state(self) -> PrivacyBudgetState:
        """Return a snapshot of current budget utilization."""
        return PrivacyBudgetState(
            epsilon_total=self._epsilon_total,
            epsilon_spent=self._epsilon_spent,
            epsilon_remaining=self.epsilon_remaining,
            query_count=self._query_count,
        )
