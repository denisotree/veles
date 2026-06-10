from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse

import html2text
import httpx

from veles.core.risk import RiskClass
from veles.core.tools.registry import tool
from veles.core.untrusted import wrap_untrusted

_USER_AGENT = "Veles/0.0.1"
_DEFAULT_TIMEOUT_SECONDS = 30.0
_ALLOW_PRIVATE_ENV = "VELES_FETCH_ALLOW_PRIVATE"

_PRIVATE_NETS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
)

_h2t = html2text.HTML2Text()
_h2t.ignore_links = False
_h2t.ignore_images = True
_h2t.ignore_tables = False
_h2t.body_width = 0  # no line-wrapping


def _is_safe_url(url: str) -> tuple[bool, str]:
    """Return (is_safe, reason). reason is empty when safe."""
    if os.environ.get(_ALLOW_PRIVATE_ENV) == "1":
        return True, ""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, f"unsupported scheme {parsed.scheme!r}"
    host = parsed.hostname
    if not host:
        return False, "missing hostname"
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return False, f"DNS lookup failed: {exc}"
    for info in infos:
        sockaddr = info[4]
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except (TypeError, ValueError):
            continue
        for net in _PRIVATE_NETS:
            if ip in net:
                return False, f"resolves to {ip} in blocked range {net}"
    return True, ""


def _html_to_markdown(html: str) -> str:
    return _h2t.handle(html)


@tool(
    risk_class=RiskClass.NETWORK_OPEN_WORLD,
    side_effects=["network"],
)
def fetch_url(url: str, max_bytes: int = 200_000) -> str:
    """Fetch `url` over HTTPS/HTTP and return the page content as text.

    HTML responses are automatically converted to readable markdown (links
    preserved, images stripped, navigation noise removed). Non-HTML responses
    (JSON, plain text, XML) are returned as-is.

    The URL is checked against a deny-list of private/loopback/link-local IPs
    (including AWS metadata) before the request is made. Set
    `VELES_FETCH_ALLOW_PRIVATE=1` to bypass — for local dev only.

    Decoded as UTF-8 with `errors="replace"`. Truncates to `max_bytes`
    characters after conversion. The response status code is appended on a
    final `<http <code>>` line.
    """
    ok, reason = _is_safe_url(url)
    if not ok:
        return f"<error: blocked: {reason}>"
    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=_DEFAULT_TIMEOUT_SECONDS,
            headers={"User-Agent": _USER_AGENT},
        )
    except httpx.HTTPError as exc:
        return f"<error fetching {url}: {type(exc).__name__}: {exc}>"

    content_type = response.headers.get("content-type", "")
    body = response.text
    if "text/html" in content_type:
        body = _html_to_markdown(body)

    truncated_marker = ""
    if len(body) > max_bytes:
        body = body[:max_bytes]
        truncated_marker = f"\n<truncated to {max_bytes} chars>"
    wrapped = wrap_untrusted(f"{body}{truncated_marker}", source=url)
    return f"{wrapped}\n<http {response.status_code}>"
