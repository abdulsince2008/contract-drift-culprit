#!/usr/bin/env python3
import click
import yaml
import sys
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON

from drift_finder import DriftCulpritFinder
from slack_notifier import SlackNotifier


console = Console()


@click.command()
@click.argument("old_spec", type=click.Path(exists=True, readable=True))
@click.argument("new_spec", type=click.Path(exists=True, readable=True))
@click.option("--repo-path", "-r", default=".", type=click.Path(exists=True, file_okay=False),
              help="Path to git repository (default: current directory)")
@click.option("--config", "-c", type=click.Path(exists=True, readable=True),
              help="Path to config YAML file")
@click.option("--route-patterns", "-p", multiple=True,
              help="Glob patterns for route handler files (can specify multiple)")
@click.option("--slack/--no-slack", default=False, help="Send report to Slack")
@click.option("--slack-token", envvar="SLACK_BOT_TOKEN", help="Slack bot token")
@click.option("--slack-channel", envvar="SLACK_CHANNEL", help="Slack channel ID")
@click.option("--repo-url", help="Repository URL for Slack report")
@click.option("--output", "-o", type=click.Path(writable=True), help="Output JSON file")
@click.option("--oasdiff-path", default="oasdiff", help="Path to oasdiff binary")
def main(old_spec, new_spec, repo_path, config, route_patterns, slack, 
         slack_token, slack_channel, repo_url, output, oasdiff_path):
    """
    Contract-Drift Culprit Finder
    
    Finds breaking API changes between two OpenAPI specs and uses git blame
    to identify the commits that likely introduced each change.
    
    Example:
        drift-culprit old.yaml new.yaml --repo-path /path/to/repo --slack
    """
    route_patterns_list = list(route_patterns)
    
    if config:
        with open(config) as f:
            cfg = yaml.safe_load(f)
            if cfg.get("route_patterns"):
                route_patterns_list.extend(cfg["route_patterns"])
            if cfg.get("repo_path") and repo_path == ".":
                repo_path = cfg["repo_path"]
            if cfg.get("oasdiff_path"):
                oasdiff_path = cfg["oasdiff_path"]
    
    if not route_patterns_list:
        route_patterns_list = None
    
    console.print(Panel.fit(
        f"[bold]Contract-Drift Culprit Finder[/bold]\n"
        f"Old spec: {old_spec}\n"
        f"New spec: {new_spec}\n"
        f"Repo: {repo_path}",
        title="🔍 Analyzing"
    ))
    
    try:
        finder = DriftCulpritFinder(repo_path=repo_path, oasdiff_path=oasdiff_path)
        report = finder.analyze(old_spec, new_spec, route_patterns_list)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    
    _print_report(console, report)
    
    if output:
        import json
        with open(output, "w") as f:
            json.dump(report, f, indent=2)
        console.print(f"\n[green]Report saved to {output}[/green]")
    
    if slack:
        notifier = SlackNotifier(token=slack_token, channel=slack_channel)
        if notifier.send_drift_report(report, repo_url):
            console.print("[green]Slack notification sent[/green]")
        else:
            console.print("[yellow]Slack notification failed (check token/channel)[/yellow]")
    
    if report["total_breaking_changes"] > 0:
        sys.exit(1)
    else:
        console.print("\n[green]No breaking changes detected[/green]")
        sys.exit(0)


def _print_report(console: Console, report: Dict[str, Any]):
    console.print(f"\n[bold]Total Breaking Changes:[/bold] {report['total_breaking_changes']}\n")
    
    for idx, result in enumerate(report["results"], 1):
        change = result["breaking_change"]
        culprits = result["culprit_commits"]
        
        table = Table(title=f"Change #{idx}: {change['method']} {change['path']}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Type", change["change_type"])
        table.add_row("Description", change["description"])
        
        console.print(table)
        
        if culprits:
            culprit_table = Table(title="Suspect Commits")
            culprit_table.add_column("Commit", style="yellow")
            culprit_table.add_column("Author", style="green")
            culprit_table.add_column("Date", style="blue")
            culprit_table.add_column("Message", style="white")
            culprit_table.add_column("Files", style="magenta")
            
            for c in culprits[:5]:
                culprit_table.add_row(
                    c["commit_hash"],
                    c["author"],
                    c["date"],
                    c["message"][:60] + ("..." if len(c["message"]) > 60 else ""),
                    ", ".join(c["files_changed"][:3])
                )
            
            console.print(culprit_table)
        else:
            console.print("[yellow]No matching commits found in route handlers[/yellow]")
        
        console.print()


if __name__ == "__main__":
    main()