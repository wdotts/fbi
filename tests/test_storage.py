import pytest

from src import storage


def test_add_list_remove_wishlist_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))

    assert storage.load_wishlist() == []

    storage.add_to_wishlist({"source": "amazon", "source_id": "A1", "title": "Album One"})
    storage.add_to_wishlist({"source": "musicbrainz", "source_id": "A2", "title": "Album Two"})

    items = storage.load_wishlist()
    assert [i["source_id"] for i in items] == ["A2", "A1"]
    assert storage.wishlist_keys() == {"amazon:A1", "musicbrainz:A2"}

    # Re-adding an existing key replaces it and moves it to the front.
    storage.add_to_wishlist({"source": "amazon", "source_id": "A1", "title": "Album One (Deluxe)"})
    items = storage.load_wishlist()
    assert items[0]["title"] == "Album One (Deluxe)"
    assert [i["source_id"] for i in items] == ["A1", "A2"]

    storage.remove_from_wishlist("musicbrainz:A2")
    assert storage.wishlist_keys() == {"amazon:A1"}
    assert (tmp_path / "wishlist.json").exists()


def test_add_to_wishlist_requires_source_and_source_id(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        storage.add_to_wishlist({"title": "No identity"})
    with pytest.raises(ValueError):
        storage.add_to_wishlist({"source": "amazon", "title": "No source_id"})
