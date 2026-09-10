"""Factory for creating the appropriate LLM planner."""

from __future__ import annotations

from typing import Protocol

from dp_guard.config import DPGuardConfig
from dp_guard.mock_llm import MockLLMPlanner
from dp_guard.openai_planner import OpenAIPlanner
from dp_guard.privacy_policy import PrivacyPolicy
from dp_guard.types import NetworkContext, OrchestrationPlan, ProposedAction


class LLMPlanner(Protocol):
    """Protocol for LLM or mock plan generators."""

    def propose(
        self,
        intent: str,
        epoch_index: int,
        context: NetworkContext | None = None,
        prior_observations: list | None = None,
    ) -> tuple[OrchestrationPlan, ProposedAction]:
        """Return a metric-read plan and proposed action."""
        ...


def create_llm_planner(config: DPGuardConfig, policy: PrivacyPolicy) -> tuple[LLMPlanner, str]:
    """
    Create an LLM planner based on configuration.

    Args:
        config: Runtime configuration.
        policy: Typed privacy policy.

    Returns:
        Tuple of (planner instance, provider name string).
    """
    if config.use_mock_llm:
        return MockLLMPlanner(), "mock"

    if config.openai_api_key:
        return (
            OpenAIPlanner(
                api_key=config.openai_api_key,
                model=config.openai_model,
                policy=policy,
            ),
            f"openai:{config.openai_model}",
        )

    return MockLLMPlanner(), "mock"
