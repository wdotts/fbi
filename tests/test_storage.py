import pytest

from src import storage


def test_add_list_remove_wishlist_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))

    assert storage.load_wishlist() == []

    storage.add_to_wishlist({"asin": "A1", "title": "Album One"})
    storage.add_to_wishlist({"asin": "A2", "title": "Album Two"})

    items = storage.load_wishlist()
    assert [i["asin"] for i in items] == ["A2", "A1"]
    assert storage.wishlist_asins() == {"A1", "A2"}

    # Re-adding an existing ASIN replaces it and moves it to the front.
    storage.add_to_wishlist({"asin": "A1", "title": "Album One (Deluxe)"})
    items = storage.load_wishlist()
    assert items[0]["title"] == "Album One (Deluxe)"
    assert [i["asin"] for i in items] == ["A1", "A2"]

    storage.remove_from_wishlist("A2")
    assert storage.wishlist_asins() == {"A1"}
    assert (tmp_path / "wishlist.json").exists()


def test_add_to_wishlist_requires_asin(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        storage.add_to_wishlist({"title": "No ASIN"})
