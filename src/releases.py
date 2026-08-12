from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional

_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m", "%Y")


def parse_release_date(raw: Optional[str]) -> Optional[date]:
    """Parse Amazon's ReleaseDate string, which may be a full date, a
    year-month, or just a year, depending on how complete the catalog
    listing is."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class Release:
    asin: str
    title: str
    artist: Optional[str]
    release_date: Optional[date]
    price_display: Optional[str]
    currency: Optional[str]
    image_url: Optional[str]
    url: Optional[str]

    def release_date_display(self) -> str:
        return self.release_date.isoformat() if self.release_date else "Unknown"

    def to_dict(self) -> dict:
        return {
            "asin": self.asin,
            "title": self.title,
            "artist": self.artist,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "price_display": self.price_display,
            "currency": self.currency,
            "image_url": self.image_url,
            "url": self.url,
        }


def _attr(obj, *names):
    for name in names:
        obj = getattr(obj, name, None)
        if obj is None:
            return None
    return obj


def release_from_item(item) -> Release:
    """Convert an Amazon Creators API `Item` (from search_items) into a
    plain Release. Every lookup is defensive since Amazon only returns
    the resources it actually has data for."""
    item_info = getattr(item, "item_info", None)
    title = _attr(item_info, "title", "display_value") or "Unknown title"

    by_line = getattr(item_info, "by_line_info", None)
    contributors = getattr(by_line, "contributors", None) or []
    artist_names = [c.name for c in contributors if getattr(c, "name", None)]
    if artist_names:
        artist = ", ".join(dict.fromkeys(artist_names))
    else:
        artist = _attr(by_line, "brand", "display_value")

    raw_release_date = _attr(item_info, "product_info", "release_date", "display_value")
    release_date = parse_release_date(raw_release_date)

    price_display = None
    currency = None
    offers = getattr(item, "offers_v2", None)
    listings = getattr(offers, "listings", None) or []
    if listings:
        money = _attr(listings[0], "price", "money")
        price_display = getattr(money, "display_amount", None)
        currency = getattr(money, "currency", None)

    image_url = _attr(item, "images", "primary", "medium", "url")

    return Release(
        asin=getattr(item, "asin", "") or "",
        title=title,
        artist=artist,
        release_date=release_date,
        price_display=price_display,
        currency=currency,
        image_url=image_url,
        url=getattr(item, "detail_page_url", None),
    )


def filter_and_sort_releases(
    releases: Iterable[Release],
    since: Optional[date] = None,
    until: Optional[date] = None,
    require_date: bool = False,
) -> list[Release]:
    """Keep releases within [since, until] and sort newest-first. Items
    with no known release date are dropped when require_date is set,
    otherwise kept and sorted to the end."""
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
