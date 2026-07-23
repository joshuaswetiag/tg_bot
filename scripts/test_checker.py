"""Quick proxy checker smoke test."""

import asyncio
import sys

from bot.utils.proxy_checker import check_proxies, parse_proxies_from_text, progress_bar


def test_parse() -> None:
    text = """
vSWOdfHdZfA0_custom_zone_AI_st__city_sid_57260950_time_5:4899816:change4.owlproxy.com:7778
103.45.12.1:8080
103.45.12.2:8080:user:pass
user:pass@103.45.12.3:3128
invalid line
"""
    parsed = parse_proxies_from_text(text)
    assert len(parsed) == 4, parsed
    assert parsed[0].endswith("@change4.owlproxy.com:7778"), parsed[0]
    assert parsed[0].startswith("vSWOdfHdZfA0"), parsed[0]
    assert parsed[2] == "user:pass@103.45.12.2:8080", parsed[2]
    print("Parse test: PASS")


async def test_check_dead() -> None:
    proxies = ["127.0.0.1:1", "127.0.0.1:2", "192.0.2.1:8080"]
    progress: list[tuple[int, int]] = []

    async def on_progress(done: int, total: int) -> None:
        progress.append((done, total))
        print(f"  Progress: {done}/{total}")

    print("Checking 3 proxies (expect all dead)...")
    results = await check_proxies(proxies, on_progress=on_progress, max_concurrent=3)

    live = sum(1 for r in results if r.alive)
    dead = sum(1 for r in results if not r.alive)
    print(f"Results: total={len(results)} live={live} dead={dead}")

    for r in results:
        status = "LIVE" if r.alive else "DEAD"
        print(f"  [{status}] {r.proxy} — {r.detail}")

    assert len(results) == 3
    assert len(progress) >= 3
    print("Checker flow: PASS")


async def test_check_public_proxy_list() -> None:
    """Try a few free public proxies if any respond (optional live test)."""
    # Common format test only - no guarantee these work
    sample = parse_proxies_from_text("8.8.8.8:8080\n1.1.1.1:8080")
    if not sample:
        return
    results = await check_proxies(sample[:2], max_concurrent=2)
    print(f"Public sample check: {sum(r.alive for r in results)}/{len(results)} live")


def main() -> int:
    print("=== Proxy Checker Tests ===\n")
    test_parse()
    asyncio.run(test_check_dead())
    asyncio.run(test_check_public_proxy_list())
    print("\nAll tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
