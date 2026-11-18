"""Track a domain's search positions with the QuanticData SERP API and keep the history in SQLite."""

from ._version import __version__
from .api import (
    AuthenticationError,
    InputError,
    PaymentRequiredError,
    QuanticDataClient,
    QuanticDataError,
    RateLimitError,
)
from .domains import matches, normalise_domain, result_domain
from .export import write_rows
from .models import COLUMNS, Check, SearchSettings, check_from_payload
from .store import Movement, Store
from .tracker import Tracker, read_keywords

__all__ = [
    "COLUMNS",
    "AuthenticationError",
    "Check",
    "InputError",
    "Movement",
    "PaymentRequiredError",
    "QuanticDataClient",
    "QuanticDataError",
    "RateLimitError",
    "SearchSettings",
    "Store",
    "Tracker",
    "__version__",
    "check_from_payload",
    "matches",
    "normalise_domain",
    "read_keywords",
    "result_domain",
    "write_rows",
]
