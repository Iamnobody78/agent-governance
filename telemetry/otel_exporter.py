"""
OpenTelemetry + GAAT Governance Telemetry Exporter
====================================================

Integrates governance decision tracking with OpenTelemetry standards
and the GAAT (Governance-Aware Agent Telemetry) reference architecture.

Standard:
  OpenTelemetry — vendor-neutral observability framework for traces,
  metrics, and logs consumed by Grafana/Prometheus/Datadog.

Reference: GAAT (arXiv 2026) — Governance-Aware Agent Telemetry
           "GTS schema extends OpenTelemetry for governance decisions"

Architecture (Layer 3 — Standardization & Interop):
  All 5 core modules → GovernanceTelemetry.trace_decision()
  └── OTel Span/Trace → Grafana dashboard
  └── GAAT GTS events → governance execution bus

Usage:
    from telemetry import GovernanceTelemetry

    telemetry = GovernanceTelemetry(service_name="agent-governance")
    telemetry.record_policy_decision(
        module="GodelianBoundary",
        operation="evaluate",
        verdict=DecisionVerdict.ALLOW,
    )
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterator


# ── Attempt OTel import ────────────────────────────────────────────────────────

try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = metrics = None  # type: ignore


# ── Enums ──────────────────────────────────────────────────────────────────────

class DecisionVerdict(str, Enum):
    """Governance decision verdicts."""
    ALLOW = "allow"
    DENY = "deny"
    DEFER = "defer"
    MODIFY = "modify"
    EXTERNALIZE = "externalize"
    ERROR = "error"


class PolicyCategory(str, Enum):
    """GAAT policy categories."""
    SECURITY = "security"
    PRIVACY = "privacy"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"
    ETHICAL = "ethical"
    FINANCIAL = "financial"
    SAFETY = "safety"


# ── GAAT GTS Schema ────────────────────────────────────────────────────────────

@dataclass
class GTSEvent:
    """Governance Telemetry Schema (GTS) — GAAT-compatible event.

    Extends OpenTelemetry spans with governance-specific attributes
    as defined in the GAAT reference architecture.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    module: str = ""
    operation: str = ""
    verdict: DecisionVerdict = DecisionVerdict.ALLOW
    policy_category: PolicyCategory = PolicyCategory.SECURITY
    policy_name: str = ""
    agent_id: str = ""
    session_id: str = ""
    duration_ms: float = 0.0
    risk_score: float = 0.0
    confidence: float = 1.0
    reason: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    parent_decision_id: str = ""

    def to_otel_attributes(self) -> dict[str, Any]:
        return {
            "governance.module": self.module,
            "governance.operation": self.operation,
            "governance.verdict": self.verdict.value,
            "governance.policy_category": self.policy_category.value,
            "governance.policy_name": self.policy_name,
            "governance.agent_id": self.agent_id,
            "governance.session_id": self.session_id,
            "governance.risk_score": self.risk_score,
            "governance.confidence": self.confidence,
            "governance.event_id": self.event_id,
        }

    def to_log_format(self) -> str:
        return json.dumps({
            "ts": self.timestamp,
            "event_id": self.event_id,
            "module": self.module,
            "op": self.operation,
            "verdict": self.verdict.value,
            "policy": self.policy_name,
            "risk": self.risk_score,
            "conf": self.confidence,
            "reason": self.reason[:200],
        }, ensure_ascii=False)


# ── GovernanceTelemetry ────────────────────────────────────────────────────────

