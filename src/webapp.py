from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Flask, jsonify, render_template, request

from .amazon_client import search_new_releases
from .config import ConfigError, load_amazon_config
from .releases import filter_and_sort_releases

app = Flask(__name__)


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _get_releases(args):
    config = load_amazon_config()
    days = int(args.get("days") or 60)
    since = _parse_date(args.get("since")) or (date.today() - timedelta(days=days))
    until = _parse_date(args.get("until"))
    keywords = args.get("keywords") or None
    pages = int(args.get("pages") or 3)

    raw = search_new_releases(config, keywords=keywords, pages=pages)
    return filter_and_sort_releases(raw, since=since, until=until)


@app.route("/")
def index():
    try:
        releases = _get_releases(request.args)
        error = None
    except ConfigError as exc:
        releases = []
        error = str(exc)
    return render_template(
        "index.html",
        releases=releases,
        error=error,
        keywords=request.args.get("keywords", ""),
        days=request.args.get("days", "60"),
    )


@app.route("/api/releases")
def api_releases():
    try:
        releases = _get_releases(request.args)
    except ConfigError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify([r.to_dict() for r in releases])


if __name__ == "__main__":
    app.run(debug=True)
