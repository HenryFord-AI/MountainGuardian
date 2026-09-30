"""
MountainGuardian G03A – short-term raw weather response cache.

Frozen design (doc 04 §35): raw Open-Meteo responses may be reused for
30 minutes so repeated scans / demo clicks do not hammer the provider.
The ORIGINAL retrieval time travels with the cached payload and is never
rewritten: cached data must never be presented as newly retrieved data.

Cache content is runtime data (data/runtime/...), never committed to Git.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

CACHE_TTL_SECONDS = 30 * 60  # frozen recommendation: 30 minutes


@dataclass(frozen=True)
class CachedResponse:
    payload: dict[str, Any]
    original_retrieval_time: str   # ISO-8601 UTC of the ORIGINAL retrieval
    retrieved_at_epoch: float      # epoch seconds of the ORIGINAL retrieval
    cache_age_seconds: float       # age of the cached entry at read time
    cached: bool = True


class WeatherRawCache:
    """File-backed raw response cache with honest retrieval-time metadata."""

    def __init__(
        self,
        cache_dir: Path,
        ttl_seconds: float = CACHE_TTL_SECONDS,
        clock: "Callable[[], float] | None" = None,
    ):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = float(ttl_seconds)
        self._clock = clock or time.time

    # -- keying ------------------------------------------------------------
    @staticmethod
    def key_for(endpoint: str, params: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"endpoint": endpoint, "params": params}, sort_keys=True, ensure_ascii=True
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    # -- API ---------------------------------------------------------------
    def get(self, endpoint: str, params: dict[str, Any]) -> CachedResponse | None:
        path = self._path(self.key_for(endpoint, params))
        if not path.is_file():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            payload = entry["payload"]
            retrieved_at_epoch = float(entry["retrieved_at_epoch"])
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            return None  # corrupt cache entry: treat as miss, never crash a scan
        age = self._clock() - retrieved_at_epoch
        if age > self.ttl_seconds:
            return None  # expired: caller must re-retrieve
        return CachedResponse(
            payload=payload,
            original_retrieval_time=str(entry["retrieval_time"]),
            retrieved_at_epoch=retrieved_at_epoch,
            cache_age_seconds=age,
        )

    def put(
        self,
        endpoint: str,
        params: dict[str, Any],
        payload: dict[str, Any],
        retrieval_time: str,
        retrieved_at_epoch: float | None = None,
    ) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "endpoint": endpoint,
            "params": params,
            "payload": payload,
            "retrieval_time": retrieval_time,
            "retrieved_at_epoch": (
                self._clock() if retrieved_at_epoch is None else float(retrieved_at_epoch)
            ),
            "cache_ttl_seconds": self.ttl_seconds,
            "note": (
                "Raw provider response cache. retrieval_time is the ORIGINAL "
                "retrieval time; reuse within the TTL must not be presented as "
                "a fresh retrieval."
            ),
        }
        path = self._path(self.key_for(endpoint, params))
        path.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def clear(self) -> None:
        if self.cache_dir.is_dir():
            for path in self.cache_dir.glob("*.json"):
                path.unlink(missing_ok=True)
