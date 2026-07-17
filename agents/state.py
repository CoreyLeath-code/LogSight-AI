# agents/state.py
from typing import Any

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    The immutable single source of truth passed across the LogSight-AI lifecycle.
    Prevents side effects and provides explicit telemetry for debugging.
    """

    raw_logs: str
    parsed_json: list[dict[str, Any]] | None = None
    security_threats: list[str] = Field(default_factory=list)
    root_cause_analysis: str | None = None
    recommended_actions: str | None = None

    # Observability & Guardrails Telemetry
    execution_steps: list[str] = Field(default_factory=list)
    loop_count: int = 0
    circuit_tripped: bool = False
    failure_reason: str | None = None

    def log_step(self, step_description: str) -> "AgentState":
        """Returns a new copy of state with the updated execution trace."""
        updated_steps = list(self.execution_steps) + [step_description]
        return self.model_copy(update={"execution_steps": updated_steps})
