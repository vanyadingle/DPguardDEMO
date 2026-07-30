"""
DP-Guard prototype demo — two consecutive orchestration epochs.

Demonstrates:
  1. DP Laplace releases with privacy budget tracking.
  2. Admissibility blocking of risky LLM-proposed actions.
  3. Budget depletion on subsequent epochs.
"""

from __future__ import annotations

import numpy as np

from dp_guard.admissibility_verifier import AdmissibilityVerifier
from dp_guard.mock_llm import MockLLMPlanner
from dp_guard.orchestrator import Orchestrator
from dp_guard.privacy_accountant import PrivacyAccountant
from dp_guard.telemetry_plane import RawTelemetryStore, TelemetryPlane


def main() -> None:
    """Run the DP-Guard skeleton demo with dummy 6G network telemetry."""
    # Reproducible noise for demo presentation
    np.random.seed(42)

    # Raw telemetry — ONLY accessible inside TelemetryPlane
    raw_store = RawTelemetryStore(
        {
            "threat_level": 45.0,       # elevated threat (above safety threshold)
            "active_connections": 1200.0,
            "anomaly_score": 38.0,
        }
    )

    telemetry = TelemetryPlane(raw_store)
    accountant = PrivacyAccountant(epsilon_total=1.2)
    verifier = AdmissibilityVerifier(
        threat_safety_threshold=30.0,
        anomaly_safety_threshold=40.0,
        beta=0.05,
    )
    llm = MockLLMPlanner()

    orchestrator = Orchestrator(
        telemetry_plane=telemetry,
        privacy_accountant=accountant,
        verifier=verifier,
        llm_planner=llm,
    )

    print("DP-Guard Prototype - Typed DP Security Orchestrator")
    print("Raw telemetry is encapsulated; orchestrator sees DP releases only.")
    print(f"True threat_level=45 (hidden), safety threshold=30\n")

    intents = [
        "Maintain connectivity for eMBB slice under nominal load",
        "Re-evaluate security posture after anomaly alert",
        "Additional adaptive query (budget stress test)",
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
            f"Epoch {idx}: proposed={epoch.proposed_action.action_type}, "
            f"executed={epoch.executed_action.action_type}, "
            f"status={status}, eps_remaining={epoch.remaining_epsilon:.2f}"
        )


if __name__ == "__main__":
    main()
