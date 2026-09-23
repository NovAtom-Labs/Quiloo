"""Compatibility entrypoint for the repository CLI."""

from tcad_agent.cli import app

__all__ = ["app"]


if __name__ == "__main__":
    app()

