from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Flask, jsonify, redirect, render_template, request, url_for

from . import storage
from .amazon_client import MAX_PAGES, search_new_releases
from .cart import cart_add_url, cart_add_url_multi
from .config import ConfigError, load_amazon_config
from .releases import filter_and_sort_releases

app = Flask(__name__)


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _search(args):
    config = load_amazon_config()
    exact_date = _parse_date(args.get("date"))
    keywords = args.get("keywords") or None

    if exact_date:
        since = until = exact_date
        pages = MAX_PAGES
    else:
        days = int(args.get("days") or 60)
        since = _parse_date(args.get("since")) or (date.today() - timedelta(days=days))
        until = _parse_date(args.get("until"))
        pages = int(args.get("pages") or 3)

    outcome = search_new_releases(config, keywords=keywords, pages=pages)
    releases = filter_and_sort_releases(outcome.releases, since=since, until=until)
    return releases, outcome, config, exact_date


def _rows_with_extras(releases, config):
    in_wishlist = storage.wishlist_asins()
    return [
        {
            "release": r,
            "cart_url": cart_add_url(r.asin, config.country, config.partner_tag),
            "in_wishlist": r.asin in in_wishlist,
        }
        for r in releases
    ]


@app.route("/")
def index():
    error = None
    note = None
    rows = []
    try:
        releases, outcome, config, exact_date = _search(request.args)
        rows = _rows_with_extras(releases, config)
        if exact_date and outcome.scanned_count >= 100:
            note = (
                "Amazon's search API has no direct release-date filter and caps a "
                "single search at 100 catalog listings ordered by recency, so "
                "results for dates more than a couple of months old may be "
                "incomplete. Try adding keywords (an artist or label) to dig "
                "further into the catalog for this date."
            )
    except ConfigError as exc:
        error = str(exc)
    return render_template(
        "index.html",
        rows=rows,
        error=error,
        note=note,
        keywords=request.args.get("keywords", ""),
        days=request.args.get("days", "60"),
        date=request.args.get("date", ""),
    )


@app.route("/api/releases")
def api_releases():
    try:
        releases, outcome, config, exact_date = _search(request.args)
    except ConfigError as exc:
        return jsonify({"error": str(exc)}), 400
    in_wishlist = storage.wishlist_asins()
    return jsonify(
        {
            "scanned_count": outcome.scanned_count,
            "pages_fetched": outcome.pages_fetched,
            "results": [
                {
                    **r.to_dict(),
                    "cart_url": cart_add_url(r.asin, config.country, config.partner_tag),
                    "in_wishlist": r.asin in in_wishlist,
                }
                for r in releases
            ],
        }
    )


@app.route("/wishlist")
def wishlist_view():
    items = storage.load_wishlist()
    cart_url = None
    try:
        config = load_amazon_config()
        asins = [i["asin"] for i in items if i.get("asin")]
        if asins:
            cart_url = cart_add_url_multi(asins, config.country, config.partner_tag)
    except ConfigError:
        pass
    return render_template("wishlist.html", items=items, cart_url=cart_url)


@app.route("/wishlist/add", methods=["POST"])
def wishlist_add():
    item = {
        "asin": request.form.get("asin"),
        "title": request.form.get("title"),
        "artist": request.form.get("artist") or None,
        "release_date": request.form.get("release_date") or None,
        "price_display": request.form.get("price_display") or None,
        "currency": request.form.get("currency") or None,
        "image_url": request.form.get("image_url") or None,
        "url": request.form.get("url") or None,
    }
    if item["asin"]:
        storage.add_to_wishlist(item)
    return redirect(request.form.get("next") or url_for("index"))


@app.route("/wishlist/remove", methods=["POST"])
def wishlist_remove():
    asin = request.form.get("asin")
    if asin:
        storage.remove_from_wishlist(asin)
    return redirect(request.form.get("next") or url_for("wishlist_view"))


if __name__ == "__main__":
    app.run(debug=True)
