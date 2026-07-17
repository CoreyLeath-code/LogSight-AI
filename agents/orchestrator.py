# agents/orchestrator.py
import json
import os

from anthropic import Anthropic

from .guards import CircuitBreakerException, ExecutionCircuitBreaker
from .state import AgentState


class LogSightOrchestrator:
    """
    Main Orchestrator engine coordinating specialized worker layers
    using defensive system patterns and immutable states.
    """

    def __init__(self):
        # Fallback to a placeholder if the key isn't loaded yet to prevent initialization crashes
        api_key = os.environ.get("ANTHROPIC_API_KEY", "mock-key-for-dev")
        self.client = Anthropic(api_key=api_key)
        self.breaker = ExecutionCircuitBreaker(max_loops=3, error_threshold=2)

    def process_incident(self, raw_log_data: str) -> AgentState:
        """Runs the raw logs through the structured Orchestration-Worker Pipeline."""
        state = AgentState(raw_logs=raw_log_data)
        state = state.log_step("Initializing Orchestrator Core Execution Pipeline.")

        try:
            # 1. Structure Layer (Worker 1)
            state = self._run_parser_worker(state)

            # 2. Iterative Reason/Triage Loop (Worker 2)
            while state.root_cause_analysis is None:
                self.breaker.verify_bounds(state.loop_count)

                state = self._run_analysis_worker(state)
                state.loop_count += 1
                state = state.log_step(f"Completed Triage Iteration Cycle {state.loop_count}")

            # 3. Mitigation/Resolution Synthesis (Worker 3)
            state = self._run_remediation_worker(state)
            state = state.log_step("Pipeline execution finished successfully.")
            return state

        except CircuitBreakerException as cbe:
            # Catch systemic loops/errors and gracefully degrade execution state
            state.circuit_tripped = True
            state.failure_reason = str(cbe)
            state = state.log_step(f"CRITICAL FAULT: {str(cbe)}")
            return self._handle_graceful_degradation(state)

    def _run_parser_worker(self, state: AgentState) -> AgentState:
        state = state.log_step("Invoking Log Parser Worker.")

        system_prompt = (
            "You are a strict Log Parsing Subsystem. Your sole job is to transform chaotic, "
            "unstructured system logs into a clean structured JSON array. Never output conversational prose."
        )
        user_prompt = f"Convert the following raw logs into a valid JSON array matching keys [timestamp, level, service, message]:\n{state.raw_logs}"

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # Basic validation check to keep downstream workers clean
            parsed_data = json.loads(response.content[0].text)
            return state.model_copy(update={"parsed_json": parsed_data}).log_step(
                "Log parsing complete."
            )
        except Exception as e:
            self.breaker.record_error()
            # If JSON parsing fails, fall back to string encapsulation and continue path
            fallback_json = [{"level": "UNKNOWN", "message": state.raw_logs}]
            return state.model_copy(update={"parsed_json": fallback_json}).log_step(
                f"Parser warning: {str(e)}. Using fallback format."
            )

    def _run_analysis_worker(self, state: AgentState) -> AgentState:
        state = state.log_step("Invoking Infrastructure Root-Cause Analysis Worker.")

        system_prompt = (
            "You are an expert Reliability Engineer specializing in system telemetry analysis. "
            "Identify anomalies, trace root causes, and explicitly point out security concerns."
        )
        user_prompt = f"Analyze these structured log instances to pinpoint the core architectural fault:\n{json.dumps(state.parsed_json)}"

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return state.model_copy(update={"root_cause_analysis": response.content[0].text})

    def _run_remediation_worker(self, state: AgentState) -> AgentState:
        state = state.log_step("Invoking Remediation Synthesis Worker.")

        system_prompt = "You are a DevOps Automation Agent. Generate standard operating procedures (SOPs) and runbooks based on failure reports."
        user_prompt = f"Write clear mitigation steps for this issue:\n{state.root_cause_analysis}"

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return state.model_copy(update={"recommended_actions": response.content[0].text})

    def _handle_graceful_degradation(self, state: AgentState) -> AgentState:
        """Provides a safe default output state when the circuit breaker opens."""
        return state.model_copy(
            update={
                "root_cause_analysis": "ANALYSIS HALTED: The processing safety limits were breached.",
                "recommended_actions": "MANUAL INTERVENTION REQUIRED: Please isolate this instance and review the system execution logs below.",
            }
        )
