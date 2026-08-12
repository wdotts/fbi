from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _data_dir() -> Path:
    path = Path(os.environ.get("APP_DATA_DIR", _DEFAULT_DATA_DIR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _wishlist_path() -> Path:
    return _data_dir() / "wishlist.json"


def _item_key(item: dict) -> Optional[str]:
    source = item.get("source")
    source_id = item.get("source_id")
    if source and source_id:
        return f"{source}:{source_id}"
    return None


def load_wishlist() -> list[dict]:
    path = _wishlist_path()
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save(items: list[dict]) -> None:
    with _wishlist_path().open("w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def add_to_wishlist(item: dict) -> None:
    """Save (or replace) a wishlist entry, most-recently-added first.
    Items are keyed by 'source:source_id' (e.g. 'amazon:B000TEST' or
    'musicbrainz:<mbid>'), not by ASIN, since most non-Amazon releases
    don't have one."""
    key = _item_key(item)
    if not key:
        raise ValueError("Cannot add a wishlist item without both 'source' and 'source_id'.")
    items = [i for i in load_wishlist() if _item_key(i) != key]
    items.insert(0, item)
    _save(items)


def remove_from_wishlist(key: str) -> None:
    items = [i for i in load_wishlist() if _item_key(i) != key]
    _save(items)


def wishlist_keys() -> set[str]:
    return {k for k in (_item_key(i) for i in load_wishlist()) if k}
