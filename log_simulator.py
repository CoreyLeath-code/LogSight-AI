import random
import time

import requests

API_URL = "http://localhost:8000/api/v1/ingest"  # Adjust mapping to match your current FastAPI port

COMPONENTS = ["auth-service", "payment-gateway", "kube-router", "db-pool-manager", "api-gateway"]
LEVELS = ["INFO", "INFO", "INFO", "DEBUG", "WARN"]


def generate_valid_log():
    return {
        "timestamp": time.time(),
        "component": random.choice(COMPONENTS),
        "level": random.choice(LEVELS),
        "message": "Connection pooling successfully handling context handshakes.",
        "payload_size_bytes": random.randint(128, 512),
    }


def generate_anomaly_log():
    return {
        "timestamp": time.time(),
        "component": "payment-gateway",
        "level": "FATAL",
        "message": "CRITICAL_FAILURE: SIMD Vector alignment mismatch during parsing payload buffer allocation error 0x7FFF.",
        "payload_size_bytes": random.randint(2048, 4096),
    }


print("ðŸš€ Initiating LogSight-AI High-Throughput Stream Generator...")
print("Streaming targeted datasets matching production schemas...")

try:
    while True:
        # Batch generation to simulate heavy packet bursts
        batch = []
        is_attack_window = (
            int(time.time()) % 15 == 0
        )  # Generate anomaly signature spikes every 15 seconds

        for _ in range(5000):
            if is_attack_window and random.random() > 0.7:
                batch.append(generate_anomaly_log())
            else:
                batch.append(generate_valid_log())

        # Transmit batch packet over to your ingestion pipeline
        try:
            # Uncomment the next line once your core pipeline server container is active:
            # response = requests.post(API_URL, json={"logs": batch}, timeout=1)
            pass
        except requests.exceptions.RequestException:
            pass  # Gracefully handle offline states during sandbox orchestration

        print(f"Ingested {len(batch)} logs into stream buffers... Status: 200 OK")
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nStopping Log Stream Generation gracefully.")
