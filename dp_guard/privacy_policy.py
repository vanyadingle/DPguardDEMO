"""Typed privacy policy plane with role-based access control."""

from __future__ import annotations

from typing import Dict, Mapping, Set

from dp_guard.exceptions import PolicyViolationError
from dp_guard.telemetry_plane import DEFAULT_METRIC_CATALOG
from dp_guard.types import (
    ActionType,
    MetricDefinition,
    MetricQuery,
    MetricType,
    OperatorRole,
    OrchestrationPlan,
    ProposedAction,
)


# Admissible actions per role
ROLE_ACTIONS: Dict[OperatorRole, Set[ActionType]] = {
    OperatorRole.SECURITY_OPERATOR: {
        "allow_traffic",
        "block_traffic",
        "isolate_segment",
        "monitor_only",
        "safe_fallback",
        "rate_limit_slice",
    },
    OperatorRole.NETWORK_ADMIN: {
        "allow_traffic",
        "monitor_only",
        "rate_limit_slice",
        "safe_fallback",
    },
    OperatorRole.READONLY_AUDITOR: {
        "monitor_only",
        "safe_fallback",
    },
}


class PrivacyPolicy:
    """
    Typed access policy Pi: Role -> authorized metric types and constraints.

    Enforces:
      - Role authorization for metric types
      - Per-metric epsilon bounds [min_epsilon, max_epsilon]
      - Action authorization per role
    """

    def __init__(
        self,
        role: OperatorRole,
        catalog: Mapping[MetricType, MetricDefinition] | None = None,
    ) -> None:
        """
        Initialize policy for a given operator role.

        Args:
            role: Active operator role for this orchestration session.
            catalog: Typed metric catalog with authorization metadata.
        """
        self._role = role
        self._catalog: Dict[MetricType, MetricDefinition] = dict(
            catalog or DEFAULT_METRIC_CATALOG
        )

    @property
    def role(self) -> OperatorRole:
        """Return the active operator role."""
        return self._role

    def authorized_metrics(self) -> Set[MetricType]:
        """Return metric types authorized for the active role."""
        return {
            metric_type
            for metric_type, definition in self._catalog.items()
            if self._role in definition.authorized_roles
            or self._role == OperatorRole.NETWORK_ADMIN
        }

    def authorized_actions(self) -> Set[ActionType]:
        """Return actions authorized for the active role."""
        return set(ROLE_ACTIONS.get(self._role, {"safe_fallback"}))

    def validate_query(self, query: MetricQuery) -> None:
        """
        Validate a single metric query against typed policy.

        Args:
            query: Proposed metric read with epsilon cost.

        Raises:
            PolicyViolationError: If query violates typed policy constraints.
        """
        if query.metric_type not in self.authorized_metrics():
            raise PolicyViolationError(
                f"Role '{self._role.value}' not authorized for metric '{query.metric_type.value}'"
            )

        definition = self._catalog[query.metric_type]
        if query.epsilon < definition.min_epsilon or query.epsilon > definition.max_epsilon:
            raise PolicyViolationError(
                f"Epsilon {query.epsilon} for '{query.metric_type.value}' "
                f"outside allowed range [{definition.min_epsilon}, {definition.max_epsilon}]"
            )

    def validate_plan(self, plan: OrchestrationPlan) -> None:
        """
        Validate all queries in an orchestration plan.

        Args:
            plan: LLM-proposed plan.

        Raises:
            PolicyViolationError: If any query violates policy.
        """
        for query in plan.queries:
            self.validate_query(query)

    def validate_action(self, action: ProposedAction) -> None:
        """
        Validate proposed action against role authorization.

        Args:
            action: LLM-proposed control action.

        Raises:
            PolicyViolationError: If action is not authorized for the role.
        """
        if action.action_type not in self.authorized_actions():
            raise PolicyViolationError(
                f"Role '{self._role.value}' not authorized for action '{action.action_type}'"
            )

    def build_llm_schema_context(self) -> Dict[str, object]:
        """
        Build sanitized schema context for LLM prompting.

        Returns:
            Dictionary describing authorized metrics, actions, and epsilon bounds.
        """
        metrics = []
        for metric_type in self.authorized_metrics():
            definition = self._catalog[metric_type]
            metrics.append(
                {
                    "name": metric_type.value,
                    "description": definition.description,
                    "min_epsilon": definition.min_epsilon,
                    "max_epsilon": definition.max_epsilon,
                }
            )
        return {
            "role": self._role.value,
            "authorized_metrics": metrics,
            "authorized_actions": sorted(self.authorized_actions()),
        }