class GovernanceTelemetry:
    """Governance-aware telemetry exporter.

    Provides a unified interface for recording governance decisions
    as OpenTelemetry spans (when OTel SDK is installed) and GAAT
    GTS events (for governance execution bus consumption).
    """

    def __init__(
        self,
        service_name: str = "agent-governance",
        otlp_endpoint: str = "",
        log_file: str = "governance_telemetry.log",
        enable_otel: bool = True,
        enable_file_fallback: bool = True,
    ):
        self.service_name = service_name
        self.log_file = log_file
        self.enable_file_fallback = enable_file_fallback
        self._otel_ready = False
        self._tracer = None
        self._meter = None
        self._policy_counter = None
        self._decision_latency = None
        self._start_time = time.time()

        if enable_otel and OTEL_AVAILABLE and otlp_endpoint:
            self._init_otel(otlp_endpoint)
        elif enable_otel and OTEL_AVAILABLE:
            self._init_otel_console()

    def _init_otel(self, endpoint: str):
        try:
            resource = Resource.create({"service.name": self.service_name})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)  # type: ignore
            self._tracer = trace.get_tracer(self.service_name)
            self._otel_ready = True
        except Exception:
            self._otel_ready = False

    def _init_otel_console(self):
        try:
            resource = Resource.create({"service.name": self.service_name})
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            trace.set_tracer_provider(provider)  # type: ignore
            self._tracer = trace.get_tracer(self.service_name)
            self._otel_ready = True
        except Exception:
            self._otel_ready = False

    @contextmanager
    def decision_span(
        self, operation: str, module: str = "", attributes: dict[str, Any] | None = None
    ) -> Iterator[Any]:
        start = time.time()
        span = None
        if self._otel_ready and self._tracer:
            span = self._tracer.start_span(operation)
            if attributes:
                span.set_attributes(attributes)
        try:
            yield span
        finally:
            if span:
                duration_ms = (time.time() - start) * 1000
                span.set_attribute("governance.duration_ms", duration_ms)
                span.set_attribute("governance.module", module)
                span.end()

    def record_policy_decision(
        self,
        module: str,
        operation: str,
        verdict: DecisionVerdict,
        policy_name: str = "",
        policy_category: PolicyCategory = PolicyCategory.SECURITY,
        agent_id: str = "",
        risk_score: float = 0.0,
        confidence: float = 1.0,
        reason: str = "",
        context: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> GTSEvent:
        event = GTSEvent(
            module=module,
            operation=operation,
            verdict=verdict,
            policy_category=policy_category,
            policy_name=policy_name,
            agent_id=agent_id,
            duration_ms=duration_ms,
            risk_score=risk_score,
            confidence=confidence,
            reason=reason,
            context=context or {},
        )
        if self.enable_file_fallback:
            self._write_log(event)
        return event

    def record_policy_violation(
        self, module: str, operation: str, policy_name: str = "",
        severity: str = "high", details: str = ""
    ) -> GTSEvent:
        return self.record_policy_decision(
            module=module, operation=operation,
            verdict=DecisionVerdict.DENY, policy_name=policy_name,
            risk_score=0.9,
            reason=f"Policy violation [{severity}]: {details}",
        )

    def record_policy_allow(
        self, module: str, operation: str, policy_name: str = "", reason: str = ""
    ) -> GTSEvent:
        return self.record_policy_decision(
            module=module, operation=operation,
            verdict=DecisionVerdict.ALLOW, policy_name=policy_name, reason=reason,
        )

    def get_stats(self) -> dict[str, Any]:
        return {
            "service": self.service_name,
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "otel_ready": self._otel_ready,
            "file_fallback": self.enable_file_fallback,
        }

    def _write_log(self, event: GTSEvent):
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(event.to_log_format() + '\n')
        except Exception:
            pass

    def shutdown(self):
        if self._otel_ready:
            try:
                trace.get_tracer_provider().shutdown()  # type: ignore
            except Exception:
                pass


# ── Global Instance ────────────────────────────────────────────────────────────

_global_telemetry: GovernanceTelemetry | None = None


def get_telemetry(
    service_name: str = "agent-governance",
    otlp_endpoint: str = "",
    reset: bool = False,
) -> GovernanceTelemetry:
    global _global_telemetry
    if _global_telemetry is None or reset:
        _global_telemetry = GovernanceTelemetry(
            service_name=service_name,
            otlp_endpoint=otlp_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", ""),
            log_file=os.environ.get("GOVERNANCE_TELEMETRY_LOG", "governance_telemetry.log"),
        )
    return _global_telemetry


def shutdown_telemetry():
    global _global_telemetry
    if _global_telemetry:
        _global_telemetry.shutdown()
        _global_telemetry = None
