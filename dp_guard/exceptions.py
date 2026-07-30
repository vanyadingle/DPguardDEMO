"""Custom exceptions for the DP-Guard framework."""


class PrivacyBudgetExceededError(Exception):
    """Raised when a telemetry query would exceed the remaining privacy budget."""

    def __init__(self, requested_epsilon: float, remaining_epsilon: float) -> None:
        """
        Initialize the exception with budget details.

        Args:
            requested_epsilon: Privacy cost requested for the current query.
            remaining_epsilon: Privacy budget still available.
        """
        self.requested_epsilon = requested_epsilon
        self.remaining_epsilon = remaining_epsilon
        super().__init__(
            f"Privacy budget exceeded: requested eps={requested_epsilon:.4f}, "
            f"remaining eps={remaining_epsilon:.4f}"
        )


class RawTelemetryAccessError(Exception):
    """Raised when raw telemetry is accessed outside the Telemetry Plane."""
