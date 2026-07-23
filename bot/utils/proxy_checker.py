import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import aiohttp

ProgressCallback = Callable[[int, int], Awaitable[None]]

_PROXY_AT_RE = re.compile(
    r"^(?:(?P<user>[^:]+):(?P<pass>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)$"
)


@dataclass
class CheckResult:
    proxy: str
    alive: bool
    detail: str


def normalize_proxy(line: str) -> str | None:
    """Parse supported formats into user:pass@host:port or host:port."""
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


async def check_proxy(line: str, timeout: float = 8.0) -> CheckResult:
    normalized = normalize_proxy(line)
    if not normalized:
        return CheckResult(line.strip(), False, "Invalid format")

    parsed = parse_proxy(normalized)
    if not parsed:
        return CheckResult(normalized, False, "Invalid format")

    host, port, user, password = parsed

    try:
        auth = aiohttp.BasicAuth(user, password) if user and password else None
        connector = aiohttp.TCPConnector(ssl=False, limit=0)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                "http://httpbin.org/ip",
                proxy=f"http://{host}:{port}",
                proxy_auth=auth,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ip = data.get("origin", "unknown")
                    return CheckResult(normalized, True, f"Online — IP: {ip}")
                return CheckResult(normalized, False, f"HTTP {resp.status}")
    except asyncio.TimeoutError:
        return CheckResult(normalized, False, "Timeout")
    except Exception as exc:
        return CheckResult(normalized, False, str(exc)[:80])


async def check_proxies(
    lines: list[str],
    *,
    max_concurrent: int = 50,
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
