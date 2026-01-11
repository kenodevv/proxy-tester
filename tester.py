import time
import subprocess
import platform
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

from proxy_parser import Proxy
from detector import detect_block, get_content_hash, BlockDetectionResult


@dataclass
class URLTestResult:
    url: str
    success: bool = False
    http_status: Optional[int] = None
    http_error: Optional[str] = None
    latency_ms: Optional[float] = None
    download_speed_kbps: Optional[float] = None
    content_length: int = 0
    block_result: Optional[BlockDetectionResult] = None

    def is_working(self) -> bool:
        if not self.success or self.http_status is None:
            return False
        if self.http_status >= 500:
            return False
        if self.block_result and self.block_result.is_blocked and self.block_result.confidence > 0.6:
            return False
        return True


@dataclass
class MultiURLTestResult:
    proxy: Proxy
    url_results: Dict[str, URLTestResult] = field(default_factory=dict)
    ping_ms: Optional[float] = None
    ping_error: Optional[str] = None
    detected_ip: Optional[str] = None

    def working_count(self) -> int:
        return sum(1 for r in self.url_results.values() if r.is_working())

    def total_count(self) -> int:
        return len(self.url_results)

    def is_fully_working(self) -> bool:
        return len(self.url_results) > 0 and all(r.is_working() for r in self.url_results.values())

    def avg_latency(self) -> Optional[float]:
        latencies = [r.latency_ms for r in self.url_results.values()
                     if r.is_working() and r.latency_ms]
        return sum(latencies) / len(latencies) if latencies else None


@dataclass
class TestResult:
    proxy: Proxy
    success: bool = False
    http_status: Optional[int] = None
    http_error: Optional[str] = None
    latency_ms: Optional[float] = None
    download_speed_kbps: Optional[float] = None
    content_length: int = 0
    block_result: Optional[BlockDetectionResult] = None
    ping_ms: Optional[float] = None
    ping_error: Optional[str] = None
    detected_ip: Optional[str] = None

    def is_working(self) -> bool:
        if not self.success or self.http_status is None:
            return False
        if self.http_status >= 500:
            return False
        if self.block_result and self.block_result.is_blocked and self.block_result.confidence > 0.6:
            return False
        return True


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
DEFAULT_TIMEOUT = 15


def test_http(proxy: Proxy, url: str, timeout: int = DEFAULT_TIMEOUT,
               reference_hash: Optional[str] = None, reference_length: Optional[int] = None) -> TestResult:
    result = TestResult(proxy=proxy)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    try:
        proxies = proxy.get_request_proxies()

        start_time = time.time()
        response = requests.get(
            url,
            proxies=proxies,
            headers=headers,
            timeout=timeout,
            verify=False,  # Ignore SSL errors for testing
            allow_redirects=True
        )
        end_time = time.time()

        result.latency_ms = (end_time - start_time) * 1000
        result.http_status = response.status_code
        result.content_length = len(response.content)

        if result.latency_ms > 0:
            result.download_speed_kbps = (result.content_length / 1024) / (result.latency_ms / 1000)

        result.block_result = detect_block(
            response_text=response.text,
            status_code=response.status_code,
            content_length=result.content_length,
            reference_hash=reference_hash,
            reference_length=reference_length
        )

        result.success = True

    except requests.exceptions.ProxyError as e:
        result.http_error = "Proxy connection failed"
        result.success = False
    except requests.exceptions.ConnectTimeout:
        result.http_error = "Connection timeout"
        result.success = False
    except requests.exceptions.ReadTimeout:
        result.http_error = "Read timeout"
        result.success = False
    except requests.exceptions.SSLError as e:
        result.http_error = f"SSL Error: {str(e)[:50]}"
        result.success = False
    except requests.exceptions.ConnectionError as e:
        result.http_error = "Connection failed"
        result.success = False
    except Exception as e:
        result.http_error = f"Error: {str(e)[:50]}"
        result.success = False

    return result


def test_ping(proxy: Proxy, count: int = 3) -> tuple[Optional[float], Optional[str]]:
    host = proxy.host
    system = platform.system().lower()

    try:
        if system == "windows":
            cmd = ["ping", "-n", str(count), "-w", "2000", host]
        else:
            cmd = ["ping", "-c", str(count), "-W", "2", host]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            output = result.stdout
            if system == "windows":
                import re
                match = re.search(r'Average\s*=\s*(\d+)ms', output)
                if match:
                    return float(match.group(1)), None
            else:
                import re
                match = re.search(r'avg[^=]*=\s*[\d.]+/([\d.]+)/', output)
                if match:
                    return float(match.group(1)), None
                times = re.findall(r'time[=<]([\d.]+)\s*ms', output)
                if times:
                    avg = sum(float(t) for t in times) / len(times)
                    return round(avg, 2), None

            return None, "Could not parse ping output"
        else:
            return None, "Host unreachable"

    except subprocess.TimeoutExpired:
        return None, "Ping timeout"
    except Exception as e:
        return None, f"Ping error: {str(e)[:30]}"


def check_proxy_ip(proxy: Proxy, timeout: int = 10) -> Optional[str]:
    ip_check_urls = [
        "https://api.ipify.org",
        "https://icanhazip.com",
        "https://ipinfo.io/ip",
    ]

    for url in ip_check_urls:
        try:
            response = requests.get(
                url,
                proxies=proxy.get_request_proxies(),
                timeout=timeout,
                headers={"User-Agent": USER_AGENT}
            )
            if response.status_code == 200:
                ip = response.text.strip()
                if ip and len(ip) < 50:
                    return ip
        except:
            continue

    return None


