"""Transport security configuration tests (without broker credentials or network)."""

from __future__ import annotations

import ssl

import pytest

from logsight.kafka_security import kafka_security_settings


def test_default_dev_mode_is_explicit_plaintext() -> None:
    assert kafka_security_settings({}) == {"security_protocol": "PLAINTEXT"}


@pytest.mark.parametrize(
    "environment",
    [
        {"LOGSIGHT_KAFKA_SECURITY_PROTOCOL": "SASL_PLAINTEXT"},
        {"LOGSIGHT_KAFKA_SECURITY_PROTOCOL": "PLAINTEXT", "LOGSIGHT_KAFKA_SASL_PASSWORD": "test"},
        {"LOGSIGHT_KAFKA_SSL_CA_FILE": "/some/path"},
        {"LOGSIGHT_KAFKA_SECURITY_PROTOCOL": "SSL", "LOGSIGHT_KAFKA_SASL_USERNAME": "test"},
        {"LOGSIGHT_KAFKA_SECURITY_PROTOCOL": "SASL_SSL", "LOGSIGHT_KAFKA_SASL_MECHANISM": "PLAIN"},
        {
            "LOGSIGHT_KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
            "LOGSIGHT_KAFKA_SASL_MECHANISM": "UNSUPPORTED",
            "LOGSIGHT_KAFKA_SASL_USERNAME": "test",
            "LOGSIGHT_KAFKA_SASL_PASSWORD": "test",
        },
        {"LOGSIGHT_KAFKA_SECURITY_PROTOCOL": "SSL", "LOGSIGHT_KAFKA_SSL_CA_FILE": "/missing-ca.pem"},
    ],
)
def test_invalid_and_unencrypted_secret_configurations_are_rejected(
    environment: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        kafka_security_settings(environment)


def test_tls_mode_uses_verified_ssl_context() -> None:
    options = kafka_security_settings({"LOGSIGHT_KAFKA_SECURITY_PROTOCOL": "SSL"})
    assert options["security_protocol"] == "SSL"
    assert isinstance(options["ssl_context"], ssl.SSLContext)
    assert options["ssl_context"].verify_mode == ssl.CERT_REQUIRED
    assert options["ssl_context"].check_hostname is True


def test_sasl_ssl_mode_requires_credentials_and_verified_tls() -> None:
    options = kafka_security_settings(
        {
            "LOGSIGHT_KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
            "LOGSIGHT_KAFKA_SASL_MECHANISM": "SCRAM-SHA-512",
            "LOGSIGHT_KAFKA_SASL_USERNAME": "example",
            "LOGSIGHT_KAFKA_SASL_PASSWORD": "sample-not-a-real-secret",
        }
    )
    assert options["security_protocol"] == "SASL_SSL"
    assert options["sasl_mechanism"] == "SCRAM-SHA-512"
    assert options["sasl_plain_username"] == "example"
    assert options["sasl_plain_password"] == "sample-not-a-real-secret"
    assert options["ssl_context"].check_hostname
