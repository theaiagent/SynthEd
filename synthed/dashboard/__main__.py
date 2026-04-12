"""Entry point: python -m synthed.dashboard."""

from shiny import run_app

from .app import app

if __name__ == "__main__":
    run_app(app, host="127.0.0.1", port=8080, launch_browser=True)
