"""
DP-Guard full prototype - closed-loop security orchestrator demo.

Uses real structured UE session telemetry, optional OpenAI LLM,
typed privacy policy, DP Laplace releases, admissibility verification,
and audit logging.
"""

from __future__ import annotations

import logging
import sys

import numpy as np

from dp_guard.action_executor import ActionExecutor
from dp_guard.admissibility_verifier import AdmissibilityVerifier
from dp_guard.audit_log import AuditLog
from dp_guard.config import DPGuardConfig
from dp_guard.llm_factory import create_llm_planner
from dp_guard.network_telemetry import NetworkTelemetrySource
from dp_guard.orchestrator import Orchestrator
from dp_guard.privacy_accountant import PrivacyAccountant
from dp_guard.privacy_policy import PrivacyPolicy
from dp_guard.telemetry_plane import RawTelemetryStore, TelemetryPlane

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def build_orchestrator(config: DPGuardConfig) -> Orchestrator:
    """
    Wire all DP-Guard planes from configuration.

    Args:
        config: Runtime configuration.

    Returns:
        Fully configured Orchestrator instance.
    """
    telemetry_source = NetworkTelemetrySource(
        records_path=config.telemetry_path,
        topology_path=config.topology_path,
        target_slice="eMBB-1",
    )

    raw_store = RawTelemetryStore(telemetry_source)
    telemetry = TelemetryPlane(raw_store)
    accountant = PrivacyAccountant(epsilon_total=config.epsilon_total)
    policy = PrivacyPolicy(role=config.operator_role)
    verifier = AdmissibilityVerifier(
        threat_safety_threshold=config.threat_safety_threshold,
        anomaly_safety_threshold=config.anomaly_safety_threshold,
        beta=config.verification_beta,
    )
    llm, provider = create_llm_planner(config, policy)
    executor = ActionExecutor(telemetry_source)
    audit = AuditLog(config.audit_log_path)

    return Orchestrator(
        telemetry_plane=telemetry,
        telemetry_source=telemetry_source,
        privacy_accountant=accountant,
        verifier=verifier,
        policy=policy,
        llm_planner=llm,
        action_executor=executor,
        audit_log=audit,
        llm_provider=provider,
    )


def print_banner(config: DPGuardConfig, orchestrator: Orchestrator) -> None:
    """Print startup banner with runtime info."""
    source = orchestrator._telemetry_source  # noqa: SLF001 - demo introspection
    metrics = source.aggregate_metrics()

    print("=" * 60)
    print("DP-Guard FULL - Typed DP Security Orchestrator")
    print("=" * 60)
    print(f"gNodeB: {source.gnb_id} | Region: {source.region}")
    print(f"Target slice: eMBB-1 | UE sessions: {int(metrics['active_connections'])}")
    print(f"LLM provider: {config.use_mock_llm and 'mock (offline)' or config.openai_model}")
    print(f"Privacy budget eps_tot: {config.epsilon_total}")
    print(f"Role: {config.operator_role.value}")
    print()
    print("Raw aggregates (HIDDEN from LLM/orchestrator):")
    for key, value in metrics.items():
        print(f"  {key}: {value:.2f}")
    print()


def main() -> None:
    """Run the full DP-Guard demo with three orchestration epochs."""
    np.random.seed(42)
    config = DPGuardConfig.from_env()
    orchestrator = build_orchestrator(config)
    print_banner(config, orchestrator)

    intents = [
        "Maintain secure connectivity for eMBB slice under elevated threat watch",
        "Investigate authentication anomalies and packet loss on eMBB-1",
        "Adaptive re-assessment after prior mitigation attempts",
    ]

    for intent in intents:
        orchestrator.run_epoch(intent)

    print("\n" + "=" * 60)
    print("DEMO SUMMARY")
    print("=" * 60)
    for idx, epoch in enumerate(orchestrator.history, start=1):
        status = "OK" if epoch.admissible else "BLOCKED/FALLBACK"
        if epoch.budget_exhausted:
            status = "BUDGET EXHAUSTED"
        print(
            f"Epoch {idx}: llm={epoch.llm_provider}, "
            f"proposed={epoch.proposed_action.action_type}, "
            f"executed={epoch.executed_action.action_type}, "
            f"status={status}, eps_remaining={epoch.remaining_epsilon:.2f}"
        )

    print(f"\nAudit log: {config.audit_log_path}")
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
