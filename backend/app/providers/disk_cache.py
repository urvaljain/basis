"""Persistent response cache — and the source of truth for Demo Mode.

## Why this exists

During development every public Overpass mirror returned HTTP 504 simultaneously, for
several minutes. The in-process cache does not survive a restart, so each run paid three
timeouts before degrading. A cold analysis took 191 seconds and came back without spatial
context at all.

That is not an edge case to guard against — it is the normal condition of free, shared,
unauthenticated infrastructure, and this product is built entirely on it. Two consequences:

1. **Development and evaluation need responses that survive a restart.** Re-fetching the
   same six queries hundreds of times while iterating is slow, rude to the operators, and
   makes evaluation runs non-comparable when the upstream data shifts underneath them.
2. **A live demo cannot depend on Overpass being up.** The brief calls for a Demo Mode that
   works when external APIs fail — and the honest way to build one is not a scripted
   animation but *real responses, captured at a known moment, replayed with their capture
   time shown.*

## The honesty rule

A cached response is labelled as cached, with the timestamp it was captured. Demo Mode says
so in the interface. Every value a viewer sees came from a real call to a real service on a
real date — it is simply not being made again while someone watches.

What this must never become is a fixture file someone hand-edited to make a demo look
better. So fixtures are written only by :func:`capture`, which records the live response
verbatim together with its provenance, and :func:`verify_fixtures` re-checks that the stored
payload still parses through the provider's own parser.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "data" / "fixtures"

# Cached provider responses stay usable for a long time. The underlying data changes slowly
# (OSM features, terrain, historical climate), and a stale-but-labelled response is far more
# useful than a failed request — provided the label is honest.
DEFAULT_MAX_AGE_DAYS = 30


@dataclass
class CachedResponse:
    """A stored provider response with the provenance needed to trust it."""

    provider: str
    endpoint: str
    query: dict[str, Any]
    payload: Any
    captured_at: str
    key: str

    @property
    def age_days(self) -> float:
        captured = datetime.fromisoformat(self.captured_at)
        return (datetime.now(timezone.utc) - captured).total_seconds() / 86400

    @property
    def is_stale(self) -> bool:
        return self.age_days > DEFAULT_MAX_AGE_DAYS

    def provenance_note(self) -> str:
        """What the interface shows beside a replayed value."""
        return (
            f"Captured from {self.provider} on "
            f"{datetime.fromisoformat(self.captured_at):%d %b %Y at %H:%M UTC} "
            f"({self.age_days:.0f} days ago). This is a real recorded response, replayed "
            f"rather than re-fetched."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "endpoint": self.endpoint,
            "query": self.query,
            "captured_at": self.captured_at,
            "key": self.key,
            "payload": self.payload,
        }


def _path_for(key: str) -> Path:
    return FIXTURE_DIR / f"{key}.json"


def load(key: str) -> CachedResponse | None:
    """Load a stored response, or None."""
    path = _path_for(key)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return CachedResponse(
            provider=raw["provider"],
            endpoint=raw["endpoint"],
            query=raw["query"],
            payload=raw["payload"],
            captured_at=raw["captured_at"],
            key=raw["key"],
        )
    except Exception:  # noqa: BLE001 - a corrupt fixture must not break a request path
        logger.exception("failed to read fixture %s", path)
        return None


def store(key: str, provider: str, endpoint: str, query: dict[str, Any], payload: Any) -> None:
    """Persist a live response verbatim.

    Called only on a successful live fetch. Nothing else writes fixtures, which is what
    keeps them honest: a fixture is a recording, never an authored artefact.
    """
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    record = CachedResponse(
        provider=provider,
        endpoint=endpoint,
        query=query,
        payload=payload,
        captured_at=datetime.now(timezone.utc).isoformat(),
        key=key,
    )
    try:
        _path_for(key).write_text(
            json.dumps(record.to_dict(), indent=2, default=str), encoding="utf-8"
        )
        logger.info("captured fixture %s for %s", key, provider)
    except Exception:  # noqa: BLE001
        logger.exception("failed to write fixture %s", key)


def list_fixtures() -> list[CachedResponse]:
    if not FIXTURE_DIR.exists():
        return []
    out = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        if loaded := load(path.stem):
            out.append(loaded)
    return out


def summary() -> dict[str, Any]:
    """Provenance summary for the Demo Mode banner and the admin view."""
    fixtures = list_fixtures()
    if not fixtures:
        return {"count": 0, "providers": [], "oldest_days": None, "any_stale": False}
    return {
        "count": len(fixtures),
        "providers": sorted({f.provider for f in fixtures}),
        "oldest_days": round(max(f.age_days for f in fixtures), 1),
        "newest_days": round(min(f.age_days for f in fixtures), 1),
        "any_stale": any(f.is_stale for f in fixtures),
        "captured": [
            {"provider": f.provider, "captured_at": f.captured_at, "key": f.key}
            for f in fixtures
        ],
    }


def verify_fixtures(parsers: dict[str, Any]) -> list[str]:
    """Re-parse every fixture through its provider's own parser.

    Guards against a fixture that has silently stopped matching the shape the code expects —
    which would make Demo Mode break in front of an audience, the one moment it exists to
    prevent.
    """
    problems: list[str] = []
    for fixture in list_fixtures():
        parser = parsers.get(fixture.provider)
        if parser is None:
            problems.append(f"{fixture.key}: no parser registered for {fixture.provider}")
            continue
        try:
            parser(fixture.payload, **fixture.query)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{fixture.key}: does not parse — {type(e).__name__}: {e}")
    return problems
