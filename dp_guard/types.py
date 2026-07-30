"""Shared type definitions for DP-Guard."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal


class MetricType(str, Enum):
    """Supported typed metrics in the telemetry catalog."""

    THREAT_LEVEL = "threat_level"
    ACTIVE_CONNECTIONS = "active_connections"
    ANOMALY_SCORE = "anomaly_score"


@dataclass(frozen=True)
class MetricDefinition:
    """
    Typed metric metadata binding query, sensitivity, and semantic contract.

    Attributes:
        metric_type: Catalog identifier for the metric.
        sensitivity: Global L1 sensitivity Δ₁(q) for the aggregation query.
        description: Human-readable description of the metric semantics.
    """

    metric_type: MetricType
    sensitivity: float
    description: str


@dataclass(frozen=True)
class MetricQuery:
    """
    A single metric read request in an orchestration plan.

    Attributes:
        metric_type: Which typed metric to release.
        epsilon: Per-release privacy cost ε for the Laplace mechanism.
    """

    metric_type: MetricType
    epsilon: float


@dataclass
class OrchestrationPlan:
    """
    LLM-proposed sequence of DP metric reads.

    Attributes:
        queries: Ordered list of metric queries to execute.
        reasoning: Optional natural-language rationale from the LLM.
    """

    queries: List[MetricQuery]
    reasoning: str = ""


ActionType = Literal[
    "allow_traffic",
    "block_traffic",
    "isolate_segment",
    "safe_fallback",
    "monitor_only",
]


@dataclass(frozen=True)
class ProposedAction:
    """
    LLM-proposed control action against network actuators.

    Attributes:
        action_type: Command identifier from the admissible action schema.
        parameters: Optional action-specific parameters.
    """

    action_type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NoisyObservation:
    """
    Differentially private release of a single metric.

    Attributes:
        metric_type: Source metric type.
        noisy_value: Noisy aggregate returned to the orchestrator.
        epsilon: Privacy cost charged for this release.
        sensitivity: L1 sensitivity used for noise calibration.
        scale: Laplace scale b = Δ₁(q) / ε.
    """

    metric_type: MetricType
    noisy_value: float
    epsilon: float
    sensitivity: float
    scale: float


@dataclass
class EpochResult:
    """Outcome of a single DP-Guard orchestration epoch."""

    intent: str
    plan: OrchestrationPlan
    proposed_action: ProposedAction
    observations: List[NoisyObservation]
    executed_action: ProposedAction
    admissible: bool
    verification_message: str
    remaining_epsilon: float
    budget_exhausted: bool = False
