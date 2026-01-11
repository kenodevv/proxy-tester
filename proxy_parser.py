import re
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class ProxyType(Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


@dataclass
class Proxy:
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    proxy_type: ProxyType = ProxyType.HTTP
    raw: str = ""

    def __str__(self) -> str:
        auth = f"{self.username}:***@" if self.username else ""
        return f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"

    def short_str(self) -> str:
        auth = " (auth)" if self.username else " (no auth)"
        return f"{self.host}:{self.port}{auth}"

    def get_request_proxies(self) -> dict:
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        else:
            auth = ""

        proxy_url = f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"

        if self.proxy_type == ProxyType.SOCKS5:
            return {
                "http": proxy_url,
                "https": proxy_url
            }
        else:
            return {
                "http": proxy_url,
                "https": proxy_url
            }


def parse_proxy(line: str) -> Optional[Proxy]:
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    proxy_type = ProxyType.HTTP

    url_match = re.match(
        r'^(https?|socks5)://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)$',
        line,
        re.IGNORECASE
    )
    if url_match:
        scheme, username, password, host, port = url_match.groups()
        if scheme.lower() == 'socks5':
            proxy_type = ProxyType.SOCKS5
        elif scheme.lower() == 'https':
            proxy_type = ProxyType.HTTPS
        return Proxy(
            host=host,
            port=int(port),
            username=username,
            password=password,
            proxy_type=proxy_type,
            raw=line
        )

    at_match = re.match(r'^([^:]+):([^@]+)@([^:]+):(\d+)$', line)
    if at_match:
        username, password, host, port = at_match.groups()
        return Proxy(
            host=host,
            port=int(port),
            username=username,
            password=password,
            proxy_type=proxy_type,
            raw=line
        )

    colon_auth_match = re.match(r'^([^:]+):(\d+):([^:]+):(.+)$', line)
    if colon_auth_match:
        host, port, username, password = colon_auth_match.groups()
        return Proxy(
            host=host,
            port=int(port),
            username=username,
            password=password,
            proxy_type=proxy_type,
            raw=line
        )

    simple_match = re.match(r'^([^:]+):(\d+)$', line)
    if simple_match:
        host, port = simple_match.groups()
        return Proxy(
            host=host,
            port=int(port),
            proxy_type=proxy_type,
            raw=line
        )

    return None


def parse_proxy_file(filepath: str) -> List[Proxy]:
    proxies = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                proxy = parse_proxy(line)
                if proxy:
                    proxies.append(proxy)
    except FileNotFoundError:
        raise FileNotFoundError(f"Proxy file not found: {filepath}")
    except Exception as e:
        raise Exception(f"Error reading proxy file: {e}")

    return proxies


def parse_selection(selection: str, total: int) -> List[int]:
    # Accepts: 'all', '1,2,3', '1-5', or '1,3-5,8'
    selection = selection.strip().lower()

    if selection == 'all':
        return list(range(total))

    indices = set()
    parts = selection.replace(' ', '').split(',')

    for part in parts:
        if '-' in part:
            # Range like 1-5
            try:
                start, end = part.split('-')
                start = int(start) - 1  # Convert to 0-based
                end = int(end) - 1
                for i in range(start, end + 1):
                    if 0 <= i < total:
                        indices.add(i)
            except ValueError:
                continue
        else:
            # Single number
            try:
                idx = int(part) - 1  # Convert to 0-based
                if 0 <= idx < total:
                    indices.add(idx)
            except ValueError:
                continue

    return sorted(list(indices))


if __name__ == "__main__":
    # Test the parser
    test_lines = [
        "192.168.1.1:8080",
        "10.0.0.1:3128:admin:password123",
        "myuser:mypass@proxy.example.com:8080",
        "http://user:pass@203.0.113.50:3128",
        "socks5://user:pass@198.51.100.10:1080",
        "# This is a comment",
        "",
    ]

    for line in test_lines:
        proxy = parse_proxy(line)
        if proxy:
            print(f"Parsed: {line}")
            print(f"  -> {proxy}")
            print(f"  -> Request proxies: {proxy.get_request_proxies()}")
            print()
