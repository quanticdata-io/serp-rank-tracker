"""Runs the searches for a list of keywords and turns each answer into a :class:`Check`."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from .api import InputError, QuanticDataClient, QuanticDataError
from .domains import normalise_domain
from .models import Check, SearchSettings, check_from_payload


@dataclass
class Failure:
    keyword: str
    error: QuanticDataError


def read_keywords(lines: Iterable[str]) -> list[str]:
    """One keyword per line; blank lines and ``#`` comments are skipped; duplicates removed."""
    seen: dict[str, None] = {}
    for raw in lines:
        line = raw.strip()
        if line and not line.startswith("#"):
            seen.setdefault(line, None)
    return list(seen)


class Tracker:
    def __init__(
        self,
        client: QuanticDataClient,
        domain: str,
        settings: SearchSettings | None = None,
        *,
        subdomains: bool = True,
        delay: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.domain = normalise_domain(domain)
        if "." not in self.domain:
            raise ValueError(f"Not a domain: {domain!r}")
        self.settings = settings or SearchSettings()
        self.subdomains = subdomains
        self.delay = delay
        self._sleep = sleep
        self.failures: list[Failure] = []

    def check(self, keyword: str) -> Check:
        payload = self.client.search(self.settings.params(keyword))
        return check_from_payload(
            payload,
            keyword=keyword,
            domain=self.domain,
            settings=self.settings,
            subdomains=self.subdomains,
        )

    def run(self, keywords: Iterable[str]) -> Iterator[Check]:
        """Checks each keyword in turn. A failed keyword is recorded in ``failures``
        and skipped; an input error (HTTP 400) stops the run, since every keyword
        would fail the same way."""
        for index, keyword in enumerate(keywords):
            if index and self.delay:
                self._sleep(self.delay)
            try:
                yield self.check(keyword)
            except InputError:
                raise
            except QuanticDataError as exc:
                if exc.status in (401, 402):
                    raise
                self.failures.append(Failure(keyword, exc))