def get_reference_response(url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[Optional[str], Optional[int]]:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            verify=False
        )
        content_hash = get_content_hash(response.text)
        return content_hash, len(response.content)
    except:
        return None, None


def test_proxy_full(proxy: Proxy, url: str, reference_hash: Optional[str] = None,
                    reference_length: Optional[int] = None, include_ping: bool = True,
                    include_ip_check: bool = True) -> TestResult:
    result = test_http(proxy, url, reference_hash=reference_hash, reference_length=reference_length)

    if include_ping:
        ping_ms, ping_error = test_ping(proxy)
        result.ping_ms = ping_ms
        result.ping_error = ping_error

    if include_ip_check and result.success:
        result.detected_ip = check_proxy_ip(proxy)

    return result


def test_proxies_parallel(proxies: List[Proxy], url: str, max_workers: int = 10,
                          include_ping: bool = True, include_ip_check: bool = True,
                          progress_callback: Optional[Callable[[int, int, TestResult], None]] = None) -> List[TestResult]:
    reference_hash, reference_length = get_reference_response(url)

    results = [None] * len(proxies)
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(
                test_proxy_full,
                proxy,
                url,
                reference_hash,
                reference_length,
                include_ping,
                include_ip_check
            ): i
            for i, proxy in enumerate(proxies)
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                result = future.result()
            except Exception as e:
                result = TestResult(
                    proxy=proxies[index],
                    success=False,
                    http_error=f"Test failed: {str(e)[:50]}"
                )

            results[index] = result
            completed += 1

            if progress_callback:
                progress_callback(completed, len(proxies), result)

    return results


# Suppress SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def test_http_for_url(proxy: Proxy, url: str, reference_hash: Optional[str] = None,
                      reference_length: Optional[int] = None, timeout: int = DEFAULT_TIMEOUT) -> URLTestResult:
    result = URLTestResult(url=url)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    try:
        proxies = proxy.get_request_proxies()

        start_time = time.time()
        response = requests.get(
            url,
            proxies=proxies,
            headers=headers,
            timeout=timeout,
            verify=False,
            allow_redirects=True
        )
        end_time = time.time()

        result.latency_ms = (end_time - start_time) * 1000
        result.http_status = response.status_code
        result.content_length = len(response.content)

        if result.latency_ms > 0:
            result.download_speed_kbps = (result.content_length / 1024) / (result.latency_ms / 1000)

        result.block_result = detect_block(
            response_text=response.text,
            status_code=response.status_code,
            content_length=result.content_length,
            reference_hash=reference_hash,
            reference_length=reference_length
        )

        result.success = True

    except requests.exceptions.ProxyError:
        result.http_error = "Proxy connection failed"
    except requests.exceptions.ConnectTimeout:
        result.http_error = "Connection timeout"
    except requests.exceptions.ReadTimeout:
        result.http_error = "Read timeout"
    except requests.exceptions.SSLError as e:
        result.http_error = f"SSL Error: {str(e)[:50]}"
    except requests.exceptions.ConnectionError:
        result.http_error = "Connection failed"
    except Exception as e:
        result.http_error = f"Error: {str(e)[:50]}"

    return result


def test_proxy_multi_url(proxy: Proxy, urls: List[str],
                         reference_data: Dict[str, Tuple[Optional[str], Optional[int]]],
                         include_ping: bool = True, include_ip_check: bool = True) -> MultiURLTestResult:
    result = MultiURLTestResult(proxy=proxy)

    for url in urls:
        ref_hash, ref_length = reference_data.get(url, (None, None))
        url_result = test_http_for_url(proxy, url, ref_hash, ref_length)
        result.url_results[url] = url_result

    if include_ping:
        result.ping_ms, result.ping_error = test_ping(proxy)

    if include_ip_check and any(r.success for r in result.url_results.values()):
        result.detected_ip = check_proxy_ip(proxy)

    return result


def test_proxies_multi_url_parallel(proxies: List[Proxy], urls: List[str], max_workers: int = 10,
                                     include_ping: bool = True, include_ip_check: bool = True,
                                     progress_callback: Optional[Callable[[int, int, MultiURLTestResult], None]] = None) -> List[MultiURLTestResult]:
    reference_data: Dict[str, Tuple[Optional[str], Optional[int]]] = {}
    for url in urls:
        ref_hash, ref_length = get_reference_response(url)
        reference_data[url] = (ref_hash, ref_length)

    results: List[Optional[MultiURLTestResult]] = [None] * len(proxies)
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(
                test_proxy_multi_url,
                proxy,
                urls,
                reference_data,
                include_ping,
                include_ip_check
            ): i
            for i, proxy in enumerate(proxies)
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                result = future.result()
            except Exception as e:
                result = MultiURLTestResult(proxy=proxies[index])
                for url in urls:
                    result.url_results[url] = URLTestResult(
                        url=url,
                        success=False,
                        http_error=f"Test failed: {str(e)[:50]}"
                    )

            results[index] = result
            completed += 1

            if progress_callback:
                progress_callback(completed, len(proxies), result)

    return results  # type: ignore
