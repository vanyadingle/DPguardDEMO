"""Orchestration Plane — closed-loop event loop connecting all DP-Guard planes."""

from __future__ import annotations

from typing import List, Optional, Protocol

from dp_guard.admissibility_verifier import AdmissibilityVerifier
from dp_guard.exceptions import PrivacyBudgetExceededError
from dp_guard.privacy_accountant import PrivacyAccountant
from dp_guard.telemetry_plane import TelemetryPlane
from dp_guard.types import (
    EpochResult,
    NoisyObservation,
    OrchestrationPlan,
    ProposedAction,
)


class LLMPlanner(Protocol):
    """Protocol for LLM or mock plan generators."""

    def propose(self, intent: str, epoch_index: int) -> tuple[OrchestrationPlan, ProposedAction]:
        """Return a metric-read plan and proposed action."""
        ...


class Orchestrator:
    """
    Main DP-Guard control loop.

    The orchestrator never accesses raw telemetry. It:
      1. Receives an operator intent.
      2. Obtains an LLM plan + proposed action.
      3. Executes DP metric reads via Telemetry Plane (with Privacy Accountant).
      4. Verifies admissibility under DP uncertainty.
      5. Executes the action or triggers safe fallback.
    """

    SAFE_FALLBACK = ProposedAction(action_type="safe_fallback", parameters={"mode": "deny-by-default"})

    def __init__(
        self,
        telemetry_plane: TelemetryPlane,
        privacy_accountant: PrivacyAccountant,
        verifier: AdmissibilityVerifier,
        llm_planner: LLMPlanner,
    ) -> None:
        """
        Wire all four architectural planes.

        Args:
            telemetry_plane: DP-only metric interface.
            privacy_accountant: Privacy filter / budget tracker.
            verifier: Admissibility checker under DP uncertainty.
            llm_planner: Proposal generator (mock or real LLM).
        """
        self._telemetry = telemetry_plane
        self._accountant = privacy_accountant
        self._verifier = verifier
        self._llm = llm_planner
        self._epoch_index = 0
        self._history: List[EpochResult] = []

    @property
    def history(self) -> List[EpochResult]:
        """Return completed epoch results."""
        return list(self._history)

    def run_epoch(self, intent: str) -> EpochResult:
        """
        Execute one DP-Guard orchestration epoch.

        Args:
            intent: Sanitized operator intent (no raw telemetry).

        Returns:
            EpochResult summarizing plan execution, verification, and action.
        """
        plan, proposed_action = self._llm.propose(intent, self._epoch_index)
        observations: List[NoisyObservation] = []
        budget_exhausted = False
        verification_message = ""
        admissible = False
        executed_action = self.SAFE_FALLBACK

        print(f"\n{'=' * 60}")
        print(f"EPOCH {self._epoch_index + 1} | Intent: {intent}")
        print(f"{'=' * 60}")
        print(f"LLM Plan ({len(plan.queries)} queries): {plan.reasoning}")
        print(f"Proposed action: {proposed_action.action_type}")

        # Static type-and-budget check before execution
        try:
            self._accountant.check_plan_budget(plan)
        except PrivacyBudgetExceededError as exc:
            budget_exhausted = True
            verification_message = f"Plan rejected at budget gate: {exc}"
            print(f"[PRIVACY] {verification_message}")
            result = self._finalize_epoch(
                intent, plan, proposed_action, observations,
                executed_action, False, verification_message, budget_exhausted,
            )
            self._epoch_index += 1
            return result

        # Adaptive execution of metric reads
        for query in plan.queries:
            try:
                self._accountant.check_budget(query.epsilon)
            except PrivacyBudgetExceededError as exc:
                budget_exhausted = True
                verification_message = f"Budget exhausted mid-plan: {exc}"
                print(f"[PRIVACY] {verification_message}")
                executed_action = self.SAFE_FALLBACK
                result = self._finalize_epoch(
                    intent, plan, proposed_action, observations,
                    executed_action, False, verification_message, budget_exhausted,
                )
                self._epoch_index += 1
                return result

            obs = self._telemetry.release_metric(query.metric_type, query.epsilon)
            self._accountant.charge(query)
            observations.append(obs)
            print(
                f"  [DP-READ] {query.metric_type.value}: "
                f"z_noisy={obs.noisy_value:.2f} (eps={query.epsilon}, b={obs.scale:.2f})"
            )

        # Admissibility verification under DP uncertainty
        verification = self._verifier.verify(proposed_action, observations)
        admissible = verification.admissible
        verification_message = verification.message

        if admissible:
            executed_action = proposed_action
            print(f"[VERIFY] ADMISSIBLE - {verification_message}")
        else:
            executed_action = self.SAFE_FALLBACK
            print(f"[VERIFY] BLOCKED - {verification_message}")
            print(f"[ACTION] Safe fallback executed: {executed_action.action_type}")

        if admissible:
            print(f"[ACTION] Executed: {executed_action.action_type}")

        for metric, (lo, hi) in verification.confidence_intervals.items():
            print(f"  CI({metric}): [{lo:.2f}, {hi:.2f}] @ confidence 1-beta")

        state = self._accountant.get_state()
        print(
            f"[BUDGET] Spent eps={state.epsilon_spent:.2f} / "
            f"eps_tot={state.epsilon_total:.2f} "
            f"(remaining={state.epsilon_remaining:.2f})"
        )

        result = self._finalize_epoch(
            intent, plan, proposed_action, observations,
            executed_action, admissible, verification_message, budget_exhausted,
        )
        self._epoch_index += 1
        return result

    def _finalize_epoch(
        self,
        intent: str,
        plan: OrchestrationPlan,
        proposed_action: ProposedAction,
        observations: List[NoisyObservation],
        executed_action: ProposedAction,
        admissible: bool,
        verification_message: str,
        budget_exhausted: bool,
    ) -> EpochResult:
        """Record epoch outcome and return result object."""
        state = self._accountant.get_state()
        result = EpochResult(
            intent=intent,
            plan=plan,
            proposed_action=proposed_action,
            observations=observations,
            executed_action=executed_action,
            admissible=admissible,
            verification_message=verification_message,
            remaining_epsilon=state.epsilon_remaining,
            budget_exhausted=budget_exhausted,
        )
        self._history.append(result)
        return result
