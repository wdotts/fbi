from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional, Sequence

from . import amazon_client, discogs_client, musicbrainz_client
from .config import AppConfig, ConfigError, require_amazon
from .releases import Release, filter_and_sort_releases

ALL_SOURCES = ("musicbrainz", "discogs", "amazon")
DEFAULT_SOURCES = ("musicbrainz",)

# Used only to build a bounded MusicBrainz/Discogs date-range query when the
# caller leaves "until" open-ended (e.g. "everything from the last 60 days
# onward, including near-future pre-orders").
_FAR_FUTURE = date.today() + timedelta(days=730)


@dataclass
class SearchResult:
    releases: List[Release]
    notes: List[str] = field(default_factory=list)


def parse_sources(raw: Optional[str]) -> List[str]:
    if not raw:
        return list(DEFAULT_SOURCES)
    sources = [s.strip().lower() for s in raw.split(",") if s.strip()]
    unknown = [s for s in sources if s not in ALL_SOURCES]
    if unknown:
        raise ValueError(f"Unknown source(s): {', '.join(unknown)}. Valid: {', '.join(ALL_SOURCES)}.")
    return sources or list(DEFAULT_SOURCES)


def search(
    config: AppConfig,
    sources: Sequence[str],
    since: date,
    until: Optional[date] = None,
    keywords: Optional[str] = None,
    formats: Sequence[str] = ("CD",),
    require_date: bool = False,
    amazon_search_index: str = "Music",
    amazon_browse_node_id: Optional[str] = None,
    amazon_pages: int = 3,
    amazon_min_price: Optional[int] = None,
    amazon_max_price: Optional[int] = None,
    musicbrainz_max_results: int = musicbrainz_client.DEFAULT_MAX_RESULTS,
    discogs_max_candidates: int = 30,
    discogs_fetch_details: bool = True,
) -> SearchResult:
    releases: List[Release] = []
    notes: List[str] = []
    range_until = until or _FAR_FUTURE

    if "musicbrainz" in sources:
        if not config.musicbrainz_contact:
            notes.append(
                "MusicBrainz: no APP_CONTACT_EMAIL set in .env; using a generic "
                "User-Agent. MusicBrainz asks automated clients to identify "
                "themselves - set it for a more polite/robust client."
            )
        outcome = musicbrainz_client.search_releases(
            since=since,
            until=range_until,
            keywords=keywords,
            formats=formats,
            contact=config.musicbrainz_contact,
            max_results=musicbrainz_max_results,
        )
        releases.extend(outcome.releases)
        notes.append(f"MusicBrainz: scanned {outcome.scanned_count} candidate listing(s).")
        if outcome.scanned_count >= musicbrainz_max_results:
            notes.append(
                "MusicBrainz: hit the max-results safety cap "
                f"({musicbrainz_max_results}); raise --musicbrainz-max-results "
                "for a wider (slower) scan if this range is very large."
            )

    if "discogs" in sources:
        outcome = discogs_client.search_releases(
            since=since,
            until=range_until,
            keywords=keywords,
            formats=formats,
            token=config.discogs_token,
            max_candidates=discogs_max_candidates,
            fetch_details=discogs_fetch_details,
        )
        releases.extend(outcome.releases)
        if discogs_fetch_details:
            notes.append(
                f"Discogs: checked {outcome.candidates_checked} candidate(s) "
                f"({outcome.detail_fetches} detail lookup(s)) for an exact date "
                "match; Discogs search only reports release year, so this is "
                "capped and may miss items beyond the candidate list."
            )
        else:
            notes.append(
                f"Discogs: {outcome.candidates_checked} year/format match(es), "
                "not confirmed against the exact date (--no-discogs-details)."
            )

    if "amazon" in sources:
        try:
            amazon_config = require_amazon(config)
        except ConfigError as exc:
            notes.append(f"Amazon: skipped - {exc}")
        else:
            outcome = amazon_client.search_new_releases(
                amazon_config,
                keywords=keywords,
                search_index=amazon_search_index,
                browse_node_id=amazon_browse_node_id,
                pages=amazon_pages,
                min_price=amazon_min_price,
                max_price=amazon_max_price,
            )
            releases.extend(outcome.releases)
            notes.append(
                f"Amazon: scanned {outcome.scanned_count} catalog listing(s) "
                f"across {outcome.pages_fetched} page(s) (100-result API cap)."
            )
            if outcome.scanned_count >= 100:
                notes.append(
                    "Amazon: hit its 100-result search cap; older dates may be "
                    "incomplete there. MusicBrainz doesn't have this limit."
                )

    filtered = filter_and_sort_releases(releases, since=since, until=until, require_date=require_date)
    return SearchResult(releases=filtered, notes=notes)
