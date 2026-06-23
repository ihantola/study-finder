"""Configuration for study-finder.

Defaults are sensible for local use; every value can be overridden through an
environment variable (loaded from a ``.env`` file if present).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # read .env if it exists; no-op otherwise

# Field-of-study filter (koodisto URI) for "Tietojenkäsittely ja tietoliikenne
# (ICT)" — level 1, code 06 in the 2016 national classification.
ICT_KOULUTUSALA = "kansallinenkoulutusluokitus2016koulutusalataso1_06"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Config:
    # The real host is opintopolku.fi/konfo-backend — the konfo-backend.* host
    # does not resolve. Treat Swagger as source of truth if this ever changes.
    base_url: str = field(default_factory=lambda: _env("KONFO_BASE_URL", "https://opintopolku.fi/konfo-backend"))
    # Preferred languages, in priority order, for picking multilingual text.
    languages: tuple[str, ...] = field(default_factory=lambda: tuple(_env("KONFO_LANGUAGES", "fi,en,sv").split(",")))
    # Politeness: each live request waits a random delay drawn uniformly from
    # [throttle_min_seconds, throttle_max_seconds]. Set both to 0 to disable.
    throttle_min_seconds: float = field(default_factory=lambda: float(_env("KONFO_THROTTLE_MIN_SECONDS", "2")))
    throttle_max_seconds: float = field(default_factory=lambda: float(_env("KONFO_THROTTLE_MAX_SECONDS", "10")))
    # Generic identification — deliberately NOT a personal email.
    user_agent: str = field(
        default_factory=lambda: _env("KONFO_USER_AGENT", "study-finder/0.1 (+https://github.com/study-finder)")
    )
    caller_id: str = field(default_factory=lambda: _env("KONFO_CALLER_ID", "study-finder"))
    # Where raw API responses are cached and processed output is written.
    cache_dir: Path = field(default_factory=lambda: Path(_env("KONFO_CACHE_DIR", "data/raw")))
    processed_dir: Path = field(default_factory=lambda: Path(_env("KONFO_PROCESSED_DIR", "data/processed")))
    # Retry behaviour for transient failures.
    max_retries: int = field(default_factory=lambda: int(_env("KONFO_MAX_RETRIES", "3")))


DEFAULT_CONFIG = Config()
