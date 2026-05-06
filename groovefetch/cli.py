"""Command-line interface for GrooveFetch."""

import asyncio
import json
import sys
from typing import Any, Callable, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .core import GrooveFetch
from .utils import validate_url

console = Console()


def coro(f: Callable) -> Callable:
    """Decorator to run async functions in Click."""
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@click.group()
@click.version_option(version="0.1.0", prog_name="groovefetch")
def main() -> None:
    """🌐 GrooveFetch — AI-native adaptive web scraper"""
    pass


@main.command()
@click.argument("url")
@click.option("--mode", "-m", default="auto", type=click.Choice(["auto", "http", "stealth"]))
@click.option("--output", "-o", default=None, help="Output JSON file")
@click.option("--selector", "-s", default="", help="Container CSS selector")
@coro
async def scrape(url: str, mode: str, output: Optional[str], selector: str):
    """Scrape a URL and output structured data."""
    url = validate_url(url)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Scraping {url}...", total=None)
        
        async with GrooveFetch() as gf:
            result = await gf.scrape(url, mode=mode, container_selector=selector)
        
        progress.update(task, completed=True)
    
    # Display results
    table = Table(title=f"Scrape Results: {url}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Status", "✅ Success" if result.is_valid else "⚠️ Partial")
    table.add_row("Mode", result.metadata.get("mode", "unknown"))
    table.add_row("Items Found", str(len(result.raw_data)))
    table.add_row("Validated", str(len(result.validated)))
    table.add_row("Errors", str(len(result.errors)))
    table.add_row("Duration", f"{result.metadata.get('duration', 0):.2f}s")
    
    console.print(table)
    
    if result.validated:
        console.print("\n[bold]Validated Data:[/bold]")
        for item in result.validated[:5]:
            console.print(f"  • {item.model_dump()}")
    
    if output:
        with open(output, "w") as f:
            json.dump(result.to_dict(), f, indent=2, default=str)
        console.print(f"\n[green]✓[/green] Saved to {output}")


@main.command()
@click.argument("url")
@coro
async def snapshot(url: str):
    """Get token-efficient accessibility snapshot."""
    url = validate_url(url)
    
    async with GrooveFetch() as gf:
        result = await gf.snapshot(url)
    
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        sys.exit(1)
    
    console.print(Panel(
        f"[bold]{result['title']}[/bold]\n\n"
        f"[dim]URL:[/dim] {result['url']}\n"
        f"[dim]Estimated tokens:[/dim] {result['token_estimate']}\n"
        f"[dim]Elements:[/dim] {len(result['elements'])}\n\n"
        f"{result['text'][:2000]}...",
        title="Accessibility Snapshot",
        border_style="blue",
    ))


@main.command()
@click.argument("url")
@click.option("--max-pages", "-n", default=10, help="Maximum pages to crawl")
@click.option("--same-domain", is_flag=True, default=True, help="Stay on same domain")
@coro
async def crawl(url: str, max_pages: int, same_domain: bool):
    """Crawl starting from a URL."""
    url = validate_url(url)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Crawling...", total=None)
        
        async with GrooveFetch() as gf:
            results = await gf.crawl(url, max_pages=max_pages, same_domain=same_domain)
        
        progress.update(task, completed=True)
    
    table = Table(title=f"Crawl Results: {url}")
    table.add_column("#", style="cyan")
    table.add_column("URL", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Mode", style="blue")
    
    for idx, result in enumerate(results, 1):
        status = "✅" if result.status < 400 else "❌"
        table.add_row(str(idx), result.url[:60], f"{status} {result.status}", result.mode)
    
    console.print(table)
    console.print(f"\n[green]✓[/green] Fetched {len(results)} pages")


@main.command()
@click.argument("domain")
def stats(domain: str) -> None:
    """Show learned stats for a domain."""
    from .adaptive import AdaptiveLearner
    
    learner = AdaptiveLearner()
    profile = learner.get_profile(domain)
    
    if profile.request_count == 0:
        console.print(f"[yellow]No data yet for {domain}[/yellow]")
        return
    
    table = Table(title=f"Learning Stats: {domain}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Requests", str(profile.request_count))
    table.add_row("Success Rate", f"{profile.success_rate:.1%}")
    table.add_row("Optimal Delay", f"{profile.optimal_delay:.1f}s")
    table.add_row("Stealth Required", "Yes" if profile.stealth_required > 0.5 else "No")
    table.add_row("Failures", str(profile.failure_count))
    
    console.print(table)


if __name__ == "__main__":
    main()
