"""Network actuator plane - executes verified control actions."""

from __future__ import annotations

import logging
from typing import Any, Dict

from dp_guard.network_telemetry import NetworkTelemetrySource
from dp_guard.types import ActionExecutionResult, ProposedAction

logger = logging.getLogger(__name__)


class ActionExecutor:
    """
    Simulated 6G network actuator interface.

    Applies control-plane commands to the underlying telemetry source,
    modeling closed-loop effects on the network state.
    """

    def __init__(self, telemetry_source: NetworkTelemetrySource) -> None:
        """
        Initialize the action executor.

        Args:
            telemetry_source: Live telemetry source affected by actions.
        """
        self._source = telemetry_source
        self._log: list[ActionExecutionResult] = []

    @property
    def history(self) -> list[ActionExecutionResult]:
        """Return execution history."""
        return list(self._log)

    def execute(self, action: ProposedAction) -> ActionExecutionResult:
        """
        Execute a verified control action on the network.

        Args:
            action: Verified action to apply.

        Returns:
            ActionExecutionResult with outcome and side effects.
        """
        action_type = action.action_type
        params = action.parameters

        handlers: Dict[str, Any] = {
            "allow_traffic": self._exec_allow_traffic,
            "block_traffic": self._exec_block_traffic,
            "isolate_segment": self._exec_isolate_segment,
            "monitor_only": self._exec_monitor_only,
            "safe_fallback": self._exec_safe_fallback,
            "rate_limit_slice": self._exec_rate_limit,
        }

        handler = handlers.get(action_type, self._exec_safe_fallback)
        result = handler(action)
        self._log.append(result)
        logger.info("Executed action %s: %s", action_type, result.message)
        return result

    def _exec_allow_traffic(self, action: ProposedAction) -> ActionExecutionResult:
        slice_id = str(action.parameters.get("slice", "eMBB-1"))
        return ActionExecutionResult(
            action=action,
            success=True,
            message=f"Traffic allowed on slice {slice_id}",
            side_effects={"slice": slice_id, "policy": "permit"},
        )

    def _exec_block_traffic(self, action: ProposedAction) -> ActionExecutionResult:
        slice_id = str(action.parameters.get("slice", "eMBB-1"))
        self._source.apply_action_effects("block_traffic", action.parameters)
        return ActionExecutionResult(
            action=action,
            success=True,
            message=f"Blocked anomalous sessions on slice {slice_id}",
            side_effects={"slice": slice_id, "policy": "deny_anomalous"},
        )

    def _exec_isolate_segment(self, action: ProposedAction) -> ActionExecutionResult:
        slice_id = str(action.parameters.get("slice", "eMBB-1"))
        self._source.apply_action_effects("isolate_segment", action.parameters)
        return ActionExecutionResult(
            action=action,
            success=True,
            message=f"Isolated segment {slice_id}",
            side_effects={"slice": slice_id, "policy": "isolated"},
        )

    def _exec_monitor_only(self, action: ProposedAction) -> ActionExecutionResult:
        return ActionExecutionResult(
            action=action,
            success=True,
            message="Monitoring mode enabled; no policy changes applied",
            side_effects={"policy": "observe"},
        )

    def _exec_safe_fallback(self, action: ProposedAction) -> ActionExecutionResult:
        return ActionExecutionResult(
            action=action,
            success=True,
            message="Safe fallback: deny-by-default, no policy changes",
            side_effects={"policy": "deny_by_default"},
        )

    def _exec_rate_limit(self, action: ProposedAction) -> ActionExecutionResult:
        slice_id = str(action.parameters.get("slice", "eMBB-1"))
        self._source.apply_action_effects("rate_limit_slice", action.parameters)
        return ActionExecutionResult(
            action=action,
            success=True,
            message=f"Rate limit applied to slice {slice_id}",
            side_effects={"slice": slice_id, "policy": "rate_limited"},
        )
