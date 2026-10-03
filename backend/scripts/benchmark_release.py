"""Descriptive release measurements; no timing thresholds or repeated live fetches."""

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from statistics import median
from time import perf_counter

import httpx

from app.adapters.scraper import parse_entries
from app.domain.filters import filter_entries
from app.domain.models import EntryFilter


def summary(samples: list[float]) -> dict[str, float | int]:
    ordered = sorted(samples)
    return {
        "n": len(ordered),
        "median_ms": round(median(ordered), 3),
        "p95_ms": round(ordered[int((len(ordered) - 1) * 0.95)], 3),
        "min_ms": round(ordered[0], 3),
        "max_ms": round(ordered[-1], 3),
    }


def measure(action: Callable[[], object], count: int) -> list[float]:
    samples = []
    for _ in range(count):
        start = perf_counter()
        action()
        samples.append((perf_counter() - start) * 1000)
    return samples


def benchmark_fixture(count: int) -> dict[str, dict[str, float | int]]:
    fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/front_page.html"
    html = fixture.read_text(encoding="utf-8")
    entries = parse_entries(html)
    parse_entries(html)  # Warm imports and parser initialization.
    results = {"parse_30": summary(measure(lambda: parse_entries(html), count))}
    for entry_filter in EntryFilter:
        def action(entry_filter: EntryFilter = entry_filter) -> object:
            return filter_entries(entries, entry_filter)

        action()
        results[f"filter_{entry_filter.value}"] = summary(measure(action, count))
    return results


def benchmark_api(base_url: str, count: int) -> dict[str, object]:
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=30) as client:
        def request(entry_filter: str) -> tuple[float, dict[str, object]]:
            start = perf_counter()
            response = client.get("/api/v1/entries", params={"filter": entry_filter})
            elapsed = (perf_counter() - start) * 1000
            response.raise_for_status()
            return elapsed, response.json()

        cold_ms, cold = request("all")
        if cold["cache_hit"] is not False or cold["source_count"] != 30:
            raise RuntimeError(
                "Expected a fresh API process and a 30-entry cold request"
            )
        warm = []
        for index in range(count):
            elapsed, result = request(("long", "short", "all")[index % 3])
            if result["cache_hit"] is not True or result["source_count"] != 30:
                raise RuntimeError("Expected warm requests within the cache TTL")
            warm.append(elapsed)
    return {"cold": summary([cold_ms]), "warm": summary(warm)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-samples", type=int, default=200)
    parser.add_argument("--warm-samples", type=int, default=8)
    parser.add_argument(
        "--api-url", help="Fresh API process; makes one live upstream fetch"
    )
    args = parser.parse_args()
    if args.fixture_samples < 1 or args.warm_samples < 1:
        parser.error("sample counts must be positive")
    results: dict[str, object] = {"fixture": benchmark_fixture(args.fixture_samples)}
    if args.api_url:
        results["api"] = benchmark_api(args.api_url, args.warm_samples)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
