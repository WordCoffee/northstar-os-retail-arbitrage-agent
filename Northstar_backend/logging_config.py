"""Structured logging configuration for Northstar OS.

Provides JSON-formatted structured logs for all API requests,
provider calls, and background tasks. Supports both development
(human-readable) and production (JSON) formats.

Usage:
    from logging_config import setup_logging, get_logger
    setup_logging()
    logger = get_logger("sourcescout")
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data

        # Add exception info
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_entry, default=str)


class DevFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",    # cyan
        "INFO": "\033[32m",     # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now().strftime("%H:%M:%S")
        return f"{color}{ts} [{record.levelname:8s}] {record.name}: {record.getMessage()}{self.RESET}"


def setup_logging(level: str = None):
    """Configure logging for the application."""
    env_level = level or os.environ.get("LOG_LEVEL", "INFO")
    log_format = os.environ.get("LOG_FORMAT", "dev")  # "dev" or "json"

    root = logging.getLogger()
    root.setLevel(getattr(logging, env_level.upper(), logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(DevFormatter())

    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(f"northstar.{name}")


def log_provider_call(logger: logging.Logger, provider: str, method: str,
                       status: str, latency_ms: int = None, **kwargs):
    """Log a provider API call with structured data."""
    extra = {
        "event": "provider_call",
        "provider": provider,
        "method": method,
        "status": status,
        "latency_ms": latency_ms,
        **kwargs,
    }
    logger.info(f"{provider}.{method} -> {status}", extra={"extra_data": extra})


def log_api_request(logger: logging.Logger, method: str, path: str,
                     status_code: int, latency_ms: int = None, user_id: str = None):
    """Log an API request with structured data."""
    extra = {
        "event": "api_request",
        "method": method,
        "path": path,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "user_id": user_id,
    }
    logger.info(f"{method} {path} -> {status_code}", extra={"extra_data": extra})
