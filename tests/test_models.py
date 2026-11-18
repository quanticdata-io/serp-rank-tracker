from __future__ import annotations

from serp_rank_tracker import COLUMNS, SearchSettings, check_from_payload

from .helpers import payload

GOOGLE = SearchSettings(country="us", lang="en", location="New York, New York, United States", depth=20)


def test_click_address_result_is_found_by_display_link() -> None:
    check = check_from_payload(
        payload("google_sitemap_xml.json"),
        keyword="what is a sitemap xml",
        domain="webnode.com",
        settings=GOOGLE,
    )
    assert check.position == 7
    assert check.all_positions == [7, 8]
    assert check.url is None  # Google returned only its click address
    assert check.display_link is not None
    assert check.display_link.startswith("www.webnode.com")
    assert check.organic_count == 17
    assert check.ai_overview is True
    assert check.ai_overview_cites_domain is False
    assert check.from_cache is True
    assert check.search_url is not None
    assert check.search_url.startswith("https://www.google.com/search?")


def test_direct_link_gives_the_ranking_url() -> None:
    check = check_from_payload(
        payload("google_sitemap_xml.json"), keyword="k", domain="xml-sitemaps.com", settings=GOOGLE
    )
    assert check.position == 3
    assert check.url == "https://www.xml-sitemaps.com/"


def test_subdomain_option() -> None:
    data = payload("google_sitemap_xml.json")
    assert check_from_payload(data, keyword="k", domain="wikipedia.org", settings=GOOGLE).position == 5
    strict = check_from_payload(data, keyword="k", domain="wikipedia.org", settings=GOOGLE, subdomains=False)
    assert strict.position is None
    assert strict.all_positions == []


def test_not_ranking() -> None:
    check = check_from_payload(
        payload("google_sitemap_xml.json"), keyword="k", domain="example.com", settings=GOOGLE
    )
    assert check.position is None
    assert check.url is None
    assert check.title is None


def test_bing_results() -> None:
    settings = SearchSettings(engine="bing", country="us", lang="en")
    check = check_from_payload(
        payload("bing_python_http_client.json"),
        keyword="python http client library",
        domain="python.org",
        settings=settings,
    )
    assert check.position == 1
    assert check.all_positions == [1, 2]
    assert check.url == "https://docs.python.org/3/library/http.client.html"
    assert check.ai_overview is False
    assert check.engine == "bing"


def test_rich_blocks() -> None:
    data = payload("synthetic_rich_blocks.json")
    settings = SearchSettings(country="us")
    ours = check_from_payload(data, keyword="best burr grinder", domain="example.com", settings=settings)
    assert ours.position == 2  # blog.example.com
    assert ours.all_positions == [2, 3]
    assert ours.url == "https://blog.example.com/grinders"
    assert ours.ai_overview
    assert ours.ai_overview_cites_domain
    assert ours.featured_snippet
    assert ours.featured_snippet_domain
    assert ours.people_also_ask == 2

    other = check_from_payload(data, keyword="best burr grinder", domain="example.org", settings=settings)
    assert other.position == 4
    assert not other.ai_overview_cites_domain
    assert other.featured_snippet
    assert not other.featured_snippet_domain


def test_row_has_every_column() -> None:
    check = check_from_payload(
        payload("synthetic_rich_blocks.json"), keyword="k", domain="example.com", settings=SearchSettings()
    )
    assert tuple(check.as_row()) == COLUMNS


def test_settings_params() -> None:
    assert SearchSettings().params("q") == {"query": "q", "engine": "google", "num": 10}
    params = SearchSettings(
        engine="bing", country="it", lang="it", location="Milan, Italy", device="mobile", depth=30
    ).params("caffè")
    assert params == {
        "query": "caffè",
        "engine": "bing",
        "num": 30,
        "country": "it",
        "lang": "it",
        "location": "Milan, Italy",
        "device": "mobile",
    }
