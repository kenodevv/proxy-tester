#!/usr/bin/env python3
import sys
import os
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from proxy_parser import parse_proxy_file, parse_selection, Proxy
from tester import test_proxies_parallel, test_proxies_multi_url_parallel, TestResult, MultiURLTestResult
from display import (
    console,
    print_header,
    print_proxy_list,
    print_results_table,
    print_summary,
    print_error,
    print_info,
    print_warning,
    prompt,
    create_progress,
    print_url_list,
    print_multi_url_results,
    print_multi_url_summary
)


DEFAULT_PROXY_FILE = "proxies.txt"
DEFAULT_URL = "https://httpbin.org/ip"
MAX_WORKERS = 10


def get_proxy_file_path() -> str:
    default_path = os.path.join(os.path.dirname(__file__), DEFAULT_PROXY_FILE)

    if os.path.exists(default_path):
        filepath = prompt("Proxy file", DEFAULT_PROXY_FILE)
    else:
        filepath = prompt("Proxy file (path to .txt)")

    if not os.path.isabs(filepath):
        filepath = os.path.join(os.path.dirname(__file__), filepath)

    return filepath


def get_target_urls() -> List[str]:
    console.print("\n[bold]Target URL(s)[/bold]")
    console.print("[dim]Separate multiple URLs with commas[/dim]")

    raw_input = prompt("URLs", DEFAULT_URL)

    urls = []
    for url in raw_input.split(','):
        url = url.strip()
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            urls.append(url)

    return urls if urls else [DEFAULT_URL]


def get_proxy_selection(total: int) -> List[int]:
    console.print(f"\n[bold]Select proxies to test[/bold]")
    console.print("[dim]Enter numbers (1,2,3), ranges (1-5), or 'all'[/dim]")

    while True:
        selection = prompt("Selection", "all")
        indices = parse_selection(selection, total)

        if indices:
            return indices
        else:
            print_warning("Invalid selection. Please try again.")


def main():
    try:
        print_header()

        try:
            filepath = get_proxy_file_path()
            proxies = parse_proxy_file(filepath)
        except FileNotFoundError as e:
            print_error(str(e))
            print_info(f"Create a file with proxies (one per line) and try again.")
            print_info("Supported formats:")
            print_info("  - ip:port")
            print_info("  - ip:port:user:pass")
            print_info("  - user:pass@ip:port")
            print_info("  - http://user:pass@ip:port")
            print_info("  - socks5://user:pass@ip:port")
            sys.exit(1)

        if not proxies:
            print_error("No valid proxies found in file.")
            sys.exit(1)

        print_proxy_list(proxies)

        selected_indices = get_proxy_selection(len(proxies))
        selected_proxies = [proxies[i] for i in selected_indices]

        print_info(f"\nSelected {len(selected_proxies)} proxies for testing.\n")

        urls = get_target_urls()
        console.print()

        if len(urls) > 1:
            print_url_list(urls)

        if len(urls) == 1:
            print_info(f"Testing {len(selected_proxies)} proxies against {urls[0]}...")
            console.print()

            results: List[TestResult] = []

            with create_progress() as progress:
                task = progress.add_task(
                    "[cyan]Testing proxies...",
                    total=len(selected_proxies)
                )

                def on_progress(completed: int, total: int, result: TestResult):
                    progress.update(task, completed=completed)

                results = test_proxies_parallel(
                    selected_proxies,
                    urls[0],
                    max_workers=MAX_WORKERS,
                    include_ping=True,
                    include_ip_check=True,
                    progress_callback=on_progress
                )

            print_results_table(results)
            print_summary(results)
        else:
            print_info(f"Testing {len(selected_proxies)} proxies against {len(urls)} URLs...")
            console.print()

            multi_results: List[MultiURLTestResult] = []

            with create_progress() as progress:
                task = progress.add_task(
                    "[cyan]Testing proxies...",
                    total=len(selected_proxies)
                )

                def on_multi_progress(completed: int, total: int, result: MultiURLTestResult):
                    progress.update(task, completed=completed)

                multi_results = test_proxies_multi_url_parallel(
                    selected_proxies,
                    urls,
                    max_workers=MAX_WORKERS,
                    include_ping=True,
                    include_ip_check=True,
                    progress_callback=on_multi_progress
                )

            print_multi_url_results(multi_results, urls)
            print_multi_url_summary(multi_results, urls)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
