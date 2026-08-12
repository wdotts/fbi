from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta

from .amazon_client import search_new_releases
from .config import ConfigError, load_amazon_config
from .releases import filter_and_sort_releases


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find new CD releases on Amazon, sorted by release date."
    )
    parser.add_argument("--keywords", help="Optional keywords, e.g. an artist or genre")
    parser.add_argument("--search-index", default="Music", help="Amazon SearchIndex (default: Music)")
    parser.add_argument("--browse-node-id", help="Optional Amazon browse node ID to narrow the category")
    parser.add_argument("--days", type=int, default=60, help="Only show releases from the last N days (default: 60)")
    parser.add_argument("--since", help="Only show releases on/after this date (YYYY-MM-DD); overrides --days")
    parser.add_argument("--until", help="Only show releases on/before this date (YYYY-MM-DD)")
    parser.add_argument("--pages", type=int, default=3, help="Number of result pages to fetch, 1-10 (default: 3)")
    parser.add_argument("--limit", type=int, default=50, help="Max number of releases to display (default: 50)")
    parser.add_argument("--min-price", type=int, help="Minimum price, in the marketplace's smallest currency unit")
    parser.add_argument("--max-price", type=int, help="Maximum price, in the marketplace's smallest currency unit")
    parser.add_argument("--require-date", action="store_true", help="Hide items with no known release date")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of a table")
    return parser.parse_args(argv)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main(argv=None) -> int:
    args = parse_args(argv)

    try:
        config = load_amazon_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    since = _parse_date(args.since) if args.since else date.today() - timedelta(days=args.days)
    until = _parse_date(args.until) if args.until else None

    raw_releases = search_new_releases(
        config,
        keywords=args.keywords,
        search_index=args.search_index,
        browse_node_id=args.browse_node_id,
        pages=args.pages,
        min_price=args.min_price,
        max_price=args.max_price,
    )
    releases = filter_and_sort_releases(
        raw_releases, since=since, until=until, require_date=args.require_date
    )[: args.limit]

    if not releases:
        print("No new CD releases found for the given filters.")
        return 0

    if args.json:
        print(json.dumps([r.to_dict() for r in releases], indent=2))
        return 0

    title_w = min(50, max((len(r.title) for r in releases), default=10))
    artist_w = min(30, max((len(r.artist or "Unknown") for r in releases), default=10))
    header = f"{'RELEASE DATE':<12}  {'ARTIST':<{artist_w}}  {'TITLE':<{title_w}}  PRICE"
    print(header)
    print("-" * len(header))
    for r in releases:
        artist = (r.artist or "Unknown")[:artist_w]
        title = r.title[:title_w]
        price = r.price_display or "N/A"
        print(f"{r.release_date_display():<12}  {artist:<{artist_w}}  {title:<{title_w}}  {price}")
        if r.url:
            print(f"  -> {r.url}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
