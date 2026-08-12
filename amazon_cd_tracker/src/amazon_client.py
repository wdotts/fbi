from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from amazon_creatorsapi import AmazonCreatorsApi
from amazon_creatorsapi.errors import ItemsNotFoundError, TooManyRequestsError
from amazon_creatorsapi.models import SearchItemsResource, SortBy

from .config import AmazonConfig
from .releases import Release, parse_release_date

logger = logging.getLogger(__name__)

# Enough resources to build a useful Release: title, artist/brand,
# release date, one price, and a thumbnail.
DEFAULT_RESOURCES = [
    SearchItemsResource.ITEM_INFO_DOT_TITLE,
    SearchItemsResource.ITEM_INFO_DOT_BY_LINE_INFO,
    SearchItemsResource.ITEM_INFO_DOT_PRODUCT_INFO,
    SearchItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_PRICE,
    SearchItemsResource.IMAGES_DOT_PRIMARY_DOT_MEDIUM,
]

MAX_PAGES = 10


@dataclass
class SearchOutcome:
    releases: List[Release]
    scanned_count: int
    pages_fetched: int


def build_client(config: AmazonConfig) -> AmazonCreatorsApi:
    return AmazonCreatorsApi(
        credential_id=config.credential_id,
        credential_secret=config.credential_secret,
        version=config.api_version,
        tag=config.partner_tag,
        country=config.country,
    )


def _attr(obj, *names):
    for name in names:
        obj = getattr(obj, name, None)
        if obj is None:
            return None
    return obj


def release_from_item(item) -> Release:
    """Convert an Amazon Creators API `Item` (from search_items/get_items)
    into a plain Release. Every lookup is defensive since Amazon only
    returns the resources it actually has data for."""
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
    asin = getattr(item, "asin", "") or ""

    return Release(
        source="amazon",
        source_id=asin,
        title=title,
        artist=artist,
        release_date=release_date,
        release_date_text=raw_release_date,
        price_display=price_display,
        currency=currency,
        image_url=image_url,
        url=getattr(item, "detail_page_url", None),
        asin=asin or None,
    )


def search_new_releases(
    config: AmazonConfig,
    keywords: Optional[str] = None,
    search_index: str = "Music",
    browse_node_id: Optional[str] = None,
    pages: int = 3,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    client: Optional[AmazonCreatorsApi] = None,
) -> SearchOutcome:
    """Search Amazon's Music catalog and return Releases, newest listings
    first as reported by the API. Callers should still apply
    filter_and_sort_releases() to enforce a release-date ordering and
    date-range filter, since NewestArrivals reflects catalog listing
    order rather than a guaranteed release-date sort.

    Amazon caps a single search at 10 pages (up to 100 results), and there
    is no server-side "filter by release date" parameter, so filtering to
    a specific date only ever happens client-side against whatever this
    scan surfaces. scanned_count/pages_fetched are returned so callers can
    tell the user how exhaustive a given search actually was.
    """
    api = client or build_client(config)
    pages = max(1, min(pages, MAX_PAGES))

    releases_by_id: dict[str, Release] = {}
    scanned_count = 0
    pages_fetched = 0
    for page in range(1, pages + 1):
        try:
            result = api.search_items(
                keywords=keywords,
                search_index=search_index,
                browse_node_id=browse_node_id,
                sort_by=SortBy.NEWESTARRIVALS,
                item_page=page,
                min_price=min_price,
                max_price=max_price,
                resources=DEFAULT_RESOURCES,
            )
        except ItemsNotFoundError:
            break
        except TooManyRequestsError:
            logger.warning("Rate limited by Amazon on page %s; stopping early.", page)
            break

        items = getattr(result, "items", None) or []
        if not items:
            break

        pages_fetched += 1
        scanned_count += len(items)
        for item in items:
            release = release_from_item(item)
            if release.source_id:
                releases_by_id[release.source_id] = release

    return SearchOutcome(
        releases=list(releases_by_id.values()),
        scanned_count=scanned_count,
        pages_fetched=pages_fetched,
    )


def get_release_by_asin(
    config: AmazonConfig, asin: str, client: Optional[AmazonCreatorsApi] = None
) -> Optional[Release]:
    """Look up a single item by ASIN, e.g. to fetch fresh details when
    adding it to the local wishlist."""
    api = client or build_client(config)
    try:
        items = api.get_items([asin], resources=DEFAULT_RESOURCES)
    except ItemsNotFoundError:
        return None
    if not items:
        return None
    return release_from_item(items[0])
