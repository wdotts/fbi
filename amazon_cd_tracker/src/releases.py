from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional


def parse_release_date(raw: Optional[str]) -> Optional[date]:
    """Parse a full YYYY-MM-DD release date.

    Returns None for missing, unparseable, or partial-precision values (a
    bare year like "2026" or a year-month like "2026-08"), since those
    can't be confirmed to fall on - or be excluded from - a specific day.
    Callers that still want to show a partial date should use
    Release.release_date_text / release_date_display() instead.
    """
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


@dataclass
class Release:
    source: str  # "amazon" | "musicbrainz" | "discogs"
    source_id: str  # ASIN / MusicBrainz MBID / Discogs release id
    title: str
    artist: Optional[str] = None
    release_date: Optional[date] = None  # set only when known to day precision
    release_date_text: Optional[str] = None  # raw value, e.g. "2026", "2026-08", or an ISO date
    format: Optional[str] = None
    price_display: Optional[str] = None
    currency: Optional[str] = None
    image_url: Optional[str] = None
    url: Optional[str] = None
    asin: Optional[str] = None  # a real Amazon ASIN, if known, regardless of source

    @property
    def key(self) -> str:
        """Unique identity across sources, e.g. 'amazon:B000TEST' or
        'musicbrainz:1234-5678'. Used to dedupe within a source and to key
        wishlist storage."""
        return f"{self.source}:{self.source_id}"

    def release_date_display(self) -> str:
        if self.release_date:
            return self.release_date.isoformat()
        return self.release_date_text or "Unknown"

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_id": self.source_id,
            "title": self.title,
            "artist": self.artist,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "release_date_text": self.release_date_text,
            "format": self.format,
            "price_display": self.price_display,
            "currency": self.currency,
            "image_url": self.image_url,
            "url": self.url,
            "asin": self.asin,
        }


def filter_and_sort_releases(
    releases: Iterable[Release],
    since: Optional[date] = None,
    until: Optional[date] = None,
    require_date: bool = False,
) -> list[Release]:
    """Keep releases within [since, until] (by exact, day-precision release
    date) and sort newest-first. Releases with no day-precision date are
    dropped when require_date is set, otherwise kept and sorted to the
    end."""
    filtered = []
    for release in releases:
        if release.release_date is None:
            if require_date:
                continue
        else:
            if since and release.release_date < since:
                continue
            if until and release.release_date > until:
                continue
        filtered.append(release)

    def sort_key(release: Release):
        if release.release_date is None:
            return (1, 0)
        return (0, -release.release_date.toordinal())

    return sorted(filtered, key=sort_key)
