from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date as date_cls
from typing import List, Optional, Sequence, Tuple

import requests

from .releases import Release, parse_release_date

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.discogs.com/database/search"
USER_AGENT = "AmazonCDTracker/1.0 (+https://github.com/)"

# Discogs throttles by source IP: ~60/min with a registered token, ~25/min
# without one. These intervals self-throttle our own detail-fetch loop to
# stay comfortably under either limit.
AUTHED_INTERVAL_SECONDS = 1.1
UNAUTHED_INTERVAL_SECONDS = 2.6


@dataclass
class SearchOutcome:
    releases: List[Release]
    candidates_checked: int
    detail_fetches: int


def _headers(token: Optional[str]) -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Discogs token={token}"
    return headers


def _title_to_artist_title(raw_title: str) -> Tuple[Optional[str], str]:
    # Discogs search result titles are conventionally "Artist - Title".
    if " - " in raw_title:
        artist, _, title = raw_title.partition(" - ")
        return artist.strip() or None, title.strip() or raw_title
    return None, raw_title


def _release_from_search_result(data: dict) -> Release:
    artist, title = _title_to_artist_title(data.get("title") or "Unknown title")
    formats = data.get("format") or []
    fmt = ", ".join(dict.fromkeys(formats)) if formats else None
    year = data.get("year")
    release_id = str(data.get("id") or "")
    uri = data.get("uri")
    url = f"https://www.discogs.com{uri}" if uri else None

    return Release(
        source="discogs",
        source_id=release_id,
        title=title,
        artist=artist,
        release_date=None,
        release_date_text=str(year) if year else None,
        format=fmt,
        image_url=data.get("cover_image") or data.get("thumb") or None,
        url=url,
    )


def search_releases(
    since: date_cls,
    until: date_cls,
    keywords: Optional[str] = None,
    formats: Sequence[str] = ("CD",),
    token: Optional[str] = None,
    max_candidates: int = 30,
    fetch_details: bool = True,
    sleep=time.sleep,
) -> SearchOutcome:
    """Search Discogs for releases, narrowed by year (Discogs' search API
    only supports year-level date filtering, not exact days) and format.

    Discogs release *search* results only carry a release year, not a full
    date. When fetch_details is True, this fetches each candidate's full
    release page (one extra HTTP request per candidate, up to
    max_candidates) to read its precise `released` field and confirm it
    actually falls in [since, until]. That's slow and rate-limit-hungry,
    hence the small default cap - treat Discogs as a secondary/enrichment
    source (it's also a real marketplace with pricing), not the primary
    way to get an exhaustive day-by-day list. Use MusicBrainz for that.
    """
    headers = _headers(token)
    interval = AUTHED_INTERVAL_SECONDS if token else UNAUTHED_INTERVAL_SECONDS

    params: dict = {"type": "release", "per_page": max_candidates}
    if formats:
        params["format"] = formats[0]
    if keywords:
        params["q"] = keywords
    if since.year == until.year:
        params["year"] = since.year

    response = requests.get(SEARCH_URL, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    results = (response.json() or {}).get("results") or []
    results = results[:max_candidates]
    candidates = [_release_from_search_result(r) for r in results]

    if not fetch_details:
        return SearchOutcome(releases=candidates, candidates_checked=len(candidates), detail_fetches=0)

    matched: List[Release] = []
    detail_fetches = 0
    for i, (release, raw) in enumerate(zip(candidates, results)):
        resource_url = raw.get("resource_url")
        if not resource_url:
            continue
        if detail_fetches:
            sleep(interval)
        try:
            detail_response = requests.get(resource_url, headers=headers, timeout=15)
            detail_response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Discogs detail fetch failed for %s: %s", resource_url, exc)
            continue
        detail_fetches += 1
        detail = detail_response.json() or {}
        raw_release_date = detail.get("released")
        release.release_date = parse_release_date(raw_release_date)
        release.release_date_text = raw_release_date or release.release_date_text
        if release.release_date and since <= release.release_date <= until:
            matched.append(release)

    return SearchOutcome(
        releases=matched, candidates_checked=len(candidates), detail_fetches=detail_fetches
    )
