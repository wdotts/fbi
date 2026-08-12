from datetime import date

from src import musicbrainz_client


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


def _mb_release(mbid, title, date_str, artist="Some Artist", fmt="CD", asin=None):
    return {
        "id": mbid,
        "title": title,
        "date": date_str,
        "asin": asin,
        "artist-credit": [{"name": artist}],
        "media": [{"format": fmt}],
    }


def test_build_query_includes_date_range_format_and_keywords():
    query = musicbrainz_client._build_query(
        date(2026, 8, 1), date(2026, 8, 1), keywords="Radiohead", formats=("CD",)
    )
    assert "date:[2026-08-01 TO 2026-08-01]" in query
    assert 'format:"CD"' in query
    assert 'artist:"Radiohead"' in query
    assert 'release:"Radiohead"' in query


def test_search_releases_paginates_and_parses_results(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params)
        offset = params["offset"]
        if offset == 0:
            releases = [_mb_release(f"mbid-{i}", f"Album {i}", "2026-08-01") for i in range(100)]
            return FakeResponse({"count": 150, "releases": releases})
        releases = [_mb_release(f"mbid-{i}", f"Album {i}", "2026-08-01") for i in range(100, 150)]
        return FakeResponse({"count": 150, "releases": releases})

    monkeypatch.setattr(musicbrainz_client.requests, "get", fake_get)

    sleeps = []
    outcome = musicbrainz_client.search_releases(
        since=date(2026, 8, 1),
        until=date(2026, 8, 1),
        contact="me@example.com",
        sleep=sleeps.append,
    )

    assert outcome.scanned_count == 150
    assert len(outcome.releases) == 150
    assert len(calls) == 2
    assert sleeps == [musicbrainz_client.RATE_LIMIT_SECONDS]  # one sleep between the two pages

    first = outcome.releases[0]
    assert first.source == "musicbrainz"
    assert first.source_id == "mbid-0"
    assert first.artist == "Some Artist"
    assert first.release_date == date(2026, 8, 1)
    assert first.format == "CD"
    assert first.url == "https://musicbrainz.org/release/mbid-0"


def test_search_releases_carries_asin_when_present(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(
            {"count": 1, "releases": [_mb_release("mbid-1", "Album", "2026-08-01", asin="B000TEST")]}
        )

    monkeypatch.setattr(musicbrainz_client.requests, "get", fake_get)

    outcome = musicbrainz_client.search_releases(since=date(2026, 8, 1), until=date(2026, 8, 1))

    assert outcome.releases[0].asin == "B000TEST"


def test_search_releases_respects_max_results_safety_cap(monkeypatch):
    call_count = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        call_count["n"] += 1
        offset = params["offset"]
        releases = [_mb_release(f"mbid-{offset + i}", "Album", "2026-08-01") for i in range(100)]
        return FakeResponse({"count": 10000, "releases": releases})

    monkeypatch.setattr(musicbrainz_client.requests, "get", fake_get)

    outcome = musicbrainz_client.search_releases(
        since=date(2026, 8, 1), until=date(2026, 8, 1), max_results=250, sleep=lambda s: None
    )

    # Stops once offset >= max_results, not once it exhausts the (huge) total.
    assert outcome.scanned_count == 300  # 3 pages of 100 before the offset>=250 check trips
    assert call_count["n"] == 3
