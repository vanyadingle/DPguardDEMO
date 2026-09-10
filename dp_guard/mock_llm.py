"""Mock LLM proposal generator (fallback when OpenAI is unavailable)."""

from __future__ import annotations

from typing import List, Mapping, Optional

from dp_guard.types import (
    MetricQuery,
    MetricType,
    NetworkContext,
    OrchestrationPlan,
    ProposedAction,
)


class MockLLMPlanner:
    """
    Deterministic LLM simulator for offline demos and CI.

    Uses epoch index and remaining budget to produce reproducible plans
    that demonstrate admissibility blocking and budget depletion.
    """

    def propose(
        self,
        intent: str,
        epoch_index: int,
        context: Optional[NetworkContext] = None,
        prior_observations: Optional[List[Mapping[str, float]]] = None,
    ) -> tuple[OrchestrationPlan, ProposedAction]:
        """
        Generate a plan and proposed action for the given intent.

        Args:
            intent: Operator intent string.
            epoch_index: Zero-based epoch counter.
            context: Optional network context with budget info.
            prior_observations: Prior noisy DP observations.

        Returns:
            Tuple of (OrchestrationPlan, ProposedAction).
        """
        remaining = context.remaining_epsilon if context else 2.0

        if epoch_index == 0:
            plan = OrchestrationPlan(
                queries=[
                    MetricQuery(metric_type=MetricType.THREAT_LEVEL, epsilon=0.3),
                    MetricQuery(metric_type=MetricType.ACTIVE_CONNECTIONS, epsilon=0.2),
                    MetricQuery(metric_type=MetricType.ANOMALY_SCORE, epsilon=0.25),
                ],
                reasoning=(
                    f"Intent '{intent}': baseline threat assessment for eMBB slice."
                ),
            )
            return plan, ProposedAction(
                action_type="allow_traffic",
                parameters={"slice": "eMBB-1"},
            )

        if epoch_index == 1:
            plan = OrchestrationPlan(
                queries=[
                    MetricQuery(metric_type=MetricType.THREAT_LEVEL, epsilon=0.35),
                    MetricQuery(metric_type=MetricType.FAILED_AUTH_ATTEMPTS, epsilon=0.2),
                    MetricQuery(metric_type=MetricType.PACKET_LOSS_RATE, epsilon=0.15),
                ],
                reasoning=(
                    f"Intent '{intent}': deeper inspection after anomaly signals."
                ),
            )
            return plan, ProposedAction(
                action_type="allow_traffic",
                parameters={"slice": "eMBB-1"},
            )

        if remaining >= 0.5:
            plan = OrchestrationPlan(
                queries=[
                    MetricQuery(metric_type=MetricType.THREAT_LEVEL, epsilon=0.25),
                    MetricQuery(metric_type=MetricType.SLICE_LOAD_PERCENT, epsilon=0.15),
                ],
                reasoning=f"Intent '{intent}': recommend restrictive action.",
            )
            return plan, ProposedAction(
                action_type="block_traffic",
                parameters={"slice": "eMBB-1", "reason": "elevated_threat"},
            )

        plan = OrchestrationPlan(
            queries=[
                MetricQuery(metric_type=MetricType.THREAT_LEVEL, epsilon=0.6),
                MetricQuery(metric_type=MetricType.ANOMALY_SCORE, epsilon=0.6),
            ],
            reasoning=f"Intent '{intent}': budget stress test.",
        )
        return plan, ProposedAction(action_type="monitor_only")
