from typing import Optional, List

from urllib.parse import urlparse

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text
from rich import box

from proxy_parser import Proxy
from tester import TestResult, MultiURLTestResult, URLTestResult


console = Console()


def print_header():
    header = Text()
    header.append("ShiftProxies Proxy Tester", style="bold cyan")

    panel = Panel(
        header,
        box=box.ROUNDED,
        padding=(0, 2),
        title="[bold white]v1.0[/bold white]",
        title_align="right"
    )
    console.print(panel)
    console.print()


def print_proxy_list(proxies: List[Proxy]):
    console.print(f"\n[bold green]Found {len(proxies)} proxies:[/bold green]\n")

    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    table.add_column("#", style="dim", width=4)
    table.add_column("Proxy", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Auth", style="magenta")

    for i, proxy in enumerate(proxies, 1):
        auth = "[green]Yes[/green]" if proxy.username else "[dim]No[/dim]"
        table.add_row(
            str(i),
            f"{proxy.host}:{proxy.port}",
            proxy.proxy_type.value.upper(),
            auth
        )

    console.print(table)
    console.print()


def create_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TextColumn("[bold cyan]{task.completed}/{task.total}[/bold cyan]"),
        console=console
    )


def format_latency(ms: Optional[float]) -> str:
    if ms is None:
        return "[dim]-[/dim]"

    if ms < 500:
        color = "green"
    elif ms < 1500:
        color = "yellow"
    else:
        color = "red"

    return f"[{color}]{ms:.0f}ms[/{color}]"


def format_speed(kbps: Optional[float]) -> str:
    if kbps is None or kbps < 1:
        return "[dim]-[/dim]"

    if kbps >= 1024:
        mbps = kbps / 1024
        if mbps >= 1:
            color = "green"
        elif mbps >= 0.5:
            color = "yellow"
        else:
            color = "red"
        return f"[{color}]{mbps:.1f}MB/s[/{color}]"
    else:
        if kbps >= 500:
            color = "green"
        elif kbps >= 100:
            color = "yellow"
        else:
            color = "red"
        return f"[{color}]{kbps:.0f}KB/s[/{color}]"


def format_status(result: TestResult) -> str:
    if not result.success:
        error = result.http_error or "Error"
        return f"[red]ERR[/red]"

    status = result.http_status
    if status is None:
        return "[dim]-[/dim]"

    if 200 <= status < 300:
        return f"[green]{status}[/green]"
    elif 300 <= status < 400:
        return f"[yellow]{status}[/yellow]"
    else:
        return f"[red]{status}[/red]"


def format_ping(ms: Optional[float], error: Optional[str] = None) -> str:
    if ms is None:
        if error:
            return "[red]FAIL[/red]"
        return "[dim]-[/dim]"

    if ms < 50:
        color = "green"
    elif ms < 150:
        color = "yellow"
    else:
        color = "red"

    return f"[{color}]{ms:.0f}ms[/{color}]"


def format_blocked(result: TestResult) -> str:
    if not result.success:
        return "[dim]-[/dim]"

    if result.block_result is None:
        return "[dim]?[/dim]"

    if result.block_result.is_blocked:
        return f"[red]YES[/red]"
    else:
        return f"[green]No[/green]"


def format_ip(ip: Optional[str]) -> str:
    if ip is None:
        return "[dim]-[/dim]"
    if len(ip) > 15:
        return f"[cyan]{ip[:12]}...[/cyan]"
    return f"[cyan]{ip}[/cyan]"


def print_results_table(results: List[TestResult]):
    console.print()

    table = Table(
        show_header=True,
        header_style="bold white on blue",
        box=box.ROUNDED,
        title="[bold]Test Results[/bold]",
        title_style="bold cyan"
    )

    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Proxy", style="white", min_width=20)
    table.add_column("Status", justify="center", width=8)
    table.add_column("Latency", justify="right", width=10)
    table.add_column("Speed", justify="right", width=10)
    table.add_column("Ping", justify="right", width=8)
    table.add_column("Blocked", justify="center", width=8)
    table.add_column("IP", justify="left", width=16)

    for i, result in enumerate(results, 1):
        proxy_str = f"{result.proxy.host}:{result.proxy.port}"

        error_note = ""
        if not result.success and result.http_error:
            error_note = f"\n[dim red]{result.http_error}[/dim red]"

        table.add_row(
            str(i),
            proxy_str + error_note,
            format_status(result),
            format_latency(result.latency_ms),
            format_speed(result.download_speed_kbps),
            format_ping(result.ping_ms, result.ping_error),
            format_blocked(result),
            format_ip(result.detected_ip)
        )

    console.print(table)
    console.print()


