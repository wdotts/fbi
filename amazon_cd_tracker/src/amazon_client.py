from __future__ import annotations

import logging
from typing import List, Optional

from amazon_creatorsapi import AmazonCreatorsApi
from amazon_creatorsapi.errors import ItemsNotFoundError, TooManyRequestsError
from amazon_creatorsapi.models import SearchItemsResource, SortBy

from .config import AmazonConfig
from .releases import Release, release_from_item

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


def build_client(config: AmazonConfig) -> AmazonCreatorsApi:
    return AmazonCreatorsApi(
        credential_id=config.credential_id,
        credential_secret=config.credential_secret,
        version=config.api_version,
        tag=config.partner_tag,
        country=config.country,
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
) -> List[Release]:
    """Search Amazon's Music catalog and return Releases, newest listings
    first as reported by the API. Callers should still apply
    filter_and_sort_releases() to enforce a release-date ordering and
    date-range filter, since NewestArrivals reflects catalog listing
    order rather than a guaranteed release-date sort.
    """
    api = client or build_client(config)
    pages = max(1, min(pages, MAX_PAGES))

    releases_by_asin: dict[str, Release] = {}
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

        for item in items:
            release = release_from_item(item)
            if release.asin:
                releases_by_asin[release.asin] = release

    return list(releases_by_asin.values())
