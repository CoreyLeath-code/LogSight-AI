"""Validated Kafka transport configuration for the experimental ingestion path.

Local PLAINTEXT remains the explicit development default. SASL over plaintext
is rejected; deployed environments must configure TLS and access controls.
"""

from __future__ import annotations

import os
import ssl
from collections.abc import Mapping
from typing import Any


def kafka_security_settings(
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ if environment is None else environment
    protocol = env.get("LOGSIGHT_KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").strip().upper()
    if protocol not in {"PLAINTEXT", "SSL", "SASL_SSL"}:
        raise ValueError("Kafka protocol must be PLAINTEXT, SSL, or SASL_SSL")

    ca_file = env.get("LOGSIGHT_KAFKA_SSL_CA_FILE", "").strip()
    mechanism = env.get("LOGSIGHT_KAFKA_SASL_MECHANISM", "").strip().upper()
    username = env.get("LOGSIGHT_KAFKA_SASL_USERNAME", "")
    password = env.get("LOGSIGHT_KAFKA_SASL_PASSWORD", "")
    has_sasl = bool(mechanism or username or password)

    if protocol == "PLAINTEXT":
        if ca_file or has_sasl:
            raise ValueError("Kafka TLS or SASL credentials require an encrypted protocol")
        return {"security_protocol": "PLAINTEXT"}

    try:
        context = ssl.create_default_context(cafile=ca_file or None)
    except (OSError, ssl.SSLError) as exc:
        raise ValueError("Invalid Kafka CA configuration") from exc
    settings: dict[str, Any] = {"security_protocol": protocol, "ssl_context": context}

    if protocol == "SSL":
        if has_sasl:
            raise ValueError("Kafka SASL settings require SASL_SSL")
        return settings

    if mechanism not in {"PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"}:
        raise ValueError("Unsupported Kafka SASL mechanism")
    if not username or not password:
        raise ValueError("Kafka SASL_SSL requires username and password")
    settings.update(
        sasl_mechanism=mechanism,
        sasl_plain_username=username,
        sasl_plain_password=password,
    )
    return settings
