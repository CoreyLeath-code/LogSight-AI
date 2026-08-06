import random
import time
from datetime import datetime

import pandas as pd
import streamlit as st

# Setup configuration and layout
st.set_page_config(page_title="LogSight-AI Dashboard", page_icon="ðŸ”", layout="wide")

st.title("ðŸ” LogSight-AI: Intelligent Log Analysis Platform")
st.caption("Production Demostration Stack | Real-Time Anomaly Detection & Categorization")

# --- SIDEBAR: LOG GENERATOR SIMULATOR ---
st.sidebar.header("ðŸ› ï¸ Live Log Stream Simulator")
st.sidebar.markdown(
    "Simulate live infrastructure traffic to test LogSight-AI's streaming ingestion and inference."
)

service_type = st.sidebar.selectbox(
    "Target Subsystem", ["AuthService", "PaymentGateway", "QueryEngine", "Nginx-Ingress"]
)
log_rate = st.sidebar.slider("Ingestion Rate (seconds)", 0.5, 3.0, 1.0)
generate_anomaly = st.sidebar.button("ðŸš¨ Inject Malicious Payload / Anomaly")

# System state initialization
if "log_history" not in st.session_state:
    st.session_state.log_history = []


# Core Mock Inference Function
def analyze_log_line(service, msg):
    """
    Simulates the backend AI processing logic: tokenization, embedding lookup,
    and classifying severe security anomalies or system bugs.
    """
    lower_msg = msg.lower()
    if "failed" in lower_msg or "denied" in lower_msg or "sql" in lower_msg:
        return "CRITICAL", "Security Threat / Unauthorized Entry Attempt"
    elif "timeout" in lower_msg or "500" in lower_msg or "dropped" in lower_msg:
        return "ERROR", "Infrastructure Bottleneck / Null Pointer Exception"
    return "INFO", "Standard Operations"


# Append simulated streaming logs dynamically
if st.sidebar.checkbox("Start Live Stream Ingestion", value=True):
    # Base message matrix
    standard_logs = [
        "User session token validated successfully.",
        "GET /v1/models HTTP/1.1 200 OK",
        "Connection established to vector search cluster.",
        "Database connection pool health check: OK",
    ]

    anomalies = [
        "SQL Injection string detected in query parameters: SELECT * FROM users; --",
        "Fatal: Connection timeout after 5000ms to microservice upstream.",
        "Brute force threshold reached: 45 failed authentication attempts from IP 192.168.1.105",
        "OutOfMemoryError: Java heap space exhausted during log vectorization.",
    ]

    # Pick target message based on manual button trigger or random seed
    if generate_anomaly:
        raw_msg = random.choice(anomalies)
    else:
        # standard fallback simulation
        raw_msg = (
            random.choice(standard_logs) if random.random() > 0.15 else random.choice(anomalies)
        )

    level, assessment = analyze_log_line(service_type, raw_msg)

    new_log = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "Subsystem": service_type,
        "Severity": level,
        "Raw Log Message": raw_msg,
        "LogSight AI Classification": assessment,
    }

    st.session_state.log_history.insert(0, new_log)
    # Caps the browser state so memory allocations don't spill over
    if len(st.session_state.log_history) > 100:
        st.session_state.log_history.pop()

# --- MAIN DASHBOARD INTERFACE ---
log_df = pd.DataFrame(st.session_state.log_history)

if not log_df.empty:
    # High-level Metrics Row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Parsed Streams", len(log_df))
    with col2:
        critical_count = len(log_df[log_df["Severity"] == "CRITICAL"])
        st.metric(
            "Security Anomalies Blocked",
            critical_count,
            delta=f"{critical_count} Alert(s)" if critical_count > 0 else None,
            delta_color="inverse",
        )
    with col3:
        error_count = len(log_df[log_df["Severity"] == "ERROR"])
        st.metric("System Operational Errors", error_count)

    st.subheader("ðŸ“‹ Active Streaming Log Ledger (Real-Time Ingestion)")

    # Styled table row coloring using pandas styling parameters
    def color_severity(val):
        if val == "CRITICAL":
            return "background-color: rgba(255, 75, 75, 0.2); color: #ff4b4b;"
        if val == "ERROR":
            return "background-color: rgba(255, 165, 0, 0.2); color: #ffa500;"
        return (
            "background-color: rgba(0, 255, 0, 0.05); color: #00ff00;"
            if st.get_option("theme.base") == "dark"
            else ""
        )

    styled_df = log_df.style.map(color_severity, subset=["Severity"])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # Optional metric charting tracking system traffic density over time
    if st.checkbox("Show Infrastructure Load Distribution Overview"):
        st.subheader("ðŸ“Š Traffic Distribution by Subsystem")
        subsystem_counts = log_df["Subsystem"].value_counts()
        st.bar_chart(subsystem_counts)
else:
    st.info(
        "Log stream ingestion is initialized. Check the 'Start Live Stream Ingestion' box in the sidebar to begin processing payload lines."
    )

# Rerun loop logic mimicking standard polling loops
time.sleep(log_rate)
st.rerun()
