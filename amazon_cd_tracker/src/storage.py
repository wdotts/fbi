from __future__ import annotations

import json
import os
from pathlib import Path

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _data_dir() -> Path:
    path = Path(os.environ.get("APP_DATA_DIR", _DEFAULT_DATA_DIR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _wishlist_path() -> Path:
    return _data_dir() / "wishlist.json"


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
    """Save (or replace) a wishlist entry, most-recently-added first."""
    asin = item.get("asin")
    if not asin:
        raise ValueError("Cannot add a wishlist item without an ASIN.")
    items = [i for i in load_wishlist() if i.get("asin") != asin]
    items.insert(0, item)
    _save(items)


def remove_from_wishlist(asin: str) -> None:
    items = [i for i in load_wishlist() if i.get("asin") != asin]
    _save(items)


def wishlist_asins() -> set[str]:
    return {i["asin"] for i in load_wishlist() if i.get("asin")}
