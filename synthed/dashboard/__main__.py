"""Entry point: python -m synthed.dashboard."""

import os

from shiny import run_app

from .app import app

_PORT_MIN = 1024
_PORT_MAX = 65535


def _validate_port(raw: str) -> int:
    """Parse and validate port number from environment variable."""
    try:
        port = int(raw)
    except ValueError:
        raise ValueError(
            f"SYNTHED_DASHBOARD_PORT must be an integer, got: {raw!r}"
        )
    if not (_PORT_MIN <= port <= _PORT_MAX):
        raise ValueError(
            f"SYNTHED_DASHBOARD_PORT must be between {_PORT_MIN} and {_PORT_MAX}, got {port}"
        )
    return port


if __name__ == "__main__":
    host = os.getenv("SYNTHED_DASHBOARD_HOST", "127.0.0.1")
    port = _validate_port(os.getenv("SYNTHED_DASHBOARD_PORT", "8080"))
    launch_browser = os.getenv("SYNTHED_DASHBOARD_LAUNCH_BROWSER", "1") == "1"
    run_app(app, host=host, port=port, launch_browser=launch_browser)
