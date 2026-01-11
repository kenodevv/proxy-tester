import re
from dataclasses import dataclass
from typing import Optional
import hashlib


@dataclass
class BlockDetectionResult:
    is_blocked: bool
    reason: Optional[str] = None
    confidence: float = 0.0  # 0.0 to 1.0


HIGH_CONFIDENCE_KEYWORDS = [
    "access denied",
    "403 forbidden",
    "401 unauthorized",
    "your ip has been blocked",
    "ip blocked",
    "ip banned",
    "you have been blocked",
    "sorry, you have been blocked",
    "request blocked",
    "access denied - akamai",
]

MEDIUM_CONFIDENCE_KEYWORDS = [
    "verify you are human",
    "human verification",
    "checking your browser",
    "please wait while we verify",
    "enable javascript and cookies",
    "too many requests",
    "rate limit exceeded",
]

LOW_CONFIDENCE_KEYWORDS = [
    "captcha",
    "recaptcha",
    "hcaptcha",
    "cloudflare",
    "security check",
]

BLOCKED_STATUS_CODES = {
    401: "Unauthorized",
    403: "Forbidden",
    407: "Proxy Authentication Required",
    429: "Too Many Requests",
    503: "Service Unavailable (possibly blocked)",
}


def detect_block(response_text: str, status_code: int, content_length: int,
                 reference_hash: Optional[str] = None, reference_length: Optional[int] = None) -> BlockDetectionResult:
    reasons = []
    confidence = 0.0

    content_lower = response_text.lower()

    title_match = re.search(r'<title[^>]*>(.*?)</title>', content_lower, re.IGNORECASE | re.DOTALL)
    title_text = title_match.group(1) if title_match else ""

    if status_code in [403, 429]:
        reasons.append(f"HTTP {status_code}: {BLOCKED_STATUS_CODES.get(status_code, 'Error')}")
        confidence += 0.3

    for keyword in HIGH_CONFIDENCE_KEYWORDS:
        if keyword.lower() in title_text:
            confidence += 0.5
            reasons.append(f"Block indicator in title: {keyword}")
            break
        elif keyword.lower() in content_lower and content_length < 5000:
            confidence += 0.3
            reasons.append(f"Block indicator: {keyword}")
            break

    if content_length < 10000:
        for keyword in MEDIUM_CONFIDENCE_KEYWORDS:
            if keyword.lower() in content_lower:
                confidence += 0.2
                reasons.append(f"Possible block: {keyword}")
                break

    if content_length < 3000:
        low_count = sum(1 for kw in LOW_CONFIDENCE_KEYWORDS if kw.lower() in content_lower)
        if low_count >= 2:
            confidence += 0.15
            reasons.append("Multiple security indicators")

    if content_length < 500 and status_code >= 400:
        confidence += 0.2
        reasons.append("Short error response")

    if content_length < 100 and status_code != 204:
        confidence += 0.3
        reasons.append("Nearly empty response")

    if content_length > 50000:
        confidence *= 0.3
    elif content_length > 20000:
        confidence *= 0.5

    confidence = min(1.0, confidence)
    is_blocked = confidence >= 0.5

    reason = "; ".join(reasons) if reasons else None

    return BlockDetectionResult(
        is_blocked=is_blocked,
        reason=reason,
        confidence=confidence
    )


def get_content_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def check_ip_match(response_text: str, expected_ip: str) -> bool:
    return expected_ip in response_text


LEGITIMATE_PATTERNS = [
    r'<html[^>]*>.*<body[^>]*>.*</body>.*</html>',
    r'<!DOCTYPE html>',
]


def looks_legitimate(response_text: str, min_length: int = 1000) -> bool:
    if len(response_text) < min_length:
        return False

    has_html = bool(re.search(r'<html', response_text, re.IGNORECASE))
    has_body = bool(re.search(r'<body', response_text, re.IGNORECASE))

    return has_html and has_body
