from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta

from . import storage
from .amazon_client import MAX_PAGES, get_release_by_asin, search_new_releases
from .cart import cart_add_url, cart_add_url_multi
from .config import ConfigError, load_amazon_config
from .releases import filter_and_sort_releases


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find new CD releases on Amazon, sorted by release date."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search for new CD releases")
    search.add_argument("--keywords", help="Optional keywords, e.g. an artist or genre")
    search.add_argument("--search-index", default="Music", help="Amazon SearchIndex (default: Music)")
    search.add_argument("--browse-node-id", help="Optional Amazon browse node ID to narrow the category")
    search.add_argument(
        "--date",
        help=(
            "Show CDs released on exactly this date (YYYY-MM-DD). Overrides "
            "--since/--until/--days, ignores --pages/--limit (fetches Amazon's "
            "maximum result depth and shows every match), for the most complete "
            "list Amazon's API can produce."
        ),
    )
    search.add_argument("--days", type=int, default=60, help="Only show releases from the last N days (default: 60); ignored if --date is set")
    search.add_argument("--since", help="Only show releases on/after this date (YYYY-MM-DD); ignored if --date is set")
    search.add_argument("--until", help="Only show releases on/before this date (YYYY-MM-DD); ignored if --date is set")
    search.add_argument("--pages", type=int, default=3, help="Number of result pages to fetch, 1-10 (default: 3); ignored if --date is set")
    search.add_argument("--limit", type=int, default=50, help="Max number of releases to display (default: 50); ignored if --date is set")
    search.add_argument("--min-price", type=int, help="Minimum price, in the marketplace's smallest currency unit")
    search.add_argument("--max-price", type=int, help="Maximum price, in the marketplace's smallest currency unit")
    search.add_argument("--require-date", action="store_true", help="Hide items with no known release date")
    search.add_argument("--cart-links", action="store_true", help="Print a real Amazon 'add to cart' link for each result")
    search.add_argument("--save-wishlist", action="store_true", help="Save every displayed result to your local wishlist")
    search.add_argument("--json", action="store_true", help="Output JSON instead of a table")

    wishlist = sub.add_parser("wishlist", help="Manage your local wishlist")
    wishlist_sub = wishlist.add_subparsers(dest="wishlist_command", required=True)

    w_add = wishlist_sub.add_parser("add", help="Look up an ASIN on Amazon and save it to your wishlist")
    w_add.add_argument("asin")

    w_remove = wishlist_sub.add_parser("remove", help="Remove an ASIN from your wishlist")
    w_remove.add_argument("asin")

    w_list = wishlist_sub.add_parser("list", help="Show your wishlist")
    w_list.add_argument("--json", action="store_true", help="Output JSON instead of a table")

    wishlist_sub.add_parser(
        "cart-link",
        help="Print one Amazon link that adds your whole wishlist to your real cart",
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
    header = f"{'RELEASE DATE':<12}  {'ARTIST':<{artist_w}}  {'TITLE':<{title_w}}  PRICE"
    print(header)
    print("-" * len(header))
    for r in rows:
        artist = (r.get("artist") or "Unknown")[:artist_w]
        title = (r.get("title") or "")[:title_w]
        price = r.get("price_display") or "N/A"
        release_date = r.get("release_date") or "Unknown"
        print(f"{release_date:<12}  {artist:<{artist_w}}  {title:<{title_w}}  {price}")
        if r.get("asin"):
            print(f"  asin: {r['asin']}")
        if r.get("url"):
            print(f"  -> {r['url']}")
        if r.get("cart_url"):
            print(f"  cart: {r['cart_url']}")


def _run_search(args: argparse.Namespace) -> int:
    try:
        config = load_amazon_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    if args.date:
        target = _parse_date_arg(args.date, "--date")
        since = until = target
        pages = MAX_PAGES
        limit = None
    else:
        since = _parse_date_arg(args.since, "--since") if args.since else date.today() - timedelta(days=args.days)
        until = _parse_date_arg(args.until, "--until") if args.until else None
        pages = args.pages
        limit = args.limit

    outcome = search_new_releases(
        config,
        keywords=args.keywords,
        search_index=args.search_index,
        browse_node_id=args.browse_node_id,
        pages=pages,
        min_price=args.min_price,
        max_price=args.max_price,
    )
    releases = filter_and_sort_releases(
        outcome.releases, since=since, until=until, require_date=args.require_date
    )
    if limit is not None:
        releases = releases[:limit]

    if args.date:
        print(
            f"Scanned {outcome.scanned_count} Amazon catalog listing(s) across "
            f"{outcome.pages_fetched} page(s) (Amazon's per-search maximum is "
            f"100 results); {len(releases)} matched {args.date} exactly.",
            file=sys.stderr,
        )
        if outcome.scanned_count >= 100:
            print(
                "Note: Amazon's search API has no direct release-date filter and "
                "caps a single search at 100 results ordered by catalog recency, "
                "so this may be incomplete for dates more than a couple of "
                "months old. Try adding --keywords (an artist or label) to dig "
                "further into the catalog for that date.",
                file=sys.stderr,
            )

    if not releases:
        print("No new CD releases found for the given filters.")
        return 0

    rows = []
    for r in releases:
        row = r.to_dict()
        if args.cart_links:
            row["cart_url"] = cart_add_url(r.asin, config.country, config.partner_tag)
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
    if args.wishlist_command == "add":
        try:
            config = load_amazon_config()
        except ConfigError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 1
        release = get_release_by_asin(config, args.asin)
        if release is None:
            print(f"Could not find an Amazon item for ASIN {args.asin}.", file=sys.stderr)
            return 1
        storage.add_to_wishlist(release.to_dict())
        print(f"Added to wishlist: {release.artist or 'Unknown'} - {release.title}")
        return 0

    if args.wishlist_command == "remove":
        storage.remove_from_wishlist(args.asin)
        print(f"Removed {args.asin} from wishlist (if it was there).")
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
        try:
            config = load_amazon_config()
        except ConfigError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 1
        items = storage.load_wishlist()
        if not items:
            print("Your wishlist is empty.")
            return 0
        asins = [i["asin"] for i in items if i.get("asin")]
        url = cart_add_url_multi(asins, config.country, config.partner_tag)
        print(url)
        if len(asins) > 25:
            print(
                f"Note: only the first 25 of {len(asins)} wishlist items fit in "
                "one cart link.",
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
