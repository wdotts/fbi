from datetime import date

from src.releases import Release, filter_and_sort_releases, parse_release_date


def test_parse_release_date_full_precision_only():
    assert parse_release_date("2026-08-01") == date(2026, 8, 1)
    assert parse_release_date(None) is None
    assert parse_release_date("") is None
    assert parse_release_date("not-a-date") is None


def test_parse_release_date_rejects_partial_precision():
    # A bare year or year-month can't be confirmed to match (or not match)
    # a specific day, so these must not be silently approximated.
    assert parse_release_date("2026") is None
    assert parse_release_date("2026-08") is None


def test_release_date_display_falls_back_to_text_for_partial_dates():
    precise = Release(source="musicbrainz", source_id="1", title="A", release_date=date(2026, 8, 1))
    assert precise.release_date_display() == "2026-08-01"

    partial = Release(source="musicbrainz", source_id="2", title="B", release_date=None, release_date_text="2026")
    assert partial.release_date_display() == "2026"

    unknown = Release(source="musicbrainz", source_id="3", title="C")
    assert unknown.release_date_display() == "Unknown"


def test_release_key_is_source_scoped():
    r = Release(source="amazon", source_id="B000TEST", title="A")
    assert r.key == "amazon:B000TEST"


def test_filter_and_sort_releases_orders_newest_first_and_applies_since():
    releases = [
        Release(source="amazon", source_id="A1", title="Old", release_date=date(2025, 1, 1)),
        Release(source="amazon", source_id="A2", title="New", release_date=date(2026, 6, 1)),
        Release(source="amazon", source_id="A3", title="Unknown Date", release_date=None),
    ]

    result = filter_and_sort_releases(releases, since=date(2026, 1, 1))

    assert [r.source_id for r in result] == ["A2", "A3"]


def test_filter_and_sort_releases_applies_until():
    releases = [
        Release(source="amazon", source_id="A1", title="Too New", release_date=date(2026, 12, 1)),
        Release(source="amazon", source_id="A2", title="In Range", release_date=date(2026, 6, 1)),
    ]

    result = filter_and_sort_releases(releases, until=date(2026, 7, 1))

    assert [r.source_id for r in result] == ["A2"]


def test_filter_and_sort_releases_require_date_drops_unknown_and_partial():
    releases = [
        Release(source="amazon", source_id="A1", title="New", release_date=date(2026, 6, 1)),
        Release(source="musicbrainz", source_id="A2", title="Year only", release_date=None, release_date_text="2026"),
    ]

    result = filter_and_sort_releases(releases, require_date=True)

    assert [r.source_id for r in result] == ["A1"]


def test_to_dict_round_trips_key_fields():
    r = Release(
        source="musicbrainz",
        source_id="mbid-1",
        title="Album",
        artist="Artist",
        release_date=date(2026, 8, 1),
        format="CD",
        asin="B000TEST",
    )
    d = r.to_dict()
    assert d["source"] == "musicbrainz"
    assert d["source_id"] == "mbid-1"
    assert d["release_date"] == "2026-08-01"
    assert d["asin"] == "B000TEST"
    assert d["format"] == "CD"
