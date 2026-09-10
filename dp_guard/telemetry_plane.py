"""Telemetry Plane — sole component with access to raw network data."""

from __future__ import annotations

from typing import Dict, Mapping

import numpy as np

from dp_guard.network_telemetry import NetworkTelemetrySource
from dp_guard.types import MetricDefinition, MetricType, NoisyObservation


class RawTelemetryStore:
    """
    Encapsulated raw telemetry dataset.

    Raw values are stored in a private attribute and cannot be modified
    or read outside the Telemetry Plane boundary.
    """

    def __init__(self, source: NetworkTelemetrySource) -> None:
        """
        Initialize the protected telemetry store from a live telemetry source.

        Args:
            source: Network telemetry source that aggregates UE session records.
        """
        self.__source = source
        self.__raw_data: Dict[str, float] = source.aggregate_metrics()

    def refresh(self) -> None:
        """Re-aggregate metrics from the underlying telemetry source."""
        self.__raw_data = self.__source.aggregate_metrics()

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


DEFAULT_METRIC_CATALOG: Dict[MetricType, MetricDefinition] = {
    MetricType.THREAT_LEVEL: MetricDefinition(
        metric_type=MetricType.THREAT_LEVEL,
        sensitivity=1.0,
        description="Max threat score across UE sessions in slice [0, 100]",
        min_epsilon=0.1,
        max_epsilon=0.8,
    ),
    MetricType.ACTIVE_CONNECTIONS: MetricDefinition(
        metric_type=MetricType.ACTIVE_CONNECTIONS,
        sensitivity=1.0,
        description="Count of active UE sessions in target slice",
        min_epsilon=0.05,
        max_epsilon=0.5,
    ),
    MetricType.ANOMALY_SCORE: MetricDefinition(
        metric_type=MetricType.ANOMALY_SCORE,
        sensitivity=5.0,
        description="Percentage of sessions flagged anomalous [0, 100]",
        min_epsilon=0.1,
        max_epsilon=0.6,
    ),
    MetricType.FAILED_AUTH_ATTEMPTS: MetricDefinition(
        metric_type=MetricType.FAILED_AUTH_ATTEMPTS,
        sensitivity=1.0,
        description="Total failed authentication attempts in slice",
        min_epsilon=0.05,
        max_epsilon=0.4,
    ),
    MetricType.SLICE_LOAD_PERCENT: MetricDefinition(
        metric_type=MetricType.SLICE_LOAD_PERCENT,
        sensitivity=2.0,
        description="Slice load as percentage of capacity [0, 100]",
        min_epsilon=0.05,
        max_epsilon=0.4,
    ),
    MetricType.PACKET_LOSS_RATE: MetricDefinition(
        metric_type=MetricType.PACKET_LOSS_RATE,
        sensitivity=0.5,
        description="Estimated packet loss rate percentage [0, 5]",
        min_epsilon=0.05,
        max_epsilon=0.3,
    ),
}


class TelemetryPlane:
    """
    Typed differentially private metric interface.

    Implements the Laplace mechanism:
        M(X) = q(X) + eta,  eta ~ Laplace(Delta1(q) / epsilon)
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

    def refresh_raw_aggregates(self) -> None:
        """Refresh encapsulated raw aggregates from the telemetry source."""
        self._store.refresh()

    def get_sensitivity(self, metric_type: MetricType) -> float:
        """
        Return L1 sensitivity Delta1(q) for a metric type.

        Args:
            metric_type: Typed metric identifier.

        Returns:
            Global L1 sensitivity bound.
        """
        return self._catalog[metric_type].sensitivity

    def get_definition(self, metric_type: MetricType) -> MetricDefinition:
        """Return full typed metric definition from catalog."""
        return self._catalog[metric_type]

    def release_metric(self, metric_type: MetricType, epsilon: float) -> NoisyObservation:
        """
        Release a differentially private aggregate via the Laplace mechanism.

        Args:
            metric_type: Typed metric to query.
            epsilon: Privacy parameter epsilon for this release.

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

        noise = float(np.random.laplace(loc=0.0, scale=scale))
        noisy_value = raw_value + noise

        return NoisyObservation(
            metric_type=metric_type,
            noisy_value=noisy_value,
            epsilon=epsilon,
            sensitivity=definition.sensitivity,
            scale=scale,
        )
