from datetime import date

from src import discogs_client


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


def test_title_to_artist_title_splits_on_dash():
    assert discogs_client._title_to_artist_title("Radiohead - OK Computer") == ("Radiohead", "OK Computer")
    assert discogs_client._title_to_artist_title("Untitled") == (None, "Untitled")


def test_search_releases_without_detail_fetch_uses_year_only(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        assert url == discogs_client.SEARCH_URL
        assert params["year"] == 2026
        return FakeResponse(
            {
                "results": [
                    {
                        "id": 111,
                        "title": "Artist A - Album A",
                        "year": 2026,
                        "format": ["CD", "Album"],
                        "uri": "/Artist-A-Album-A/release/111",
                        "resource_url": "https://api.discogs.com/releases/111",
                        "cover_image": "https://img.example/a.jpg",
                    }
                ]
            }
        )

    monkeypatch.setattr(discogs_client.requests, "get", fake_get)

    outcome = discogs_client.search_releases(
        since=date(2026, 1, 1), until=date(2026, 12, 31), fetch_details=False
    )

    assert outcome.detail_fetches == 0
    assert outcome.candidates_checked == 1
    release = outcome.releases[0]
    assert release.source == "discogs"
    assert release.source_id == "111"
    assert release.artist == "Artist A"
    assert release.title == "Album A"
    assert release.release_date is None
    assert release.release_date_text == "2026"
    assert release.url == "https://www.discogs.com/Artist-A-Album-A/release/111"


def test_search_releases_with_detail_fetch_filters_to_exact_date(monkeypatch):
    search_response = {
        "results": [
            {
                "id": 1,
                "title": "Artist A - Album A",
                "year": 2026,
                "format": ["CD"],
                "uri": "/a/release/1",
                "resource_url": "https://api.discogs.com/releases/1",
            },
            {
                "id": 2,
                "title": "Artist B - Album B",
                "year": 2026,
                "format": ["CD"],
                "uri": "/b/release/2",
                "resource_url": "https://api.discogs.com/releases/2",
            },
        ]
    }
    details = {
        "https://api.discogs.com/releases/1": {"released": "2026-08-01"},
        "https://api.discogs.com/releases/2": {"released": "2026-08-02"},  # outside range
    }

    def fake_get(url, params=None, headers=None, timeout=None):
        if url == discogs_client.SEARCH_URL:
            return FakeResponse(search_response)
        return FakeResponse(details[url])

    monkeypatch.setattr(discogs_client.requests, "get", fake_get)

    sleeps = []
    outcome = discogs_client.search_releases(
        since=date(2026, 8, 1), until=date(2026, 8, 1), fetch_details=True, sleep=sleeps.append
    )

    assert outcome.candidates_checked == 2
    assert outcome.detail_fetches == 2
    assert [r.source_id for r in outcome.releases] == ["1"]
    assert outcome.releases[0].release_date == date(2026, 8, 1)
    assert sleeps == [discogs_client.UNAUTHED_INTERVAL_SECONDS]  # one sleep between two detail fetches


def test_search_releases_uses_authed_interval_with_token(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        assert headers["Authorization"] == "Discogs token=abc123"
        if url == discogs_client.SEARCH_URL:
            return FakeResponse(
                {
                    "results": [
                        {
                            "id": 1,
                            "title": "Artist A - Album A",
                            "uri": "/a/release/1",
                            "resource_url": "https://api.discogs.com/releases/1",
                        },
                        {
                            "id": 2,
                            "title": "Artist B - Album B",
                            "uri": "/b/release/2",
                            "resource_url": "https://api.discogs.com/releases/2",
                        },
                    ]
                }
            )
        return FakeResponse({"released": "2026-08-01"})

    monkeypatch.setattr(discogs_client.requests, "get", fake_get)

    sleeps = []
    discogs_client.search_releases(
        since=date(2026, 8, 1), until=date(2026, 8, 1), token="abc123", sleep=sleeps.append
    )

    assert sleeps == [discogs_client.AUTHED_INTERVAL_SECONDS]
