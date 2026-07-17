# app.py (Partial UI Integration Example)
import os

import streamlit as st

from agents.orchestrator import LogSightOrchestrator

st.set_page_config(page_title="LogSight-AI Enterprise", layout="wide")
st.title("ðŸ›¡ï¸ LogSight-AI: Multi-Agent Observability System")

# Ensure API Key is bound safely
if "ANTHROPIC_API_KEY" not in os.environ:
    os.environ["ANTHROPIC_API_KEY"] = st.sidebar.text_input("Anthropic API Key", type="password")

raw_input_logs = st.text_area(
    "Paste System Log Payload Here:",
    height=200,
    placeholder="2026-06-28T16:50:00Z ERROR auth_service: DB connection timeout ...",
)

if st.button("Run Orchestrated Analysis Pipeline"):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.error("Please provide an API key to run analysis.")
    else:
        with st.spinner("Orchestrator executing agent lifecycle layers..."):
            # Execute Pipeline
            orchestrator = LogSightOrchestrator()
            final_state = orchestrator.process_incident(raw_input_logs)

            # Layout Response Columns
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("ðŸ“‹ System Analysis Report")
                st.markdown(f"### Root Cause\n{final_state.root_cause_analysis}")
                st.markdown(f"### Recommended SOP Mitigation\n{final_state.recommended_actions}")

            with col2:
                st.subheader("âš™ï¸ Agent Orchestration Telemetry")

                # Highlight Circuit Breaker Status
                if final_state.circuit_tripped:
                    st.error(f"ðŸ”´ Circuit Breaker: OPEN\nReason: {final_state.failure_reason}")
                else:
                    st.success("ðŸŸ¢ Circuit Breaker: CLOSED (Healthy)")

                # Print explicit chronological execution trace
                st.markdown("**Execution Trace Sequence:**")
                for step in final_state.execution_steps:
                    st.info(step)
