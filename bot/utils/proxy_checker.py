import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import quote

import aiohttp

ProgressCallback = Callable[[int, int], Awaitable[None]]

_PROXY_AT_RE = re.compile(
    r"^(?:(?P<user>[^:]+):(?P<pass>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)$"
)

_CHECK_URLS = (
    "http://ifconfig.me/ip",
    "http://ip-api.com/json/?fields=query",
    "http://httpbin.org/ip",
)


@dataclass
class CheckResult:
    proxy: str
    alive: bool
    detail: str


def normalize_proxy(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    if "@" in line:
        return line if _PROXY_AT_RE.match(line) else None

    parts = line.split(":")
    if len(parts) == 2:
        return line if _PROXY_AT_RE.match(line) else None
    if len(parts) == 4:
        host, port, user, password = parts
        normalized = f"{user}:{password}@{host}:{port}"
        return normalized if _PROXY_AT_RE.match(normalized) else None
    return None


def parse_proxies_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    proxies: list[str] = []
    for line in text.splitlines():
        normalized = normalize_proxy(line)
        if normalized and normalized not in seen:
            seen.add(normalized)
            proxies.append(normalized)
    return proxies


def parse_proxy(line: str) -> tuple[str, int, str | None, str | None] | None:
    normalized = normalize_proxy(line)
    if not normalized:
        return None
    match = _PROXY_AT_RE.match(normalized)
    if not match:
        return None
    return (
        match.group("host"),
        int(match.group("port")),
        match.group("user"),
        match.group("pass"),
    )


def _proxy_url(scheme: str, host: str, port: int, user: str | None, password: str | None) -> str:
    if user and password:
        return f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
    return f"{scheme}://{host}:{port}"


def _extract_ip(body: str, url: str) -> str:
    body = body.strip()
    if "ip-api.com" in url or "httpbin.org" in url:
        try:
            data = json.loads(body)
            if "query" in data:
                return str(data["query"])
            if "origin" in data:
                return str(data["origin"])
        except json.JSONDecodeError:
            pass
    return body.split(",")[0].strip()[:64]


async def _probe_urls(session: aiohttp.ClientSession, timeout: float) -> str | None:
    for url in _CHECK_URLS:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    body = await resp.text()
                    return _extract_ip(body, url)
        except asyncio.TimeoutError:
            continue
        except Exception:
            continue
    return None


async def _check_http_proxy(
    host: str, port: int, user: str | None, password: str | None, timeout: float
) -> str | None:
    proxy = _proxy_url("http", host, port, user, password)
    connector = aiohttp.TCPConnector(ssl=False, force_close=True)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            for url in _CHECK_URLS:
                try:
                    async with session.get(
                        url,
                        proxy=proxy,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                    ) as resp:
                        if resp.status == 200:
                            body = await resp.text()
                            ip = _extract_ip(body, url)
                            return f"Live (HTTP) — IP: {ip}"
                except (asyncio.TimeoutError, Exception):
                    continue
    finally:
        await connector.close()
    return None


async def _check_socks5_proxy(
    host: str, port: int, user: str | None, password: str | None, timeout: float
) -> str | None:
    try:
        from aiohttp_socks import ProxyConnector
    except ImportError:
        return None

    proxy = _proxy_url("socks5", host, port, user, password)
    try:
        connector = ProxyConnector.from_url(proxy, rdns=True)
        async with aiohttp.ClientSession(connector=connector) as session:
            ip = await _probe_urls(session, timeout)
            if ip:
                return f"Live (SOCKS5) — IP: {ip}"
    except Exception:
        return None
    return None


async def check_proxy(line: str, timeout: float = 12.0) -> CheckResult:
    normalized = normalize_proxy(line)
    if not normalized:
        return CheckResult(line.strip(), False, "Invalid format")

    parsed = parse_proxy(normalized)
    if not parsed:
        return CheckResult(normalized, False, "Invalid format")

    host, port, user, password = parsed

    http_detail = await _check_http_proxy(host, port, user, password, timeout)
    if http_detail:
        return CheckResult(normalized, True, http_detail)

    socks_detail = await _check_socks5_proxy(host, port, user, password, timeout)
    if socks_detail:
        return CheckResult(normalized, True, socks_detail)

    return CheckResult(normalized, False, "Dead — not responding as HTTP or SOCKS5 proxy")


async def check_proxies(
    lines: list[str],
    *,
    max_concurrent: int = 30,
    on_progress: ProgressCallback | None = None,
) -> list[CheckResult]:
    proxies = parse_proxies_from_text("\n".join(lines))
    if not proxies:
        return []

    total = len(proxies)
    results: list[CheckResult | None] = [None] * total
    done = 0
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(max_concurrent)

    async def run_one(index: int, proxy: str) -> None:
        nonlocal done
        async with sem:
            result = await check_proxy(proxy)
        results[index] = result
        async with lock:
            done += 1
            if on_progress:
                await on_progress(done, total)

    await asyncio.gather(*(run_one(i, p) for i, p in enumerate(proxies)))
    return [r for r in results if r is not None]


def progress_bar(done: int, total: int, width: int = 16) -> str:
    if total <= 0:
        return "[░░░░░░░░░░░░░░░░] 0/0 (0%)"
    ratio = done / total
    filled = int(width * ratio)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {done}/{total} ({int(ratio * 100)}%)"
