from __future__ import annotations

import os
import socket
from datetime import date, datetime, timedelta

from flask import Flask, jsonify, redirect, render_template, request, url_for

from . import aggregate, storage
from .cart import cart_add_url_multi, cart_url_for
from .config import load_config

app = Flask(__name__)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _local_ip() -> str:
    """Best-effort LAN IP for the "open this on your phone" hint. Doesn't
    actually send any traffic - just asks the OS what interface it would
    use to reach an external address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _resolve_sources(args) -> list:
    selected = [s for s in args.getlist("sources") if s in aggregate.ALL_SOURCES]
    return selected or list(aggregate.DEFAULT_SOURCES)


def _run_search(args):
    config = load_config()
    sources = _resolve_sources(args)
    exact_date = _parse_date(args.get("date"))
    keywords = args.get("keywords") or None

    if exact_date:
        since = until = exact_date
    else:
        days = int(args.get("days") or 60)
        since = _parse_date(args.get("since")) or (date.today() - timedelta(days=days))
        until = _parse_date(args.get("until"))

    result = aggregate.search(config, sources=sources, since=since, until=until, keywords=keywords)
    return result, config, sources, exact_date


def _rows_with_extras(releases, config):
    in_wishlist = storage.wishlist_keys()
    rows = []
    for r in releases:
        rows.append(
            {
                "release": r,
                "cart_url": cart_url_for(r.asin, r.artist, r.title, config.amazon_country, config.amazon_partner_tag),
                "is_real_cart": bool(r.asin and config.amazon_partner_tag),
                "in_wishlist": r.key in in_wishlist,
            }
        )
    return rows


@app.route("/")
def index():
    result, config, sources, exact_date = _run_search(request.args)
    rows = _rows_with_extras(result.releases, config)
    return render_template(
        "index.html",
        rows=rows,
        notes=result.notes,
        keywords=request.args.get("keywords", ""),
        days=request.args.get("days", "60"),
        date=request.args.get("date", ""),
        all_sources=aggregate.ALL_SOURCES,
        selected_sources=sources,
        amazon_configured=config.amazon is not None,
    )


@app.route("/api/releases")
def api_releases():
    result, config, sources, exact_date = _run_search(request.args)
    in_wishlist = storage.wishlist_keys()
    return jsonify(
        {
            "notes": result.notes,
            "sources": sources,
            "results": [
                {
                    **r.to_dict(),
                    "cart_url": cart_url_for(r.asin, r.artist, r.title, config.amazon_country, config.amazon_partner_tag),
                    "in_wishlist": r.key in in_wishlist,
                }
                for r in result.releases
            ],
        }
    )


@app.route("/wishlist")
def wishlist_view():
    config = load_config()
    items = storage.load_wishlist()
    rows = []
    for item in items:
        asin = item.get("asin")
        rows.append(
            {
                "item": item,
                "cart_url": cart_url_for(
                    asin, item.get("artist"), item.get("title") or "", config.amazon_country, config.amazon_partner_tag
                ),
                "is_real_cart": bool(asin and config.amazon_partner_tag),
            }
        )
    asins = [i["asin"] for i in items if i.get("asin")]
    bulk_cart_url = None
    if asins and config.amazon_partner_tag:
        bulk_cart_url = cart_add_url_multi(asins, config.amazon_country, config.amazon_partner_tag)
    return render_template("wishlist.html", rows=rows, bulk_cart_url=bulk_cart_url, asin_count=len(asins))


@app.route("/wishlist/add", methods=["POST"])
def wishlist_add():
    item = {
        "source": request.form.get("source"),
        "source_id": request.form.get("source_id"),
        "asin": request.form.get("asin") or None,
        "title": request.form.get("title"),
        "artist": request.form.get("artist") or None,
        "release_date": request.form.get("release_date") or None,
        "release_date_text": request.form.get("release_date_text") or None,
        "format": request.form.get("format") or None,
        "price_display": request.form.get("price_display") or None,
        "currency": request.form.get("currency") or None,
        "image_url": request.form.get("image_url") or None,
        "url": request.form.get("url") or None,
    }
    if item["source"] and item["source_id"]:
        storage.add_to_wishlist(item)
    return redirect(request.form.get("next") or url_for("index"))


@app.route("/wishlist/remove", methods=["POST"])
def wishlist_remove():
    key = request.form.get("key")
    if key:
        storage.remove_from_wishlist(key)
    return redirect(request.form.get("next") or url_for("wishlist_view"))


if __name__ == "__main__":
    # Bind to 0.0.0.0 so other devices on the same network (e.g. a phone)
    # can reach this - the Flask default of 127.0.0.1 only accepts
    # connections from this machine. debug defaults OFF here on purpose:
    # Flask/Werkzeug's interactive debugger allows arbitrary code
    # execution to anyone who can reach it, which is fine on localhost but
    # not once the server is reachable from the rest of the network. Set
    # FLASK_DEBUG=true only when you're the sole device on the network.
    port = int(os.environ.get("PORT", "5000"))
    debug = _env_flag("FLASK_DEBUG", default=False)
    ip = _local_ip()
    print(f" * Running on this machine:  http://127.0.0.1:{port}/")
    print(f" * On your phone (same Wi-Fi): http://{ip}:{port}/")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
