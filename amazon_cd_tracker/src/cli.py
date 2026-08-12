from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta

from . import aggregate, amazon_client, storage
from .cart import cart_add_url_multi, cart_url_for
from .config import ConfigError, load_config, require_amazon


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Find new CD releases, sorted by release date, across "
            "MusicBrainz, Discogs, and (if configured) Amazon."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search for new CD releases")
    search.add_argument(
        "--sources",
        default=None,
        help=f"Comma-separated sources to query: {', '.join(aggregate.ALL_SOURCES)} (default: musicbrainz)",
    )
    search.add_argument("--keywords", help="Optional keywords, e.g. an artist or genre")
    search.add_argument(
        "--formats",
        default="CD",
        help="Comma-separated media formats to match on MusicBrainz/Discogs (default: CD)",
    )
    search.add_argument(
        "--date",
        help=(
            "Show CDs released on exactly this date (YYYY-MM-DD). Overrides "
            "--since/--until/--days and ignores --limit so every match is shown."
        ),
    )
    search.add_argument("--days", type=int, default=60, help="Only show releases from the last N days (default: 60); ignored if --date is set")
    search.add_argument("--since", help="Only show releases on/after this date (YYYY-MM-DD); ignored if --date is set")
    search.add_argument("--until", help="Only show releases on/before this date (YYYY-MM-DD); ignored if --date is set")
    search.add_argument("--require-date", action="store_true", help="Hide items with no confirmed exact release date")
    search.add_argument("--cart-links", action="store_true", help="Print a real Amazon cart/search link for each result")
    search.add_argument("--save-wishlist", action="store_true", help="Save every displayed result to your local wishlist")
    search.add_argument("--json", action="store_true", help="Output JSON instead of a table")
    search.add_argument("--limit", type=int, default=50, help="Max number of releases to display (default: 50); ignored if --date is set")

    amazon_group = search.add_argument_group("Amazon options (only used when 'amazon' is in --sources)")
    amazon_group.add_argument("--browse-node-id", help="Optional Amazon browse node ID to narrow the category")
    amazon_group.add_argument("--pages", type=int, default=3, help="Amazon result pages to fetch, 1-10 (default: 3); forced to 10 if --date is set")
    amazon_group.add_argument("--min-price", type=int, help="Minimum price, in the marketplace's smallest currency unit")
    amazon_group.add_argument("--max-price", type=int, help="Maximum price, in the marketplace's smallest currency unit")

    discogs_group = search.add_argument_group("Discogs options (only used when 'discogs' is in --sources)")
    discogs_group.add_argument("--discogs-candidates", type=int, default=30, help="Max Discogs search candidates to check against the exact date (default: 30)")
    discogs_group.add_argument("--no-discogs-details", action="store_true", help="Skip Discogs' per-item detail lookup (faster, but only year-precision, unconfirmed dates)")

    mb_group = search.add_argument_group("MusicBrainz options (only used when 'musicbrainz' is in --sources)")
    mb_group.add_argument("--musicbrainz-max-results", type=int, default=aggregate.musicbrainz_client.DEFAULT_MAX_RESULTS, help="Safety cap on MusicBrainz results scanned")

    wishlist = sub.add_parser("wishlist", help="Manage your local wishlist")
    wishlist_sub = wishlist.add_subparsers(dest="wishlist_command", required=True)

    w_add = wishlist_sub.add_parser("add", help="Look up an Amazon ASIN and save it to your wishlist")
    w_add.add_argument("asin")

    w_remove = wishlist_sub.add_parser("remove", help="Remove an item from your wishlist by its key")
    w_remove.add_argument("key", help="A key like 'amazon:B000TEST' or 'musicbrainz:<mbid>', shown by 'wishlist list'")

    w_list = wishlist_sub.add_parser("list", help="Show your wishlist")
    w_list.add_argument("--json", action="store_true", help="Output JSON instead of a table")

    wishlist_sub.add_parser(
        "cart-link",
        help="Print one Amazon link that adds every wishlist item with a known ASIN to your real cart",
    )

    return parser


