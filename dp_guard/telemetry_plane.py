"""Telemetry Plane — sole component with access to raw network data."""

from __future__ import annotations

from typing import Dict, Mapping

import numpy as np

from dp_guard.types import MetricDefinition, MetricType, NoisyObservation


class RawTelemetryStore:
    """
    Encapsulated raw telemetry dataset.

    Raw values are stored in a private attribute and cannot be modified
    or read outside the Telemetry Plane boundary.
    """

    def __init__(self, initial_data: Mapping[str, float]) -> None:
        """
        Initialize the protected telemetry store.

        Args:
            initial_data: Mapping of metric names to raw numeric values.
        """
        self.__raw_data: Dict[str, float] = dict(initial_data)

    def _read_raw(self, metric_key: str) -> float:
        """
        Privileged read used only by TelemetryPlane.

        Args:
            metric_key: Internal key for the raw metric.

        Returns:
            Raw aggregate value q(X).
        """
        if metric_key not in self.__raw_data:
            raise KeyError(f"Unknown raw metric key: {metric_key}")
        return self.__raw_data[metric_key]


# Default metric catalog with L1 sensitivity metadata (Δ₁)
DEFAULT_METRIC_CATALOG: Dict[MetricType, MetricDefinition] = {
    MetricType.THREAT_LEVEL: MetricDefinition(
        metric_type=MetricType.THREAT_LEVEL,
        sensitivity=1.0,
        description="Aggregated threat score in range [0, 100]",
    ),
    MetricType.ACTIVE_CONNECTIONS: MetricDefinition(
        metric_type=MetricType.ACTIVE_CONNECTIONS,
        sensitivity=5.0,
        description="Count of active UE sessions (bounded per-record contribution)",
    ),
    MetricType.ANOMALY_SCORE: MetricDefinition(
        metric_type=MetricType.ANOMALY_SCORE,
        sensitivity=2.0,
        description="Network anomaly risk score",
    ),
}


class TelemetryPlane:
    """
    Typed differentially private metric interface.

    Implements the Laplace mechanism:
        M(X) = q(X) + η,  η ~ Laplace(Δ₁(q) / ε)
    """

    def __init__(
        self,
        store: RawTelemetryStore,
        catalog: Mapping[MetricType, MetricDefinition] | None = None,
    ) -> None:
        """
        Create the telemetry plane.

        Args:
            store: Encapsulated raw telemetry dataset.
            catalog: Typed metric catalog with sensitivity metadata.
        """
        self._store = store
        self._catalog: Dict[MetricType, MetricDefinition] = dict(
            catalog or DEFAULT_METRIC_CATALOG
        )

    def get_sensitivity(self, metric_type: MetricType) -> float:
        """
        Return L1 sensitivity Δ₁(q) for a metric type.

        Args:
            metric_type: Typed metric identifier.

        Returns:
            Global L1 sensitivity bound.
        """
        return self._catalog[metric_type].sensitivity

    def release_metric(self, metric_type: MetricType, epsilon: float) -> NoisyObservation:
        """
        Release a differentially private aggregate via the Laplace mechanism.

        Args:
            metric_type: Typed metric to query.
            epsilon: Privacy parameter ε for this release.

        Returns:
            NoisyObservation containing the DP release and calibration metadata.

        Raises:
            ValueError: If epsilon is non-positive.
            KeyError: If metric_type is unknown.
        """
        if epsilon <= 0:
            raise ValueError("epsilon must be positive")

        definition = self._catalog[metric_type]
        raw_value = self._store._read_raw(metric_type.value)
        scale = definition.sensitivity / epsilon

        # Laplace mechanism: η ~ Laplace(b), b = Δ₁(q) / ε
        noise = float(np.random.laplace(loc=0.0, scale=scale))
        noisy_value = raw_value + noise

        return NoisyObservation(
            metric_type=metric_type,
            noisy_value=noisy_value,
            epsilon=epsilon,
            sensitivity=definition.sensitivity,
            scale=scale,
        )
