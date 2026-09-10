"""Unit tests for DP-Guard core mechanisms."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from dp_guard.admissibility_verifier import AdmissibilityVerifier
from dp_guard.network_telemetry import NetworkTelemetrySource
from dp_guard.privacy_accountant import PrivacyAccountant
from dp_guard.privacy_policy import PrivacyPolicy
from dp_guard.telemetry_plane import RawTelemetryStore, TelemetryPlane
from dp_guard.types import MetricQuery, MetricType, NoisyObservation, ProposedAction


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def telemetry_source() -> NetworkTelemetrySource:
    """Create telemetry source from test data files."""
    return NetworkTelemetrySource(
        records_path=ROOT / "data" / "ue_sessions.json",
        topology_path=ROOT / "data" / "network_slices.json",
    )


def test_telemetry_aggregates_from_real_records(telemetry_source: NetworkTelemetrySource) -> None:
    """Aggregates should reflect UE session JSON data."""
    metrics = telemetry_source.aggregate_metrics()
    assert metrics["active_connections"] == 8  # 8 eMBB-1 sessions in data
    assert metrics["threat_level"] == 71  # max threat in eMBB-1
    assert metrics["failed_auth_attempts"] == 19


def test_laplace_mechanism_adds_noise(telemetry_source: NetworkTelemetrySource) -> None:
    """DP release should differ from raw value due to noise."""
    np.random.seed(0)
    store = RawTelemetryStore(telemetry_source)
    plane = TelemetryPlane(store)
    raw = store._read_raw("threat_level")  # noqa: SLF001
    obs = plane.release_metric(MetricType.THREAT_LEVEL, epsilon=0.5)
    assert obs.noisy_value != raw
    assert obs.scale == pytest.approx(2.0)  # sensitivity 1.0 / epsilon 0.5


def test_privacy_budget_exceeded() -> None:
    """Accountant should reject queries exceeding budget."""
    accountant = PrivacyAccountant(epsilon_total=0.5)
    with pytest.raises(Exception):
        accountant.check_budget(0.6)


def test_admissibility_blocks_permissive_action() -> None:
    """Verifier should block allow_traffic when threat upper bound exceeds threshold."""
    verifier = AdmissibilityVerifier(threat_safety_threshold=30.0, beta=0.05)
    observations = [
        NoisyObservation(
            metric_type=MetricType.THREAT_LEVEL,
            noisy_value=45.0,
            epsilon=0.3,
            sensitivity=1.0,
            scale=1.0 / 0.3,
        )
    ]
    result = verifier.verify(
        ProposedAction(action_type="allow_traffic"),
        observations,
    )
    assert result.admissible is False


def test_policy_rejects_unauthorized_metric() -> None:
    """Policy should reject metrics outside role authorization for auditor."""
    from dp_guard.types import OperatorRole

    policy = PrivacyPolicy(role=OperatorRole.READONLY_AUDITOR)
    plan_query = MetricQuery(metric_type=MetricType.THREAT_LEVEL, epsilon=0.2)
    with pytest.raises(Exception):
        policy.validate_query(plan_query)


def test_audit_log_writes_jsonl(tmp_path: Path, telemetry_source: NetworkTelemetrySource) -> None:
    """Audit log should append valid JSON lines."""
    from dp_guard.audit_log import AuditLog
    from dp_guard.types import EpochResult, OrchestrationPlan

    log_path = tmp_path / "test_audit.jsonl"
    audit = AuditLog(log_path)
    epoch = EpochResult(
        intent="test",
        plan=OrchestrationPlan(queries=[]),
        proposed_action=ProposedAction(action_type="monitor_only"),
        observations=[],
        executed_action=ProposedAction(action_type="safe_fallback"),
        execution_result=None,
        admissible=False,
        verification_message="test",
        remaining_epsilon=1.0,
    )
    audit.record_epoch(epoch)
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["intent"] == "test"
