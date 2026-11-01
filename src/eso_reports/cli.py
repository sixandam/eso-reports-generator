"""
Application entrypoint for the ESO Suite Fire Incidents Report Generator.
Directly launches the graphical user interface.
"""

from __future__ import annotations

import click
from .gui import launch_gui


@click.command(name="eso-reports")
def main() -> None:
    """Launch the ESO Report Generator GUI."""
    launch_gui()


if __name__ == "__main__":
    main()
