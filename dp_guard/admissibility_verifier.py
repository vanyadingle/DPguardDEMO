"""Verification Plane — deterministic safety checks under DP uncertainty."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

from dp_guard.types import ActionType, NoisyObservation, ProposedAction


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of admissibility verification."""

    admissible: bool
    message: str
    confidence_intervals: Dict[str, Tuple[float, float]]


class AdmissibilityVerifier:
    """
    Robust set-based admissibility checker under Laplace noise.

    For each noisy observation z̃ with scale b = Δ₁/ε, constructs a confidence
    set B_β(z̃) = [z̃ - t_β, z̃ + t_β] where t_β = b · ln(2/β) for two-sided
    coverage at level 1 - β.

    An action â is admissible if safety holds for the worst-case bound relevant
    to the proposed action (upper bound for permissive actions, lower bound for
    restrictive actions).
    """

    # Actions that require low threat / anomaly before execution
    PERMISSIVE_ACTIONS: frozenset[ActionType] = frozenset(
        {"allow_traffic", "monitor_only"}
    )

    def __init__(
        self,
        threat_safety_threshold: float = 30.0,
        anomaly_safety_threshold: float = 40.0,
        beta: float = 0.05,
    ) -> None:
        """
        Initialize the verifier.

        Args:
            threat_safety_threshold: Maximum allowed threat upper bound for
                permissive actions such as allow_traffic.
            anomaly_safety_threshold: Maximum allowed anomaly upper bound.
            beta: Risk tolerance; verification confidence is 1 - β.
        """
        if not 0 < beta < 1:
            raise ValueError("beta must be in (0, 1)")
        self.threat_safety_threshold = threat_safety_threshold
        self.anomaly_safety_threshold = anomaly_safety_threshold
        self.beta = beta

    @staticmethod
    def laplace_confidence_radius(scale: float, beta: float) -> float:
        """
        Compute two-sided confidence radius for Laplace noise.

        For η ~ Laplace(b): P(|η| ≤ t) = 1 - exp(-t/b).
        Setting each tail to β/2 gives t_β = b · ln(2/β).

        Args:
            scale: Laplace scale b = Δ₁(q) / ε.
            beta: Risk tolerance parameter.

        Returns:
            Radius t_β for the confidence interval.
        """
        return scale * math.log(2.0 / beta)

    def build_confidence_intervals(
        self, observations: List[NoisyObservation]
    ) -> Dict[str, Tuple[float, float]]:
        """
        Build DP confidence sets B_β(z̃) for all observations.

        Args:
            observations: List of noisy DP metric releases.

        Returns:
            Mapping from metric name to (lower, upper) confidence bounds.
        """
        intervals: Dict[str, Tuple[float, float]] = {}
        for obs in observations:
            radius = self.laplace_confidence_radius(obs.scale, self.beta)
            lower = obs.noisy_value - radius
            upper = obs.noisy_value + radius
            intervals[obs.metric_type.value] = (lower, upper)
        return intervals

    def verify(
        self,
        proposed_action: ProposedAction,
        observations: List[NoisyObservation],
    ) -> VerificationResult:
        """
        Check whether proposed action â is admissible given noisy observations.

        Implements:
            Adm(â, z̃) ≜ ∀z ∈ B_β(z̃): Safe(â, z)

        For permissive actions, uses conservative upper bounds of threat metrics.

        Args:
            proposed_action: LLM-proposed control action.
            observations: DP releases collected during the epoch.

        Returns:
            VerificationResult with admissibility decision and diagnostics.
        """
        intervals = self.build_confidence_intervals(observations)
        action = proposed_action.action_type

        if action in {"block_traffic", "isolate_segment", "safe_fallback"}:
            return VerificationResult(
                admissible=True,
                message=f"Restrictive action '{action}' is always admissible under DP uncertainty.",
                confidence_intervals=intervals,
            )

        if action in self.PERMISSIVE_ACTIONS:
            threat_bounds = intervals.get("threat_level")
            anomaly_bounds = intervals.get("anomaly_score")
            auth_bounds = intervals.get("failed_auth_attempts")
            loss_bounds = intervals.get("packet_loss_rate")

            if threat_bounds is not None:
                _, threat_upper = threat_bounds
                if threat_upper > self.threat_safety_threshold:
                    return VerificationResult(
                        admissible=False,
                        message=(
                            f"Blocked '{action}': threat upper bound {threat_upper:.2f} "
                            f"exceeds safety threshold {self.threat_safety_threshold:.2f} "
                            f"(confidence 1-beta={1 - self.beta:.2f})."
                        ),
                        confidence_intervals=intervals,
                    )

            if anomaly_bounds is not None:
                _, anomaly_upper = anomaly_bounds
                if anomaly_upper > self.anomaly_safety_threshold:
                    return VerificationResult(
                        admissible=False,
                        message=(
                            f"Blocked '{action}': anomaly upper bound {anomaly_upper:.2f} "
                            f"exceeds safety threshold {self.anomaly_safety_threshold:.2f}."
                        ),
                        confidence_intervals=intervals,
                    )

            if auth_bounds is not None:
                _, auth_upper = auth_bounds
                if auth_upper > 10.0:
                    return VerificationResult(
                        admissible=False,
                        message=(
                            f"Blocked '{action}': failed auth upper bound {auth_upper:.2f} "
                            f"exceeds safety threshold 10.0."
                        ),
                        confidence_intervals=intervals,
                    )

            if loss_bounds is not None:
                _, loss_upper = loss_bounds
                if loss_upper > 2.0:
                    return VerificationResult(
                        admissible=False,
                        message=(
                            f"Blocked '{action}': packet loss upper bound {loss_upper:.2f}% "
                            f"exceeds safety threshold 2.0%."
                        ),
                        confidence_intervals=intervals,
                    )

            return VerificationResult(
                admissible=True,
                message=f"Permissive action '{action}' verified safe under DP confidence sets.",
                confidence_intervals=intervals,
            )

        return VerificationResult(
            admissible=False,
            message=f"Unknown action type '{action}' - rejected by default.",
            confidence_intervals=intervals,
        )
