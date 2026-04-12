"""Entry point: python -m synthed.dashboard."""

import os

from shiny import run_app

from .app import app

if __name__ == "__main__":
    host = os.getenv("SYNTHED_DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("SYNTHED_DASHBOARD_PORT", "8080"))
    launch_browser = os.getenv("SYNTHED_DASHBOARD_LAUNCH_BROWSER", "1") == "1"
    run_app(app, host=host, port=port, launch_browser=launch_browser)
