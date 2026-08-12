import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.releases import (
    Release,
    filter_and_sort_releases,
    parse_release_date,
    release_from_item,
)


def make_item(asin, title, release_date, artist_names=None, price=None):
    contributors = [SimpleNamespace(name=n) for n in (artist_names or [])]
    return SimpleNamespace(
        asin=asin,
        detail_page_url=f"https://www.amazon.com/dp/{asin}",
        item_info=SimpleNamespace(
            title=SimpleNamespace(display_value=title),
            by_line_info=SimpleNamespace(contributors=contributors, brand=None),
            product_info=SimpleNamespace(
                release_date=SimpleNamespace(display_value=release_date)
            ),
        ),
        offers_v2=SimpleNamespace(
            listings=(
                [
                    SimpleNamespace(
                        price=SimpleNamespace(
                            money=SimpleNamespace(display_amount=price, currency="USD")
                        )
                    )
                ]
                if price
                else []
            )
        ),
        images=SimpleNamespace(primary=SimpleNamespace(medium=SimpleNamespace(url=None))),
    )


def test_parse_release_date_variants():
    assert parse_release_date("2026-08-01") == date(2026, 8, 1)
    assert parse_release_date("2026-08") == date(2026, 8, 1)
    assert parse_release_date("2026") == date(2026, 1, 1)
    assert parse_release_date(None) is None
    assert parse_release_date("") is None
    assert parse_release_date("not-a-date") is None


def test_release_from_item_extracts_fields():
    item = make_item(
        "B000TEST", "Great Album", "2026-07-15", artist_names=["Test Artist"], price="$12.99"
    )
    release = release_from_item(item)

    assert release.asin == "B000TEST"
    assert release.title == "Great Album"
    assert release.artist == "Test Artist"
    assert release.release_date == date(2026, 7, 15)
    assert release.price_display == "$12.99"
    assert release.currency == "USD"
    assert release.url == "https://www.amazon.com/dp/B000TEST"


def test_release_from_item_handles_missing_data():
    item = make_item("B000EMPTY", "Mystery Album", None)
    release = release_from_item(item)

    assert release.artist is None
    assert release.release_date is None
    assert release.price_display is None


def test_filter_and_sort_releases_orders_newest_first_and_applies_since():
    releases = [
        Release("A1", "Old", "Artist", date(2025, 1, 1), None, None, None, None),
        Release("A2", "New", "Artist", date(2026, 6, 1), None, None, None, None),
        Release("A3", "Unknown Date", "Artist", None, None, None, None, None),
    ]

    result = filter_and_sort_releases(releases, since=date(2026, 1, 1))

    assert [r.asin for r in result] == ["A2", "A3"]


def test_filter_and_sort_releases_applies_until():
    releases = [
        Release("A1", "Too New", "Artist", date(2026, 12, 1), None, None, None, None),
        Release("A2", "In Range", "Artist", date(2026, 6, 1), None, None, None, None),
    ]

    result = filter_and_sort_releases(releases, until=date(2026, 7, 1))

    assert [r.asin for r in result] == ["A2"]


def test_filter_and_sort_releases_require_date_drops_unknown():
    releases = [
        Release("A1", "New", "Artist", date(2026, 6, 1), None, None, None, None),
        Release("A2", "Unknown", "Artist", None, None, None, None, None),
    ]

    result = filter_and_sort_releases(releases, require_date=True)

    assert [r.asin for r in result] == ["A1"]