def print_summary(results: List[TestResult]):
    total = len(results)
    working = sum(1 for r in results if r.is_working())
    failed = total - working

    working_results = [r for r in results if r.is_working()]

    avg_latency = None
    avg_speed = None
    avg_ping = None

    if working_results:
        latencies = [r.latency_ms for r in working_results if r.latency_ms]
        speeds = [r.download_speed_kbps for r in working_results if r.download_speed_kbps]
        pings = [r.ping_ms for r in working_results if r.ping_ms]

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
        if speeds:
            avg_speed = sum(speeds) / len(speeds)
        if pings:
            avg_ping = sum(pings) / len(pings)

    if working == total:
        status_color = "green"
    elif working > 0:
        status_color = "yellow"
    else:
        status_color = "red"

    percentage = (working / total * 100) if total > 0 else 0

    summary = Text()
    summary.append("Summary: ", style="bold")
    summary.append(f"{working}/{total}", style=f"bold {status_color}")
    summary.append(" proxies working ", style="white")
    summary.append(f"({percentage:.0f}%)", style=f"{status_color}")

    console.print(Panel(summary, box=box.ROUNDED))

    if working_results:
        avg_text = Text()
        avg_text.append("Averages: ", style="bold dim")

        if avg_latency:
            avg_text.append(f"Latency: {avg_latency:.0f}ms  ", style="cyan")
        if avg_speed:
            if avg_speed >= 1024:
                avg_text.append(f"Speed: {avg_speed/1024:.1f}MB/s  ", style="cyan")
            else:
                avg_text.append(f"Speed: {avg_speed:.0f}KB/s  ", style="cyan")
        if avg_ping:
            avg_text.append(f"Ping: {avg_ping:.0f}ms", style="cyan")

        console.print(avg_text)

    console.print()


def print_error(message: str):
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_info(message: str):
    console.print(f"[cyan]{message}[/cyan]")


def print_warning(message: str):
    console.print(f"[yellow]Warning:[/yellow] {message}")


def prompt(message: str, default: str = "") -> str:
    if default:
        return console.input(f"[bold]{message}[/bold] [[cyan]{default}[/cyan]]: ").strip() or default
    return console.input(f"[bold]{message}[/bold]: ").strip()


def get_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or url


def truncate_url(url: str, max_length: int = 50) -> str:
    if len(url) <= max_length:
        return url
    return url[:max_length - 3] + "..."


def print_url_list(urls: List[str]):
    console.print(f"\n[bold green]Testing against {len(urls)} URLs:[/bold green]\n")

    for i, url in enumerate(urls, 1):
        display_url = truncate_url(url, 60)
        console.print(f"  [cyan]{i}.[/cyan] {display_url}")

    console.print()


def format_url_status(result: URLTestResult) -> str:
    if not result.success:
        return "[red]ERR[/red]"
    if result.http_status is None:
        return "[dim]-[/dim]"
    if 200 <= result.http_status < 300:
        return f"[green]{result.http_status}[/green]"
    elif 300 <= result.http_status < 400:
        return f"[yellow]{result.http_status}[/yellow]"
    return f"[red]{result.http_status}[/red]"


def print_multi_url_results(results: List[MultiURLTestResult], urls: List[str]):
    console.print()

    table = Table(
        show_header=True,
        header_style="bold white on blue",
        box=box.ROUNDED,
        title="[bold]Multi-URL Test Results[/bold]",
        title_style="bold cyan"
    )

    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Proxy", style="white", min_width=20)
    table.add_column("Success", justify="center", width=10)
    table.add_column("Avg Latency", justify="right", width=12)
    table.add_column("Ping", justify="right", width=8)
    table.add_column("IP", justify="left", width=16)

    for url in urls:
        domain = get_domain(url)
        short_name = domain[:12] if len(domain) > 12 else domain
        table.add_column(short_name, justify="center", width=10)

    for i, result in enumerate(results, 1):
        proxy_str = f"{result.proxy.host}:{result.proxy.port}"
        success_str = f"{result.working_count()}/{result.total_count()}"

        ratio = result.working_count() / result.total_count() if result.total_count() > 0 else 0
        if ratio == 1.0:
            success_style = "green"
        elif ratio >= 0.5:
            success_style = "yellow"
        else:
            success_style = "red"

        row = [
            str(i),
            proxy_str,
            f"[{success_style}]{success_str}[/{success_style}]",
            format_latency(result.avg_latency()),
            format_ping(result.ping_ms, result.ping_error),
            format_ip(result.detected_ip),
        ]

        for url in urls:
            url_result = result.url_results.get(url)
            if url_result and url_result.is_working():
                row.append("[green]OK[/green]")
            elif url_result and url_result.success:
                row.append("[yellow]BLK[/yellow]")
            else:
                row.append("[red]FAIL[/red]")

        table.add_row(*row)

    console.print(table)
    console.print()


def print_multi_url_summary(results: List[MultiURLTestResult], urls: List[str]):
    total_proxies = len(results)
    fully_working = sum(1 for r in results if r.is_fully_working())
    partial_working = sum(1 for r in results if r.working_count() > 0 and not r.is_fully_working())
    failed = total_proxies - fully_working - partial_working

    summary = Text()
    summary.append("Summary:\n", style="bold")
    summary.append(f"  All URLs working:  ", style="white")
    summary.append(f"{fully_working}/{total_proxies}", style="bold green")
    summary.append(f"\n  Partial success:   ", style="white")
    summary.append(f"{partial_working}/{total_proxies}", style="bold yellow")
    summary.append(f"\n  All failed:        ", style="white")
    summary.append(f"{failed}/{total_proxies}", style="bold red")

    console.print(Panel(summary, box=box.ROUNDED))

    console.print("\n[bold]Per-URL Success Rates:[/bold]")

    for url in urls:
        working = sum(1 for r in results if r.url_results.get(url) and r.url_results[url].is_working())
        rate = (working / total_proxies * 100) if total_proxies > 0 else 0

        if rate >= 80:
            color = "green"
        elif rate >= 50:
            color = "yellow"
        else:
            color = "red"

        short_url = truncate_url(url, 45)
        console.print(f"  [{color}]{working}/{total_proxies}[/{color}] ({rate:.0f}%) {short_url}")

    console.print()
