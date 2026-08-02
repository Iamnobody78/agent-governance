"""agent-governance telemetry — OTel + GAAT governance observability.

Layer 3 standardization: exports governance decisions as OpenTelemetry
compatible traces and metrics for visualization in Grafana/Prometheus.
"""

from telemetry.otel_exporter import (
    GovernanceTelemetry,
    GTSEvent,
    DecisionVerdict,
    PolicyCategory,
    get_telemetry,
    shutdown_telemetry,
)

__all__ = [
    "GovernanceTelemetry",
    "GTSEvent",
    "DecisionVerdict",
    "PolicyCategory",
    "get_telemetry",
    "shutdown_telemetry",
]
