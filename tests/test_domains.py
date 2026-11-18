from __future__ import annotations

import pytest

from serp_rank_tracker.domains import (
    host_of_display_link,
    is_click_address,
    matches,
    normalise_domain,
    result_domain,
    result_url,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("example.com", "example.com"),
        ("https://WWW.Example.com/path?q=1", "example.com"),
        ("www.example.com/", "example.com"),
        ("example.com:8080", "example.com"),
        ("Blog.Example.com.", "blog.example.com"),
    ],
)
def test_normalise_domain(value: str, expected: str) -> None:
    assert normalise_domain(value) == expected


@pytest.mark.parametrize(
    ("display", "expected"),
    [
        ("yoast.com › SEO blog › Technical SEO", "yoast.com"),
        ("www.youtube.com › watch", "youtube.com"),
        ("https://docs.python.org › library › http.html", "docs.python.org"),
        ("error404.atomseo.com › blog › robots-txt", "error404.atomseo.com"),
        ("Some text without a host", None),
    ],
)
def test_host_of_display_link(display: str, expected: str | None) -> None:
    assert host_of_display_link(display) == expected


def test_click_address_is_not_a_result_url() -> None:
    item = {"link": "https://www.google.com/url?q=redacted-1&sa=U", "display_link": "yoast.com › blog"}
    assert is_click_address(item["link"])
    assert result_url(item) is None
    assert result_domain(item) == "yoast.com"


def test_source_wins_over_link() -> None:
    item = {"link": "https://forum.example.org/t", "source": "example.org"}
    assert result_domain(item) == "example.org"


def test_link_host_used_when_no_source() -> None:
    assert result_domain({"link": "https://www.example.net/a"}) == "example.net"


def test_matches_subdomains() -> None:
    assert matches("blog.example.com", "example.com")
    assert not matches("blog.example.com", "example.com", subdomains=False)
    assert matches("example.com", "www.example.com", subdomains=False)
    assert not matches("notexample.com", "example.com")
    assert not matches(None, "example.com")
