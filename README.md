# ShiftProxies Proxy Tester

A CLI tool for testing HTTP and SOCKS5 proxies. Supports single and multi-URL testing with detailed output including latency, speed, block detection, and IP verification.

## Installation

1. Make sure you have Python 3.8 or higher installed
2. Install the required packages:

```bash
pip install rich requests
```

3. Place your proxies in a file called `proxies.txt` (one proxy per line)

## Usage

Run the tester:

```bash
python main.py
```

The tool will ask you for:

1. The proxy file path (defaults to `proxies.txt`)
2. Which proxies to test (enter numbers like `1,2,3` or ranges like `1-5` or just `all`)
3. The target URL(s) to test against

## Multi-URL Testing

You can test proxies against multiple websites at once by separating URLs with commas:

```
URLs [https://httpbin.org/ip]: google.com, amazon.com, nike.com
```

The output shows which proxies work on which sites:

```
#   Proxy              Success   google.com   amazon.com   nike.com
1   192.168.1.1:8080   3/3       OK           OK           OK
2   192.168.1.2:8080   2/3       OK           FAIL         OK
3   192.168.1.3:8080   0/3       FAIL         FAIL         FAIL
```

## Proxy Formats

The tool accepts these formats:

```
ip:port
ip:port:username:password
username:password@ip:port
http://username:password@ip:port
socks5://username:password@ip:port
```

## Output Columns

| Column | Meaning |
|--------|---------|
| Status | HTTP response code (200 = good) |
| Latency | Response time in milliseconds |
| Speed | Download speed in KB/s or MB/s |
| Ping | Network ping to proxy host |
| Blocked | Whether the site detected and blocked the proxy |
| IP | The IP address seen by the target website |

## Tips

1. Use `httpbin.org/ip` as a quick test (shows the proxy IP)
2. Test against actual target sites to check for blocks
3. Lower latency generally means better performance
4. If "Blocked" shows YES, the proxy works but the site is rejecting it

