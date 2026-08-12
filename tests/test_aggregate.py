from datetime import date

import pytest

from src import aggregate, amazon_client, discogs_client, musicbrainz_client
from src.config import AmazonConfig, AppConfig
from src.releases import Release


def _config(amazon=None, amazon_partner_tag=None):
    return AppConfig(
        amazon=amazon,
        amazon_country="US",
        amazon_partner_tag=amazon_partner_tag,
        musicbrainz_contact="me@example.com",
        discogs_token=None,
    )


def test_parse_sources_defaults_to_musicbrainz():
    assert aggregate.parse_sources(None) == ["musicbrainz"]
    assert aggregate.parse_sources("") == ["musicbrainz"]


def test_parse_sources_parses_and_lowercases_comma_list():
    assert aggregate.parse_sources("Amazon, musicbrainz") == ["amazon", "musicbrainz"]


def test_parse_sources_rejects_unknown_source():
    with pytest.raises(ValueError):
        aggregate.parse_sources("spotify")


def test_search_uses_musicbrainz_and_filters_to_range(monkeypatch):
    releases = [
        Release(source="musicbrainz", source_id="1", title="In range", release_date=date(2026, 8, 1)),
        Release(source="musicbrainz", source_id="2", title="Out of range", release_date=date(2020, 1, 1)),
    ]

    def fake_search_releases(**kwargs):
        return musicbrainz_client.SearchOutcome(releases=releases, scanned_count=2)

    monkeypatch.setattr(musicbrainz_client, "search_releases", fake_search_releases)

    result = aggregate.search(
        _config(), sources=["musicbrainz"], since=date(2026, 8, 1), until=date(2026, 8, 1)
    )

    assert [r.source_id for r in result.releases] == ["1"]
    assert any("MusicBrainz: scanned 2" in n for n in result.notes)


def test_search_skips_amazon_gracefully_when_unconfigured():
    result = aggregate.search(_config(amazon=None), sources=["amazon"], since=date(2026, 8, 1), until=date(2026, 8, 1))

    assert result.releases == []
    assert any(n.startswith("Amazon: skipped") for n in result.notes)


def test_search_queries_amazon_when_configured(monkeypatch):
    amazon_config = AmazonConfig(
        credential_id="id", credential_secret="secret", partner_tag="tag-20", country="US"
    )
    releases = [Release(source="amazon", source_id="B1", title="Album", release_date=date(2026, 8, 1))]

    def fake_search_new_releases(config, **kwargs):
        assert config is amazon_config
        return amazon_client.SearchOutcome(releases=releases, scanned_count=1, pages_fetched=1)

    monkeypatch.setattr(amazon_client, "search_new_releases", fake_search_new_releases)

    result = aggregate.search(
        _config(amazon=amazon_config),
        sources=["amazon"],
        since=date(2026, 8, 1),
        until=date(2026, 8, 1),
    )

    assert [r.source_id for r in result.releases] == ["B1"]
    assert any("Amazon: scanned 1" in n for n in result.notes)


def test_search_combines_multiple_sources(monkeypatch):
    monkeypatch.setattr(
        musicbrainz_client,
        "search_releases",
        lambda **kwargs: musicbrainz_client.SearchOutcome(
            releases=[Release(source="musicbrainz", source_id="mb1", title="A", release_date=date(2026, 8, 1))],
            scanned_count=1,
        ),
    )
    monkeypatch.setattr(
        discogs_client,
        "search_releases",
        lambda **kwargs: discogs_client.SearchOutcome(
            releases=[Release(source="discogs", source_id="d1", title="B", release_date=date(2026, 8, 1))],
            candidates_checked=1,
            detail_fetches=1,
        ),
    )

    result = aggregate.search(
        _config(),
        sources=["musicbrainz", "discogs"],
        since=date(2026, 8, 1),
        until=date(2026, 8, 1),
    )

    assert sorted(r.key for r in result.releases) == ["discogs:d1", "musicbrainz:mb1"]
