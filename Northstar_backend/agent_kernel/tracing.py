"""Optional OpenTelemetry spans for agent work.

Off by default (`NORTHSTAR_TRACE=1` enables it). When enabled, spans go to an
OTLP HTTP endpoint if `OTEL_EXPORTER_OTLP_ENDPOINT` is set, otherwise to the
console. The no-op path imports nothing from the SDK, so the service starts even
when the optional packages are absent.

    from agent_kernel.tracing import span
    with span("tys.kernel", task_id=task_id):
        ...
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

_ENABLED = os.environ.get("NORTHSTAR_TRACE", "0").strip() == "1"
_INITIALISED = False


def _init() -> None:
    global _INITIALISED
    if _INITIALISED:
        return
    _INITIALISED = True
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except Exception:  # noqa: BLE001 - tracing must never break the service
        return
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            return
        except Exception:  # noqa: BLE001 - fall through to console
            pass
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """A span when tracing is on; a no-op context manager when it is off."""
    if not _ENABLED:
        yield None
        return
    _init()
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer("northstar.agent")
        with tracer.start_as_current_span(name) as current:
            for key, value in attributes.items():
                if value is not None:
                    current.set_attribute(str(key), str(value)[:500])
            yield current
    except Exception:  # noqa: BLE001 - never fail the work because a span failed
        yield None
