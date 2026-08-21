import json
import logging
import re
import sys
from typing import Any, Dict

# Secret and PII patterns for redaction
SECRET_PATTERNS = [
    re.compile(r"(?i)(bearer\s+[a-zA-Z0-9_\-\.]{15,})"),
    re.compile(r"(?i)(api[_-]?key[\"']?\s*[:=]\s*[\"']?)([a-zA-Z0-9_\-]{15,})"),
    re.compile(r"(?i)(password[\"']?\s*[:=]\s*[\"']?)([^\"'\s]{4,})"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # Email
    re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b"),  # Credit card
]


def redact_sensitive_data(text: str) -> str:
    if not isinstance(text, str):
        return text
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


class ReadableConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        message = redact_sensitive_data(record.getMessage())
        formatted = f"[{timestamp}] [{record.levelname:<5}] [{record.name}] {message}"
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        return formatted


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_data(record.getMessage()),
        }

        for key, val in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                if isinstance(val, str):
                    log_obj[key] = redact_sensitive_data(val)
                else:
                    log_obj[key] = val

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str, ensure_ascii=False)


def setup_logging(log_level: str = "INFO", use_json: bool = False):
    handler = logging.StreamHandler(sys.stdout)
    if use_json:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(ReadableConsoleFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]
