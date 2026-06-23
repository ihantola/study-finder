"""Polite HTTP client for the konfo-backend API.

Responsibilities:
- send a generic ``User-Agent`` / ``Caller-Id`` (no personal email),
- throttle between live requests with a random delay (configurable range),
- retry transient failures (429 / 5xx) with exponential backoff,
- cache raw JSON responses on disk so repeated runs do not re-hit the API.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from .config import DEFAULT_CONFIG, Config

logger = logging.getLogger("study_finder.client")

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class KonfoClient:
    """Thin, well-behaved wrapper around ``requests.Session``."""

    def __init__(self, config: Config = DEFAULT_CONFIG, use_cache: bool = True):
        self.config = config
        self.use_cache = use_cache
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.user_agent,
                "Caller-Id": config.caller_id,
                "Accept": "application/json",
            }
        )
        self._last_request_ts = 0.0
        if use_cache:
            config.cache_dir.mkdir(parents=True, exist_ok=True)

    # -- caching ---------------------------------------------------------
    def _cache_path(self, path: str, params: dict[str, Any] | None) -> Path:
        key = path + ("?" + urlencode(sorted((params or {}).items())) if params else "")
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        # keep a human-readable prefix (last path segment) for easy browsing
        slug = path.strip("/").replace("/", "_") or "root"
        return self.config.cache_dir / f"{slug}_{digest}.json"

    # -- throttling ------------------------------------------------------
    def _delay_seconds(self) -> float:
        """A random per-request delay drawn from the configured range."""
        lo = max(self.config.throttle_min_seconds, 0.0)
        hi = max(self.config.throttle_max_seconds, lo)
        return random.uniform(lo, hi) if hi > lo else lo

    def _throttle(self) -> None:
        target = self._delay_seconds()
        elapsed = time.monotonic() - self._last_request_ts
        wait = target - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    # -- requests --------------------------------------------------------
    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET ``path`` (relative to base_url) and return parsed JSON.

        Reads from the on-disk cache when available; otherwise fetches, then
        stores the response before returning it.
        """
        cache_path = self._cache_path(path, params)
        if self.use_cache and cache_path.exists():
            logger.debug("cache hit %s", cache_path.name)
            return json.loads(cache_path.read_text(encoding="utf-8"))

        url = f"{self.config.base_url}/{path.lstrip('/')}"
        data = self._get_with_retries(url, params)

        if self.use_cache:
            cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def _get_with_retries(self, url: str, params: dict[str, Any] | None) -> Any:
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:  # network error
                last_exc = exc
                logger.warning("request error (attempt %d/%d): %s", attempt, self.config.max_retries, exc)
            else:
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code not in _RETRYABLE_STATUS:
                    resp.raise_for_status()
                last_exc = requests.HTTPError(f"{resp.status_code} for {url}")
                logger.warning(
                    "retryable status %s (attempt %d/%d)", resp.status_code, attempt, self.config.max_retries
                )

            if attempt < self.config.max_retries:
                time.sleep(2 ** (attempt - 1))  # 1s, 2s, 4s, ...
        raise RuntimeError(f"GET failed after {self.config.max_retries} attempts: {url}") from last_exc