def _parse_date_arg(value: str, flag: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        print(f"Invalid date for {flag}: {value!r}. Use YYYY-MM-DD.", file=sys.stderr)
        raise SystemExit(2)


def _print_table(rows: list[dict]) -> None:
    title_w = min(50, max((len(r.get("title") or "") for r in rows), default=10))
    artist_w = min(30, max((len(r.get("artist") or "Unknown") for r in rows), default=10))
    header = f"{'RELEASE DATE':<12}  {'SOURCE':<11}  {'ARTIST':<{artist_w}}  {'TITLE':<{title_w}}  PRICE"
    print(header)
    print("-" * len(header))
    for r in rows:
        artist = (r.get("artist") or "Unknown")[:artist_w]
        title = (r.get("title") or "")[:title_w]
        price = r.get("price_display") or "N/A"
        release_date = r.get("release_date") or r.get("release_date_text") or "Unknown"
        source = r.get("source") or "?"
        print(f"{release_date:<12}  {source:<11}  {artist:<{artist_w}}  {title:<{title_w}}  {price}")
        if r.get("source") and r.get("source_id"):
            print(f"  key: {r['source']}:{r['source_id']}")
        if r.get("url"):
            print(f"  -> {r['url']}")
        if r.get("cart_url"):
            print(f"  cart: {r['cart_url']}")


def _run_search(args: argparse.Namespace) -> int:
    try:
        sources = aggregate.parse_sources(args.sources)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    config = load_config()
    formats = tuple(f.strip() for f in args.formats.split(",") if f.strip())

    if args.date:
        target = _parse_date_arg(args.date, "--date")
        since = until = target
        limit = None
        amazon_pages = amazon_client.MAX_PAGES
    else:
        since = _parse_date_arg(args.since, "--since") if args.since else date.today() - timedelta(days=args.days)
        until = _parse_date_arg(args.until, "--until") if args.until else None
        limit = args.limit
        amazon_pages = args.pages

    result = aggregate.search(
        config,
        sources=sources,
        since=since,
        until=until,
        keywords=args.keywords,
        formats=formats,
        require_date=args.require_date,
        amazon_browse_node_id=args.browse_node_id,
        amazon_pages=amazon_pages,
        amazon_min_price=args.min_price,
        amazon_max_price=args.max_price,
        musicbrainz_max_results=args.musicbrainz_max_results,
        discogs_max_candidates=args.discogs_candidates,
        discogs_fetch_details=not args.no_discogs_details,
    )

    for note in result.notes:
        print(note, file=sys.stderr)

    releases = result.releases
    if limit is not None:
        releases = releases[:limit]

    if not releases:
        print("No new CD releases found for the given filters.")
        return 0

    rows = []
    for r in releases:
        row = r.to_dict()
        if args.cart_links:
            row["cart_url"] = cart_url_for(
                r.asin, r.artist, r.title, config.amazon_country, config.amazon_partner_tag
            )
        rows.append(row)

    if args.save_wishlist:
        for row in rows:
            storage.add_to_wishlist({k: v for k, v in row.items() if k != "cart_url"})
        print(f"Saved {len(rows)} release(s) to your wishlist.", file=sys.stderr)

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        _print_table(rows)

    return 0


def _run_wishlist(args: argparse.Namespace) -> int:
    config = load_config()

    if args.wishlist_command == "add":
        try:
            amazon_config = require_amazon(config)
        except ConfigError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 1
        release = amazon_client.get_release_by_asin(amazon_config, args.asin)
        if release is None:
            print(f"Could not find an Amazon item for ASIN {args.asin}.", file=sys.stderr)
            return 1
        storage.add_to_wishlist(release.to_dict())
        print(f"Added to wishlist: {release.artist or 'Unknown'} - {release.title}")
        return 0

    if args.wishlist_command == "remove":
        storage.remove_from_wishlist(args.key)
        print(f"Removed {args.key} from wishlist (if it was there).")
        return 0

    if args.wishlist_command == "list":
        items = storage.load_wishlist()
        if not items:
            print("Your wishlist is empty.")
            return 0
        if args.json:
            print(json.dumps(items, indent=2))
        else:
            _print_table(items)
        return 0

    if args.wishlist_command == "cart-link":
        items = storage.load_wishlist()
        asins = [i["asin"] for i in items if i.get("asin")]
        if not asins:
            print("Your wishlist has no items with a known Amazon ASIN yet.")
            return 0
        if not config.amazon_partner_tag:
            print("Set AMAZON_PARTNER_TAG in .env to build a cart link.", file=sys.stderr)
            return 1
        url = cart_add_url_multi(asins, config.amazon_country, config.amazon_partner_tag)
        print(url)
        if len(asins) > 25:
            print(
                f"Note: only the first 25 of {len(asins)} ASIN-linked wishlist "
                "items fit in one cart link.",
                file=sys.stderr,
            )
        skipped = len(items) - len(asins)
        if skipped:
            print(
                f"Note: {skipped} wishlist item(s) have no known Amazon ASIN "
                "and aren't in this link.",
                file=sys.stderr,
            )
        return 0

    return 1


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "search":
        return _run_search(args)
    if args.command == "wishlist":
        return _run_wishlist(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
