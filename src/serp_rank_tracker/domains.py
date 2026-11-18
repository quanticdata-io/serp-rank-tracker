"""Which domain a search result belongs to.

Google often links a result through its own click address
(``https://www.google.com/url?...``) and then leaves ``source`` empty. The
host is still printed in ``display_link`` (``"yoast.com › SEO blog"``), so the
lookup order is: ``source``, then the host of ``link`` when it is not a click
address, then the first segment of ``display_link``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

_CLICK_HOSTS = frozenset({"google.com", "www.google.com"})
_SEPARATORS = ("›", ">", " ", "/")


def normalise_domain(value: str) -> str:
    """``"https://WWW.Example.com/path"`` -> ``"example.com"``."""
    text = value.strip().lower()
    text = (urlsplit(text).hostname or "") if "://" in text else text.split("/", 1)[0]
    text = text.split(":", 1)[0].strip(".")
    if text.startswith("www."):
        text = text[4:]
    return text


def host_of_url(url: str) -> str | None:
    try:
        host = urlsplit(url.strip()).hostname
    except ValueError:
        return None
    return normalise_domain(host) if host else None


def is_click_address(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return (parts.hostname or "").lower() in _CLICK_HOSTS and parts.path.startswith("/url")


def host_of_display_link(display_link: str) -> str | None:
    text = display_link.strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    for sep in _SEPARATORS:
        text = text.split(sep, 1)[0]
    text = normalise_domain(text)
    return text if "." in text else None


def result_url(item: Mapping[str, Any]) -> str | None:
    """The result's own URL, or ``None`` when only a click address is known."""
    for key in ("link", "url"):
        value = item.get(key)
        if isinstance(value, str) and value and not is_click_address(value):
            return value
    return None


def result_domain(item: Mapping[str, Any]) -> str | None:
    source = item.get("source")
    if isinstance(source, str) and "." in source:
        return normalise_domain(source)
    url = result_url(item)
    if url:
        host = host_of_url(url)
        if host:
            return host
    display = item.get("display_link")
    if isinstance(display, str) and display:
        return host_of_display_link(display)
    return None


def matches(domain: str | None, target: str, *, subdomains: bool = True) -> bool:
    """``blog.example.com`` matches target ``example.com`` unless ``subdomains`` is off."""
    if not domain:
        return False
    domain = normalise_domain(domain)
    target = normalise_domain(target)
    if domain == target:
        return True
    return subdomains and domain.endswith("." + target)
