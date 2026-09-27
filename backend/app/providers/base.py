"""Provider abstraction: a value may not be returned without what is wrong with it.

Every external data source sits behind :class:`Provider`. The abstraction exists for the
usual reasons — retries, mirrors, caching, one place to change an endpoint — but its real
job is narrower and more important:

**A provider cannot hand back a measurement without also handing back its limitation.**

:class:`ProviderResult` carries a ``limitation`` field that is required, not optional, and it
flows into ``DatasetLocator.limitation`` on the epistemic layer, which the UI renders beside
the value. Nothing downstream can strip it. That matters because the most damaging numbers in
this product are not the wrong ones — they are the right ones presented without their
resolution. ERA5 returns real rainfall, for a grid cell 4.71 km from the site. SRTM returns
real elevation, at a 30 m posting that cannot see a plot. Both are useful. Both mislead when
displayed bare.

Failures are values too. A provider that cannot reach its source returns a
:class:`ProviderResult` with ``ok=False`` and a reason, never an exception that a caller might
swallow into a blank panel. "Data unavailable, here is what I tried" is a product state with
a design; a silent empty panel is an accident the user has to interpret.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

import certifi
import httpx

from app.providers import disk_cache

logger = logging.getLogger(__name__)


def _ssl_context() -> Any:
    """Build an SSL context with a CA bundle that actually resolves.

    On Windows, httpx does not pick up the OS certificate store, so verification fails with
    CERTIFICATE_VERIFY_FAILED against perfectly valid endpoints. Preference order:

    1. ``truststore`` — uses the operating system's own trust store, which is correct in
       corporate environments with an inspecting proxy.
    2. ``certifi`` — the portable Mozilla bundle.

    Verification is never disabled. Every source here is public data over the open internet,
    and a product whose entire argument is provenance has no business accepting unverified
    TLS to fetch the evidence it cites.
    """
    try:
        import ssl

        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # noqa: BLE001 - fall back to the portable bundle
        return certifi.where()

T = TypeVar("T")

# Rate limiting is PER PROVIDER, not global. A single global lock was the first
# implementation and it made the three site providers — which are fetched with
# asyncio.gather and hit three unrelated services — serialise behind each other, turning a
# parallel fan-out into a sequential one. Each service publishes its own policy; respecting
# Nominatim's 1 req/s by also throttling OpenTopoData helps nobody.
_DEFAULT_RATE_LIMIT_SECONDS = 0.0
_last_request_at: dict[str, float] = {}
_rate_locks: dict[str, asyncio.Lock] = {}

USER_AGENT = "basis/0.1 (+https://github.com/urvaljain/basis; urvaljain@gmail.com)"


@dataclass
class ProviderResult(Generic[T]):
    """A value, its provenance, and its limits — or an honest failure."""

    provider: str
    endpoint: str
    ok: bool
    retrieved_at: datetime
    query: dict[str, Any] = field(default_factory=dict)

    data: T | None = None
    limitation: str = ""
    """What is wrong with this value even when it is correct. Required on success."""

    licence: str | None = None
    attribution: str | None = None

    # Failure detail
    error: str | None = None
    attempts: list[str] = field(default_factory=list)

    cached: bool = False
    latency_ms: int = 0

    @property
    def failed(self) -> bool:
        return not self.ok

    def unavailable_message(self) -> str:
        """User-facing explanation of a failure.

        Deliberately states what was tried. "Zoning intelligence unavailable" invites the
        reader to assume the system did not look; naming the endpoints and the errors shows
        that it did and that the gap is real.
        """
        tried = f" Attempted: {'; '.join(self.attempts)}." if self.attempts else ""
        return (
            f"{self.provider} data is unavailable for this location. "
            f"Reason: {self.error or 'unknown'}.{tried}"
        )


class ProviderError(Exception):
    """Raised only inside a provider; never escapes ``fetch``."""


class _Cache:
    """Small in-process TTL cache.

    Deliberately not Redis. A single-process prototype querying free public APIs needs
    request coalescing and demo resilience, not a cache tier — and an unnecessary service is
    a deployment dependency that can fail during the demo it was meant to protect.
    """

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 512) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store: dict[str, tuple[float, Any]] = {}

    @staticmethod
    def key(provider: str, query: dict[str, Any]) -> str:
        blob = json.dumps({"p": provider, "q": query}, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:24]

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.time() - stored_at > self.ttl:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self.max_entries:
            oldest = min(self._store.items(), key=lambda kv: kv[1][0])[0]
            self._store.pop(oldest, None)
        self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()


CACHE = _Cache()


async def _respect_rate_limit(provider: str, min_interval: float) -> None:
    """Throttle one provider without blocking any other."""
    if min_interval <= 0:
        return
    lock = _rate_locks.setdefault(provider, asyncio.Lock())
    async with lock:
        elapsed = time.monotonic() - _last_request_at.get(provider, 0.0)
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        _last_request_at[provider] = time.monotonic()


class Provider(ABC, Generic[T]):
    """Base class for an external data source."""

    name: str
    licence: str | None = None
    attribution: str | None = None

    #: Mirrors tried in order. Public Overpass instances return 504 under load — observed
    #: on the first scripted run during Phase 0 — so fallback is standard, not defensive.
    endpoints: tuple[str, ...] = ()

    #: Attempts per endpoint before moving to the next. Kept low: when a public mirror is
    #: returning 504 it is usually overloaded, and a second mirror answers far sooner than a
    #: third retry against the first one.
    max_attempts_per_endpoint: int = 1
    timeout_seconds: float = 30.0
    cache_ttl_seconds: int = 3600

    #: Minimum seconds between calls to THIS provider. Only Nominatim publishes a hard
    #: limit (1 req/s); the rest are left unthrottled and rely on caching for politeness.
    min_request_interval_seconds: float = _DEFAULT_RATE_LIMIT_SECONDS

    #: Backoff before retrying the same endpoint.
    retry_backoff_seconds: float = 0.8

    #: Persist successful responses to disk so they survive a restart and can back Demo
    #: Mode. Every stored response is a verbatim recording, never an authored fixture.
    persist_to_disk: bool = True

    #: Serve a recorded response when every endpoint fails. This turns a total upstream
    #: outage — all three Overpass mirrors returning 504 simultaneously, which happened
    #: repeatedly during development — from "no spatial context at all" into "spatial
    #: context from a recording, labelled with its capture time".
    allow_stale_on_failure: bool = True

    @abstractmethod
    def build_request(self, endpoint: str, **kwargs: Any) -> httpx.Request:
        """Construct the HTTP request for one endpoint."""

    @abstractmethod
    def parse(self, payload: Any, **kwargs: Any) -> T:
        """Turn a raw response into the provider's domain type.

        Raise :class:`ProviderError` when the payload is well-formed but unusable — an
        empty geocoding result, for instance. That is a data absence, not a transport
        failure, and the two should not be conflated in what the user is told.
        """

    @abstractmethod
    def limitation_for(self, data: T, **kwargs: Any) -> str:
        """The honest caveat for this value. Required — there is no 'no limitation'.

        Every source in this product has one. If a provider genuinely had none, saying so
        explicitly is still better than silence, because the user learns the field is always
        populated and therefore always worth reading.
        """

    async def fetch(self, *, use_cache: bool = True, **kwargs: Any) -> ProviderResult[T]:
        """Fetch with mirror fallback, retries, rate limiting and caching.

        Never raises. A failure is returned as a result so the caller renders a designed
        empty state rather than discovering an exception at the edge of the request.
        """
        started = time.monotonic()
        cache_key = _Cache.key(self.name, kwargs)
        disk_key = f"{self.name}-{cache_key}"

        if use_cache:
            hit = CACHE.get(cache_key)
            if hit is not None:
                return ProviderResult(
                    provider=self.name,
                    endpoint="(cache)",
                    ok=True,
                    retrieved_at=hit["retrieved_at"],
                    query=kwargs,
                    data=hit["data"],
                    limitation=hit["limitation"],
                    licence=self.licence,
                    attribution=self.attribution,
                    cached=True,
                    latency_ms=int((time.monotonic() - started) * 1000),
                )

        # Disk cache: survives restarts, and is what Demo Mode replays.
        if use_cache and self.persist_to_disk:
            stored = disk_cache.load(disk_key)
            if stored is not None and not stored.is_stale:
                replayed = self._from_recording(stored, kwargs, started, live_failed=False)
                if replayed is not None:
                    return replayed

        attempts: list[str] = []
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": USER_AGENT},
            verify=_ssl_context(),
            follow_redirects=True,
        ) as client:
            for endpoint in self.endpoints:
                for attempt in range(self.max_attempts_per_endpoint):
                    try:
                        await _respect_rate_limit(
                            self.name, self.min_request_interval_seconds
                        )
                        request = self.build_request(endpoint, **kwargs)

                        # An httpx.Request constructed standalone does NOT inherit the
                        # client's default headers — those are merged only by the client's
                        # own request methods, not by `send()`. So requests were leaving
                        # with httpx's default User-Agent, which Nominatim rejects outright
                        # (HTTP 403) and Overpass rejects as Not Acceptable (HTTP 406).
                        # Both refusals are correct: these are free services whose usage
                        # policies require identifying yourself.
                        request.headers["User-Agent"] = USER_AGENT
                        request.headers.setdefault("Accept", "application/json")

                        response = await client.send(request)
                        response.raise_for_status()

                        # Overpass signals slot exhaustion with an HTTP 200 carrying an
                        # HTML body ("Too Many Requests" / "slot available after ..."),
                        # which surfaces as a JSONDecodeError several layers away and looks
                        # like a parsing bug rather than the rate limit it is. Detect it
                        # here so the reported reason is the true one.
                        content_type = response.headers.get("content-type", "")
                        if content_type.startswith("application/json"):
                            payload = response.json()
                        elif "html" in content_type or response.text.lstrip().startswith("<"):
                            snippet = " ".join(response.text.split())[:160]
                            raise RuntimeError(
                                f"expected JSON, received {content_type or 'HTML'} — "
                                f"usually rate limiting or slot exhaustion: {snippet}"
                            )
                        else:
                            payload = response.text
                        data = self.parse(payload, **kwargs)
                        limitation = self.limitation_for(data, **kwargs)
                        retrieved_at = datetime.now(timezone.utc)

                        if self.persist_to_disk:
                            disk_cache.store(
                                disk_key, self.name, endpoint, kwargs, payload
                            )

                        if use_cache:
                            CACHE.set(
                                cache_key,
                                {
                                    "data": data,
                                    "limitation": limitation,
                                    "retrieved_at": retrieved_at,
                                },
                            )

                        attempts.append(f"{endpoint} -> OK")
                        return ProviderResult(
                            provider=self.name,
                            endpoint=endpoint,
                            ok=True,
                            retrieved_at=retrieved_at,
                            query=kwargs,
                            data=data,
                            limitation=limitation,
                            licence=self.licence,
                            attribution=self.attribution,
                            attempts=attempts,
                            latency_ms=int((time.monotonic() - started) * 1000),
                        )

                    except ProviderError as e:
                        # Well-formed response, no usable data. Retrying will not help and
                        # a different mirror serves the same data, so stop here.
                        attempts.append(f"{endpoint} -> no data: {e}")
                        return ProviderResult(
                            provider=self.name,
                            endpoint=endpoint,
                            ok=False,
                            retrieved_at=datetime.now(timezone.utc),
                            query=kwargs,
                            error=str(e),
                            attempts=attempts,
                            latency_ms=int((time.monotonic() - started) * 1000),
                        )

                    except Exception as e:  # noqa: BLE001 - transport failures are expected
                        label = f"{type(e).__name__}: {str(e)[:90]}"
                        attempts.append(f"{endpoint} -> {label}")
                        logger.warning("%s attempt %d failed: %s", endpoint, attempt + 1, label)
                        await asyncio.sleep(self.retry_backoff_seconds * (attempt + 1))

        # Every endpoint failed. A recorded response, clearly labelled as one, beats an
        # empty panel: the user gets real data and is told exactly how old it is and that
        # the live fetch failed.
        if self.allow_stale_on_failure and self.persist_to_disk:
            stored = disk_cache.load(disk_key)
            if stored is not None:
                replayed = self._from_recording(stored, kwargs, started, live_failed=True)
                if replayed is not None:
                    replayed.attempts = attempts
                    return replayed

        return ProviderResult(
            provider=self.name,
            endpoint=self.endpoints[0] if self.endpoints else "",
            ok=False,
            retrieved_at=datetime.now(timezone.utc),
            query=kwargs,
            error="all endpoints failed",
            attempts=attempts,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    def _from_recording(
        self,
        stored: disk_cache.CachedResponse,
        kwargs: dict[str, Any],
        started: float,
        *,
        live_failed: bool,
    ) -> ProviderResult[T] | None:
        """Rebuild a result from a recorded response, or None if it no longer parses.

        The capture time and the fact of replay are folded into ``limitation``, which the
        UI always renders. A replayed value is never presented as a fresh one.
        """
        try:
            data = self.parse(stored.payload, **kwargs)
        except Exception:  # noqa: BLE001 - a recording that no longer parses is not usable
            logger.warning("recorded response %s no longer parses", stored.key)
            return None

        prefix = "LIVE FETCH FAILED — " if live_failed else ""
        return ProviderResult(
            provider=self.name,
            endpoint="(recorded — live fetch failed)" if live_failed else "(recorded)",
            ok=True,
            retrieved_at=datetime.fromisoformat(stored.captured_at),
            query=kwargs,
            data=data,
            limitation=f"{self.limitation_for(data, **kwargs)} {prefix}{stored.provenance_note()}",
            licence=self.licence,
            attribution=self.attribution,
            cached=True,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
