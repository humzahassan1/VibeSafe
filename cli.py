"""CLI entry point — argument parsing only, no logic."""

from __future__ import annotations

import json
import logging
import os
import sys

import click

from orchestrator import ScanOptions, run, run_github


@click.group()
@click.version_option(version="0.1.0", prog_name="vibesafe")
def cli() -> None:
    """VibeSafe — Security agent for vibecoded projects."""
    pass


def _apply_verbose(verbose: bool) -> None:
    """Enable debug logging when requested."""
    if verbose:
        os.environ["VIBESAFE_LOG_LEVEL"] = "DEBUG"
        logging.getLogger("vibesafe").setLevel(logging.DEBUG)


def _emit_report(report: str, output: str | None) -> None:
    """Write a report to a file or stdout."""
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(report)
        click.echo(f"Report written to {output}", err=True)
    else:
        click.echo(report)


def _exit_on_critical(report: str, fmt: str) -> None:
    """Exit with code 1 when critical findings are present."""
    if fmt == "json":
        try:
            data = json.loads(report)
            if data.get("summary", {}).get("critical", 0) > 0:
                sys.exit(1)
        except json.JSONDecodeError:
            pass
    else:
        if "## Critical Findings" in report:
            sys.exit(1)


def _scan_options(fmt: str, skip_tier3: bool, budget: int) -> ScanOptions:
    """Build ScanOptions from common CLI flags."""
    return ScanOptions(
        output_format=fmt,
        skip_tier3=skip_tier3,
        token_budget=budget,
    )


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
    _apply_verbose(verbose)
    options = _scan_options(fmt, skip_tier3, budget)
    report = run(path, options)
    _emit_report(report, output)
    _exit_on_critical(report, fmt)


@cli.command("scan-github")
@click.argument("repo")
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
@click.option("--ref", default=None,
              help="Branch, tag, or commit SHA (overrides ref in the repo URL).")
@click.option("--token", default=None,
              help="GitHub token for private repos (falls back to GITHUB_TOKEN).")
def scan_github_cmd(
    repo: str,
    output: str | None,
    fmt: str,
    verbose: bool,
    skip_tier3: bool,
    budget: int,
    ref: str | None,
    token: str | None,
) -> None:
    """Scan a GitHub repository for security vulnerabilities."""
    _apply_verbose(verbose)
    options = _scan_options(fmt, skip_tier3, budget)
    if token is None:
        token = os.environ.get("GITHUB_TOKEN")
    report = run_github(repo, options, token=token, ref=ref)
    _emit_report(report, output)
    _exit_on_critical(report, fmt)


def main() -> None:
    """Entry point for the vibesafe command."""
    cli()


if __name__ == "__main__":
    main()
