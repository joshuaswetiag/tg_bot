import asyncio
import re
from dataclasses import dataclass

import aiohttp


@dataclass
class CheckResult:
    proxy: str
    alive: bool
    detail: str


_PROXY_RE = re.compile(
    r"^(?:(?P<user>[^:]+):(?P<pass>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)$"
)


def parse_proxy(line: str) -> tuple[str, int, str | None, str | None] | None:
    line = line.strip()
    match = _PROXY_RE.match(line)
    if not match:
        return None
    host = match.group("host")
    port = int(match.group("port"))
    return host, port, match.group("user"), match.group("pass")


async def check_proxy(line: str, timeout: float = 8.0) -> CheckResult:
    parsed = parse_proxy(line)
    if not parsed:
        return CheckResult(line, False, "Invalid format (use host:port or user:pass@host:port)")

    host, port, user, password = parsed
    proxy_url = line if "@" in line else f"{host}:{port}"

    try:
        auth = aiohttp.BasicAuth(user, password) if user and password else None
        connector = aiohttp.TCPConnector(ssl=False)
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
                    return CheckResult(proxy_url, True, f"Online — IP: {ip}")
                return CheckResult(proxy_url, False, f"HTTP {resp.status}")
    except asyncio.TimeoutError:
        return CheckResult(proxy_url, False, "Timeout")
    except Exception as exc:
        return CheckResult(proxy_url, False, str(exc)[:80])


async def check_proxies(lines: list[str]) -> list[CheckResult]:
    tasks = [check_proxy(line) for line in lines[:10]]
    return await asyncio.gather(*tasks)
