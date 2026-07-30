"""Mock LLM proposal generator for the orchestration skeleton."""

from __future__ import annotations

from dp_guard.types import (
    MetricQuery,
    MetricType,
    OrchestrationPlan,
    ProposedAction,
)


class MockLLMPlanner:
    """
    Simulates an LLM that proposes metric-read plans and control actions.

    In the full system this would call OpenAI or another model; here we use
    deterministic rules so the demo is reproducible for academic presentation.
    """

    def propose(self, intent: str, epoch_index: int) -> tuple[OrchestrationPlan, ProposedAction]:
        """
        Generate a plan and proposed action for the given intent.

        Epoch 0: reads threat + connections, proposes allow_traffic (may pass
                  or fail depending on DP noise).
        Epoch 1: reads more metrics with higher ε cost, proposes allow_traffic
                  (likely blocked due to high true threat_level=45).
        Epoch 2+: minimal plan to demonstrate budget exhaustion.

        Args:
            intent: Operator intent string (sanitized context for the LLM).
            epoch_index: Zero-based epoch counter.

        Returns:
            Tuple of (OrchestrationPlan, ProposedAction).
        """
        if epoch_index == 0:
            plan = OrchestrationPlan(
                queries=[
                    MetricQuery(metric_type=MetricType.THREAT_LEVEL, epsilon=0.4),
                    MetricQuery(metric_type=MetricType.ACTIVE_CONNECTIONS, epsilon=0.3),
                ],
                reasoning=(
                    f"Intent '{intent}': assess threat and load before allowing traffic."
                ),
            )
            action = ProposedAction(action_type="allow_traffic", parameters={"slice": "eMBB-1"})
            return plan, action

        if epoch_index == 1:
            plan = OrchestrationPlan(
                queries=[
                    MetricQuery(metric_type=MetricType.THREAT_LEVEL, epsilon=0.3),
                    MetricQuery(metric_type=MetricType.ANOMALY_SCORE, epsilon=0.2),
                ],
                reasoning=(
                    f"Intent '{intent}': deeper inspection; still recommend allow_traffic."
                ),
            )
            action = ProposedAction(action_type="allow_traffic", parameters={"slice": "eMBB-1"})
            return plan, action

        # Later epochs: expensive plan to trigger budget exhaustion
        plan = OrchestrationPlan(
            queries=[
                MetricQuery(metric_type=MetricType.THREAT_LEVEL, epsilon=0.6),
                MetricQuery(metric_type=MetricType.ANOMALY_SCORE, epsilon=0.6),
            ],
            reasoning=f"Intent '{intent}': additional reads after prior epochs.",
        )
        action = ProposedAction(action_type="monitor_only")
        return plan, action
