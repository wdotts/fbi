from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date as date_cls
from typing import List, Optional, Sequence

import requests

from .releases import Release, parse_release_date

BASE_URL = "https://musicbrainz.org/ws/2/release/"
PAGE_SIZE = 100
RATE_LIMIT_SECONDS = 1.1
DEFAULT_MAX_RESULTS = 500


@dataclass
class SearchOutcome:
    releases: List[Release]
    scanned_count: int


def _user_agent(contact: Optional[str]) -> str:
    contact = contact or "no-contact-configured (set APP_CONTACT_EMAIL)"
    return f"AmazonCDTracker/1.0 ( {contact} )"


def _join_names(credits_list) -> Optional[str]:
    names = []
    for credit in credits_list or []:
        name = credit.get("name")
        if not name and isinstance(credit.get("artist"), dict):
            name = credit["artist"].get("name")
        if name:
            names.append(name)
    return ", ".join(dict.fromkeys(names)) if names else None


def _release_from_result(data: dict) -> Release:
    mbid = data.get("id") or ""
    artist = _join_names(data.get("artist-credit"))
    media = data.get("media") or []
    formats = [m.get("format") for m in media if m.get("format")]
    fmt = ", ".join(dict.fromkeys(formats)) if formats else None
    raw_date = data.get("date")

    return Release(
        source="musicbrainz",
        source_id=mbid,
        title=data.get("title") or "Unknown title",
        artist=artist,
        release_date=parse_release_date(raw_date),
        release_date_text=raw_date,
        format=fmt,
        url=f"https://musicbrainz.org/release/{mbid}" if mbid else None,
        asin=data.get("asin") or None,
    )


def _build_query(since: date_cls, until: date_cls, keywords: Optional[str], formats: Sequence[str]) -> str:
    parts = [f"date:[{since.isoformat()} TO {until.isoformat()}]"]
    if formats:
        fmt_query = " OR ".join(f'format:"{f}"' for f in formats)
        parts.append(f"({fmt_query})")
    if keywords:
        escaped = keywords.replace('"', '\\"')
        parts.append(f'(artist:"{escaped}" OR release:"{escaped}")')
    return " AND ".join(parts)


def search_releases(
    since: date_cls,
    until: date_cls,
    keywords: Optional[str] = None,
    formats: Sequence[str] = ("CD",),
    contact: Optional[str] = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    sleep=time.sleep,
) -> SearchOutcome:
    """Search MusicBrainz for releases with a release date in [since, until],
    optionally narrowed by format and keywords.

    Unlike Amazon's SearchItems, MusicBrainz supports a true server-side
    date range filter and has no fixed results cap, so this pages through
    everything it reports (subject to max_results as a safety cap),
    honoring MusicBrainz's ~1 request/second rate-limit etiquette between
    pages. MusicBrainz's own docs note that a date-range search can also
    surface releases known only to the year or year-month, since it
    doesn't distinguish precision when matching a range - parse_release_date
    only keeps full-precision (YYYY-MM-DD) values, so those show up here
    with release_date=None and get correctly excluded by
    filter_and_sort_releases()'s exact-day filtering.
    """
    query = _build_query(since, until, keywords, formats)
    headers = {"User-Agent": _user_agent(contact), "Accept": "application/json"}

    releases: List[Release] = []
    offset = 0
    while True:
        response = requests.get(
            BASE_URL,
            params={"query": query, "fmt": "json", "limit": PAGE_SIZE, "offset": offset},
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        batch = data.get("releases") or []
        for item in batch:
            releases.append(_release_from_result(item))

        total = data.get("count", len(releases))
        offset += len(batch)
        if not batch or offset >= total or offset >= max_results:
            break
        sleep(RATE_LIMIT_SECONDS)

    return SearchOutcome(releases=releases, scanned_count=len(releases))
