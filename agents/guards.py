# agents/guards.py
class CircuitBreakerException(Exception):
    """Custom exception raised when system constraints are violated."""

    pass


class ExecutionCircuitBreaker:
    """
    Monitors system bounds to prevent infinite tool-use or self-correction loops.
    """

    def __init__(self, max_loops: int = 3, error_threshold: int = 2):
        self.max_loops = max_loops
        self.error_threshold = error_threshold
        self.current_errors = 0
        self.status = "CLOSED"  # CLOSED, OPEN

    def verify_bounds(self, current_loops: int):
        """Checks if the system has broken execution bounds."""
        if current_loops >= self.max_loops:
            self.status = "OPEN"
            raise CircuitBreakerException(
                f"Circuit Breaker Opened: Maximum execution loop count ({self.max_loops}) exceeded."
            )

    def record_error(self):
        """Tracks consecutive downstream errors."""
        self.current_errors += 1
        if self.current_errors >= self.error_threshold:
            self.status = "OPEN"
            raise CircuitBreakerException(
                "Circuit Breaker Opened: Downstream tools exceeded maximum continuous error thresholds."
            )
