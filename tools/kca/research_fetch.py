"""Browser/HTTP fetch for the kca research workflow.

Two paths:
  - fetcher='http' (default): requests.get + readability/BeautifulSoup main-text.
  - fetcher='playwright': opt-in headless Chromium for JS-heavy pages.

Both paths treat fetched bytes as **untrusted data**. They never follow
instructions from page contents — extraction is purely structural.

Safety:
  - Refuse private/loopback hosts and file:// URLs (SSRF guard).
  - Optional allow-list via KCA_RESEARCH_ALLOW_DOMAINS (comma separated).
  - Byte cap via KCA_RESEARCH_MAX_BYTES (default 10 MB).
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_USER_AGENT = "kca-research/0.5 (+https://example.invalid/kca)"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def _max_bytes() -> int:
    raw = os.environ.get("KCA_RESEARCH_MAX_BYTES")
    if not raw:
        return DEFAULT_MAX_BYTES
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_MAX_BYTES


def _allow_domains() -> list[str] | None:
    raw = os.environ.get("KCA_RESEARCH_ALLOW_DOMAINS")
    if not raw:
        return None
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def _is_private_host(host: str) -> bool:
    """Return True for loopback/private/link-local/RFC1918 hosts."""
    if not host:
        return True
    h = host.lower().strip()
    if h in ("localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"):
        return True
    # Try to resolve via getaddrinfo, but also literal-parse first.
    try:
        ip = ipaddress.ip_address(h)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        pass
    # Resolve hostname
    try:
        infos = socket.getaddrinfo(h, None)
    except socket.gaierror:
        # Unresolvable hosts: be conservative and refuse only if it looks
        # like an internal hostname (no dot). Otherwise allow the request to
        # fail at request time.
        return "." not in h
    for info in infos:
        sockaddr = info[4]
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
    return False


def _check_policy(url: str) -> dict[str, Any] | None:
    """Return None if allowed, else an {ok: False, policy_warnings: [...]} dict."""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return {
            "ok": False,
            "url": url,
            "policy_warnings": [f"unsupported-scheme:{scheme or 'none'}"],
        }
    host = (parsed.hostname or "").lower()
    if _is_private_host(host):
        return {"ok": False, "url": url, "policy_warnings": ["private-net"]}
    allow = _allow_domains()
    if allow is not None:
        ok = any(host == d or host.endswith("." + d) for d in allow)
        if not ok:
            return {
                "ok": False,
                "url": url,
                "policy_warnings": ["domain-not-allowed"],
                "host": host,
            }
    return None


def _extract_main_text(html_bytes: bytes) -> str:
    """Best-effort main-content extraction. Never executes JS."""
    # Try readability-lxml first.
    try:
        from readability import Document  # type: ignore

        doc = Document(html_bytes.decode("utf-8", errors="replace"))
        summary_html = doc.summary(html_partial=True)
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(summary_html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        if text.strip():
            return text
    except Exception:
        pass
    # Fallback: BeautifulSoup strip script/style/nav.
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html_bytes, "html.parser")
        for tag in soup(["script", "style", "nav", "noscript", "header", "footer"]):
            tag.decompose()
        return soup.get_text("\n", strip=True)
    except Exception:
        return html_bytes.decode("utf-8", errors="replace")


def fetch_page(
    url: str,
    *,
    out_dir: Path,
    fetcher: str = "http",
    timeout_s: int = 20,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Fetch a page; write raw.html + main.txt; return result dict.

    Result keys:
      ok: bool
      url, fetcher, content_hash, http_status, raw_path, text_path
      screenshot_path: str | None
      bytes: int
      policy_warnings: list[str] (only when ok=False)
      error: str (only when ok=False)
    """
    policy = _check_policy(url)
    if policy is not None:
        return policy

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if fetcher == "playwright":
        return _fetch_playwright(
            url,
            out_dir=out_dir,
            timeout_s=timeout_s,
            user_agent=user_agent or DEFAULT_USER_AGENT,
        )
    if fetcher != "http":
        return {
            "ok": False,
            "url": url,
            "error": f"unknown fetcher: {fetcher}",
        }
    return _fetch_http(
        url,
        out_dir=out_dir,
        timeout_s=timeout_s,
        user_agent=user_agent or DEFAULT_USER_AGENT,
    )


def _fetch_http(
    url: str,
    *,
    out_dir: Path,
    timeout_s: int,
    user_agent: str,
) -> dict[str, Any]:
    try:
        import requests  # type: ignore
    except ImportError:
        return {
            "ok": False,
            "url": url,
            "error": "requests is not installed",
        }
    max_bytes = _max_bytes()
    headers = {"User-Agent": user_agent, "Accept": "text/html,*/*;q=0.5"}
    try:
        resp = requests.get(url, timeout=timeout_s, headers=headers, stream=True, allow_redirects=True)
    except Exception as e:
        return {"ok": False, "url": url, "error": f"fetch_error: {e}"}

    cl = resp.headers.get("Content-Length")
    if cl:
        try:
            if int(cl) > max_bytes:
                resp.close()
                return {
                    "ok": False,
                    "url": url,
                    "http_status": resp.status_code,
                    "policy_warnings": ["max-bytes-exceeded"],
                }
        except ValueError:
            pass

    buf = bytearray()
    for chunk in resp.iter_content(chunk_size=65536):
        if not chunk:
            continue
        buf.extend(chunk)
        if len(buf) > max_bytes:
            resp.close()
            return {
                "ok": False,
                "url": url,
                "http_status": resp.status_code,
                "policy_warnings": ["max-bytes-exceeded"],
            }
    resp.close()
    raw = bytes(buf)
    content_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    raw_path = out_dir / "raw.html"
    raw_path.write_bytes(raw)
    text = _extract_main_text(raw)
    text_path = out_dir / "main.txt"
    text_path.write_text(text, encoding="utf-8")
    return {
        "ok": True,
        "url": url,
        "fetcher": "http",
        "http_status": resp.status_code,
        "content_hash": content_hash,
        "raw_path": str(raw_path),
        "text_path": str(text_path),
        "screenshot_path": None,
        "bytes": len(raw),
    }


def _fetch_playwright(
    url: str,
    *,
    out_dir: Path,
    timeout_s: int,
    user_agent: str,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return {
            "ok": False,
            "url": url,
            "error": "playwright not installed; pip install playwright && playwright install chromium",
        }
    max_bytes = _max_bytes()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)
            html = page.content()
            raw = html.encode("utf-8", errors="replace")
            if len(raw) > max_bytes:
                browser.close()
                return {
                    "ok": False,
                    "url": url,
                    "policy_warnings": ["max-bytes-exceeded"],
                }
            text = page.inner_text("body")
            raw_path = out_dir / "raw.html"
            raw_path.write_bytes(raw)
            text_path = out_dir / "main.txt"
            text_path.write_text(text, encoding="utf-8")
            shot_path = out_dir / "screenshot.png"
            page.screenshot(path=str(shot_path), full_page=True)
            browser.close()
        content_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
        return {
            "ok": True,
            "url": url,
            "fetcher": "playwright",
            "http_status": 200,
            "content_hash": content_hash,
            "raw_path": str(raw_path),
            "text_path": str(text_path),
            "screenshot_path": str(shot_path),
            "bytes": len(raw),
        }
    except Exception as e:
        return {"ok": False, "url": url, "error": f"playwright_error: {e}"}
