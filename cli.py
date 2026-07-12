"""CLI entry point — argument parsing only, no logic."""

from __future__ import annotations

import sys

import click

from models.finding import Severity
from orchestrator import ScanOptions, run


@click.group()
@click.version_option(version="0.1.0", prog_name="vibesafe")
def cli() -> None:
    """VibeSafe — Security agent for vibecoded projects."""
    pass


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), default=None,
              help="Write report to file instead of stdout.")
@click.option("-f", "--format", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Output format (default: markdown).")
@click.option("-v", "--verbose", is_flag=True, default=False,
              help="Enable debug logging.")
@click.option("--skip-tier3", is_flag=True, default=False,
              help="Skip LLM analysis (Tier 1/2 only, no API key needed).")
@click.option("--budget", type=int, default=100_000,
              help="Max token budget for Tier 3 analysis (default: 100000).")
def scan(path: str, output: str | None, fmt: str, verbose: bool,
         skip_tier3: bool, budget: int) -> None:
    """Scan a project for security vulnerabilities."""
    import logging
    import os

    if verbose:
        os.environ["VIBESAFE_LOG_LEVEL"] = "DEBUG"
        logging.getLogger("vibesafe").setLevel(logging.DEBUG)

    options = ScanOptions(
        output_format=fmt,
        skip_tier3=skip_tier3,
        token_budget=budget,
    )

    report = run(path, options)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(report)
        click.echo(f"Report written to {output}", err=True)
    else:
        click.echo(report)

    if fmt == "json":
        import json
        try:
            data = json.loads(report)
            if data.get("summary", {}).get("critical", 0) > 0:
                sys.exit(1)
        except json.JSONDecodeError:
            pass
    else:
        if "## Critical Findings" in report:
            sys.exit(1)


def main() -> None:
    """Entry point for the vibesafe command."""
    cli()


if __name__ == "__main__":
    main()
