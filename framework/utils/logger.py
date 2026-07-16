"""Structured logging configuration for framework.

Provides JSON formatted logs for production/monitoring and colorized, 
human-readable logs for local development.
"""

import logging
import sys
from typing import Any, Dict
import structlog


def configure_logging(level: int = logging.INFO, json_format: bool = False) -> None:
    """Configures the global structlog logging.

    Args:
        level: The logging level (e.g. logging.INFO).
        json_format: If True, output raw JSON logs (great for production ELK/Grafana stacks).
                     If False, output pretty-printed developer logs.
    """
    shared_processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to redirect to structlog
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer() if json_format else structlog.dev.ConsoleRenderer(colors=True)
    ))

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Returns a structured logger with the given name.

    Args:
        name: The name of the logger (usually __name__).
    """
    return structlog.get_logger(name)


# Default configuration on import
configure_logging(level=logging.INFO, json_format=False)
