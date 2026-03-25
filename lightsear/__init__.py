from __future__ import annotations

import typing as t
from collections import defaultdict

from scrapling.fetchers import StealthySession

from lightsear.engines.baidu import search_baidu
from lightsear.engines.bing import search_bing
from lightsear.engines.duckduckgo import search_duckduckgo
from lightsear.engines.google import search_google
from lightsear.models import SearchResult

if t.TYPE_CHECKING:
    from collections.abc import Sequence

EngineName = t.Literal["google", "baidu", "bing", "duckduckgo"]

ENGINES: dict[str, t.Callable[[t.Any, str], list[SearchResult]]] = {
    "google": search_google,
    "baidu": search_baidu,
    "bing": search_bing,
    "duckduckgo": search_duckduckgo,
}


def search(
    keyword: str,
    *,
    sources: "Sequence[str] | None" = None,
    timeout: float = 20.0,
    proxy: "str | None" = None,
) -> list[SearchResult]:
    """Run web search on one or more engines and return deduplicated, sorted results.

    Results are aggregated by URL across all queried engines. URLs returned by
    multiple engines appear first (sorted by hit count descending). Each
    :class:`SearchResult` exposes ``sources`` — a comma-separated string of
    every engine that returned that URL, e.g. ``'google,bing'``.

    :param keyword: Query string.
    :param sources: Engine names to query; default is all built-in engines.
    :param timeout: Timeout in seconds (converted to ms for the browser session).
    :param proxy: Optional proxy URL, e.g. ``"http://127.0.0.1:10808"``.
    """
    names = list(sources) if sources is not None else list(ENGINES.keys())
    for n in names:
        if n not in ENGINES:
            raise ValueError(f"Unknown source {n!r}; valid: {sorted(ENGINES)}")

    raw: list[SearchResult] = []
    with StealthySession(
        timeout=int(timeout * 1000),
        proxy=proxy,
        headless=True,
        disable_resources=True,
    ) as session:
        for name in names:
            raw.extend(ENGINES[name](session, keyword))

    # Aggregate by URL: merge sources and keep the first-seen title/content.
    seen: dict[str, list[str]] = defaultdict(list)
    first: dict[str, SearchResult] = {}
    for result in raw:
        url = result.url
        if url not in first:
            first[url] = result
        seen[url].append(result.sources)

    # Sort by hit count (descending), then by original appearance order.
    order = {url: i for i, url in enumerate(first)}
    aggregated: list[SearchResult] = []
    for url, engine_hits in sorted(
        seen.items(),
        key=lambda kv: (-len(kv[1]), order[kv[0]]),
    ):
        base = first[url]
        merged_sources = ",".join(dict.fromkeys(engine_hits))  # deduplicated, ordered
        aggregated.append(
            SearchResult(
                title=base.title,
                content=base.content,
                url=url,
                sources=merged_sources,
            )
        )
    return aggregated


__all__ = [
    "search",
    "SearchResult",
    "ENGINES",
    "search_google",
    "search_baidu",
    "search_bing",
    "search_duckduckgo",
]
