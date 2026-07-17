"""Command-line interface for LogSight-AI."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

from logsight.analyzer import AnomalyReport, detect_anomalies, error_rate_spike
from logsight.parser import parse_file, parse_lines

console = Console()


def _print_report(report: AnomalyReport, show_anomalies: bool) -> None:
    stats = report.stats
    console.print("\n[bold]LogSight-AI Analysis[/bold]")
    console.print(f"  Total entries : [cyan]{stats.total}[/cyan]")
    console.print(f"  Errors        : [red]{stats.error_count}[/red]")
    console.print(f"  Warnings      : [yellow]{stats.warning_count}[/yellow]")
    console.print(
        f"  Error rate    : [{'red' if stats.error_rate >= 0.10 else 'green'}]{stats.error_rate:.1%}[/]"
    )

    if stats.top_messages:
        table = Table(title="Top Messages", show_header=True, header_style="bold magenta")
        table.add_column("Count", justify="right", style="cyan", no_wrap=True)
        table.add_column("Message")
        for msg, cnt in stats.top_messages:
            table.add_row(str(cnt), msg)
        console.print(table)

    if show_anomalies and report.has_anomalies:
        console.print(f"\n[bold red]Anomalies detected: {len(report.anomalies)}[/bold red]")
        for entry in report.anomalies[:20]:
            level_style = "red" if entry.is_error else "yellow"
            console.print(
                f"  [[{level_style}]{entry.level.value}[/{level_style}]] {entry.message[:200]}"
            )
        if len(report.anomalies) > 20:
            console.print(f"  â€¦ and {len(report.anomalies) - 20} more.")
    elif show_anomalies:
        console.print("\n[bold green]No anomalies detected.[/bold green]")


@click.group()
@click.version_option()
def main() -> None:
    """LogSight-AI: AI-powered log analysis and anomaly detection."""


@main.command("analyze")
@click.argument("logfile", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--threshold",
    "-t",
    default=2.5,
    type=click.FloatRange(min=0),
    show_default=True,
    help="Z-score threshold for anomaly detection.",
)
@click.option(
    "--no-anomalies",
    is_flag=True,
    default=False,
    help="Skip printing individual anomalous entries.",
)
@click.option(
    "--window",
    "-w",
    default=100,
    type=click.IntRange(min=1),
    show_default=True,
    help="Window size for error-rate spike detection.",
)
@click.option(
    "--spike-threshold",
    "-s",
    default=0.25,
    type=click.FloatRange(min=0, max=1),
    show_default=True,
    help="Error-rate fraction that constitutes a spike.",
)
def analyze_cmd(
    logfile: str,
    threshold: float,
    no_anomalies: bool,
    window: int,
    spike_threshold: float,
) -> None:
    """Analyze LOGFILE and report anomalies."""
    try:
        entries = list(parse_file(logfile))
    except OSError as exc:
        console.print(f"[red]Error reading file:[/red] {exc}", err=True)
        sys.exit(1)

    if not entries:
        console.print("[yellow]No log entries found.[/yellow]")
        return

    report = detect_anomalies(entries, zscore_threshold=threshold)
    _print_report(report, show_anomalies=not no_anomalies)

    spikes = error_rate_spike(entries, window_size=window, spike_threshold=spike_threshold)
    if spikes:
        console.print(
            f"\n[bold red]Error-rate spikes at windows starting at lines: "
            f"{', '.join(str(s) for s in spikes)}[/bold red]"
        )


@main.command("stdin")
@click.option(
    "--threshold",
    "-t",
    default=2.5,
    type=click.FloatRange(min=0),
    show_default=True,
    help="Z-score threshold for anomaly detection.",
)
def stdin_cmd(threshold: float) -> None:
    """Read log lines from stdin and report anomalies."""
    lines = sys.stdin.readlines()
    entries = parse_lines(lines)
    if not entries:
        console.print("[yellow]No log entries found.[/yellow]")
        return
    report = detect_anomalies(entries, zscore_threshold=threshold)
    _print_report(report, show_anomalies=True)


@main.command("health")
def health_cmd() -> None:
    """Verify that LogSight-AI is installed and operational."""
    from logsight.analyzer import detect_anomalies
    from logsight.parser import parse_line

    sample = parse_line("INFO health check")
    report = detect_anomalies([sample])
    console.print("[bold green]âœ“ LogSight-AI is healthy.[/bold green]")
    console.print(f"  version : [cyan]{_version()}[/cyan]")
    console.print(f"  parsed  : [cyan]{sample.level.value}[/cyan] â€” {sample.message}")
    console.print(f"  anomaly : [cyan]{report.has_anomalies}[/cyan]")


def _version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("logsight-ai")
    except PackageNotFoundError:
        from logsight import __version__

        return __version__


if __name__ == "__main__":
    main()
