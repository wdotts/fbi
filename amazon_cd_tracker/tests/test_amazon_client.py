from datetime import date
from types import SimpleNamespace

from src.amazon_client import release_from_item


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


def test_release_from_item_extracts_fields():
    item = make_item(
        "B000TEST", "Great Album", "2026-07-15", artist_names=["Test Artist"], price="$12.99"
    )
    release = release_from_item(item)

    assert release.source == "amazon"
    assert release.source_id == "B000TEST"
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


def test_release_from_item_keeps_partial_date_as_text_only():
    item = make_item("B000YEAR", "Old Album", "1998")
    release = release_from_item(item)

    assert release.release_date is None
    assert release.release_date_text == "1998"
    assert release.release_date_display() == "1998"
