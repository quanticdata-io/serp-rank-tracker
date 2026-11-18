"""The record stored for one keyword check, and how it is read from a SERP payload."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .domains import matches, result_domain, result_url

#: Output columns, in order. A public contract: renaming one is a major release.
COLUMNS: tuple[str, ...] = (
    "checked_at",
    "keyword",
    "domain",
    "engine",
    "country",
    "lang",
    "location",
    "device",
    "position",
    "url",
    "display_link",
    "title",
    "all_positions",
    "organic_count",
    "depth",
    "ai_overview",
    "ai_overview_cites_domain",
    "featured_snippet",
    "featured_snippet_domain",
    "people_also_ask",
    "from_cache",
    "search_url",
)


@dataclass(frozen=True)
class SearchSettings:
    """Where and how a keyword is searched. Mapped 1:1 onto documented SERP parameters."""

    engine: str = "google"
    country: str | None = None
    lang: str | None = None
    location: str | None = None
    device: str = "desktop"
    depth: int = 10

    def params(self, keyword: str) -> dict[str, Any]:
        data: dict[str, Any] = {"query": keyword, "engine": self.engine, "num": self.depth}
        if self.country:
            data["country"] = self.country
        if self.lang:
            data["lang"] = self.lang
        if self.location:
            data["location"] = self.location
        if self.device != "desktop":
            data["device"] = self.device
        return data


@dataclass
class Check:
    checked_at: str
    keyword: str
    domain: str
    engine: str
    country: str | None
    lang: str | None
    location: str | None
    device: str
    position: int | None
    url: str | None
    display_link: str | None
    title: str | None
    all_positions: list[int] = field(default_factory=list)
    organic_count: int = 0
    depth: int = 10
    ai_overview: bool = False
    ai_overview_cites_domain: bool = False
    featured_snippet: bool = False
    featured_snippet_domain: bool = False
    people_also_ask: int = 0
    from_cache: bool = False
    search_url: str | None = None

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        return {k: row[k] for k in COLUMNS}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _reference_domain(ref: Any) -> str | None:
    if isinstance(ref, Mapping):
        return result_domain(ref)
    if isinstance(ref, str):
        return result_domain({"link": ref})
    return None


def _non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def check_from_payload(
    payload: Mapping[str, Any],
    *,
    keyword: str,
    domain: str,
    settings: SearchSettings,
    subdomains: bool = True,
    checked_at: str | None = None,
) -> Check:
    """Reads the target domain's ranking out of a ``/scraper/serp`` payload.

    Positions are 1-based and counted over the merged organic list, in order,
    so they stay continuous when ``num`` merged several Google pages.
    """
    organic = [o for o in payload.get("organic") or [] if isinstance(o, Mapping)]
    positions: list[int] = []
    first: Mapping[str, Any] | None = None
    for index, item in enumerate(organic, start=1):
        if matches(result_domain(item), domain, subdomains=subdomains):
            positions.append(index)
            if first is None:
                first = item

    references = payload.get("ai_overview_references") or []
    cites = any(matches(_reference_domain(r), domain, subdomains=subdomains) for r in references)

    snippet = payload.get("featured_snippet")
    snippet_ours = isinstance(snippet, Mapping) and matches(
        result_domain(snippet), domain, subdomains=subdomains
    )
    paa = payload.get("people_also_ask") or payload.get("related_questions") or []
    meta = payload.get("search_metadata") or {}

    def text(key: str) -> str | None:
        value = first.get(key) if first is not None else None
        return value if isinstance(value, str) and value else None

    return Check(
        checked_at=checked_at or now_iso(),
        keyword=keyword,
        domain=domain,
        engine=settings.engine,
        country=settings.country,
        lang=settings.lang,
        location=settings.location,
        device=settings.device,
        position=positions[0] if positions else None,
        url=result_url(first) if first is not None else None,
        display_link=text("display_link"),
        title=text("title"),
        all_positions=positions,
        organic_count=len(organic),
        depth=settings.depth,
        ai_overview=_non_empty(payload.get("ai_overview")) or bool(references),
        ai_overview_cites_domain=cites,
        featured_snippet=_non_empty(snippet),
        featured_snippet_domain=bool(snippet_ours),
        people_also_ask=len(paa) if isinstance(paa, list) else 0,
        from_cache=bool(meta.get("from_cache")) if isinstance(meta, Mapping) else False,
        search_url=meta.get("search_url") if isinstance(meta, Mapping) else None,
    )
