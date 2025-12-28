"""Centralized logging configuration with AWS CloudWatch support.

This module provides:
- JSONFormatter for structured logging (CloudWatch Insights compatible)
- CloudWatch handler via watchtower (auto-enabled when AWS creds available)
- Fallback to stderr-only when AWS credentials are missing
"""

import json
import logging
import os
import re
import socket
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Extracts [TAG] from log messages and creates structured JSON output
    compatible with CloudWatch Insights queries.
    """

    def __init__(self, robot_name: str = None):
        super().__init__()
        self.robot_name = robot_name or "unknown"

    def format(self, record: logging.LogRecord) -> str:
        # Extract tag from message if present: [TAG] message
        tag = None
        message = record.getMessage()
        tag_match = re.match(r'\[([A-Z_]+)\]\s*(.*)', message)
        if tag_match:
            tag = tag_match.group(1)
            message = tag_match.group(2)

        # Build structured log entry
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "tag": tag,
            "message": message,
            "robot_name": self.robot_name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add any extra fields
        if hasattr(record, 'extra'):
            log_entry["extra"] = record.extra

        return json.dumps(log_entry, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    """Plain text formatter for stderr output (local debugging)."""

    def __init__(self):
        super().__init__(
            fmt='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logging(robot_name: str = None) -> logging.Logger:
    """Configure logging with optional CloudWatch integration.

    Args:
        robot_name: Robot/device name for log group naming.
                   Falls back to 'unknown' if not provided.

    Returns:
        Configured root logger.

    Behavior:
        - Always adds stderr handler for local debugging
        - Adds CloudWatch handler if AWS credentials are available
        - Graceful fallback if CloudWatch setup fails
    """
    robot_name = robot_name or os.getenv("ROBOT_NAME", "unknown")

    # Get root logger and clear existing handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    # Always add stderr handler (plain text for readability)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)
    stderr_handler.setFormatter(PlainFormatter())
    root_logger.addHandler(stderr_handler)

    # Try to add CloudWatch handler if AWS credentials available
    cloudwatch_enabled = _setup_cloudwatch_handler(root_logger, robot_name)

    # Log startup info
    logger = logging.getLogger(__name__)
    if cloudwatch_enabled:
        logger.info(f"[STARTUP] CloudWatch logging enabled: /mcp/{robot_name}")
    else:
        logger.info("[STARTUP] CloudWatch logging disabled (no AWS credentials)")

    return root_logger


def _setup_cloudwatch_handler(logger: logging.Logger, robot_name: str) -> bool:
    """Attempt to set up CloudWatch handler.

    Returns:
        True if CloudWatch handler was successfully added, False otherwise.
    """
    # Check for AWS credentials
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))

    if not all([aws_access_key, aws_secret_key, aws_region]):
        return False

    try:
        from watchtower import CloudWatchLogHandler
        import boto3

        # Create boto3 client with explicit credentials
        logs_client = boto3.client(
            'logs',
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )

        # Generate log stream name: date-hostname
        hostname = socket.gethostname()
        log_stream = f"{datetime.now().strftime('%Y-%m-%d')}-{hostname}"

        # Create CloudWatch handler
        cloudwatch_handler = CloudWatchLogHandler(
            log_group_name=f"/mcp/{robot_name}",
            log_stream_name=log_stream,
            boto3_client=logs_client,
            use_queues=True,  # Async sending for performance
            create_log_group=True,
            create_log_stream=True,
        )
        cloudwatch_handler.setLevel(logging.INFO)
        cloudwatch_handler.setFormatter(JSONFormatter(robot_name))

        logger.addHandler(cloudwatch_handler)
        return True

    except ImportError:
        # watchtower not installed
        logging.getLogger(__name__).warning(
            "[STARTUP] watchtower not installed, CloudWatch logging unavailable"
        )
        return False
    except Exception as e:
        # Any AWS/CloudWatch error - log and continue without CloudWatch
        logging.getLogger(__name__).warning(
            f"[STARTUP] CloudWatch setup failed: {e}"
        )
        return False
