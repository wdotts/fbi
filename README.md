# Amazon New CD Release Tracker

A small app that connects to Amazon's official **Amazon Creators API** (the
successor to the Product Advertising API 5.0) to search Amazon's Music
catalog and list new CD releases, sorted by release date. It ships as both
a CLI and a local web UI, sharing the same search/sort logic.

This app only talks to Amazon through its official, authenticated API. It
does not scrape Amazon's website, which would violate Amazon's Terms of
Service.

## Before you start: you need Amazon API access

Amazon does not offer public, credential-free access to its catalog. To use
this app you need:

1. **An Amazon Associates account** in the marketplace you want to search
   (e.g. amazon.com for the US), enrolled and in good standing.
2. **Amazon Creators API credentials** (a credential ID and secret), issued
   through Associates Central once your account qualifies for API access.
   Amazon typically requires a track record of qualifying referred sales
   before granting API access — a brand-new Associates account usually
   won't be approved immediately. See Amazon's Associates Program and
   Creators API documentation for current eligibility rules; they change
   over time and are out of this project's control.
3. **A partner/tracking tag** from your Associates account.

There is no way around this requirement — it's how Amazon controls access
to its catalog data. Until you have credentials, the app will run but will
show a clear configuration error instead of results.

## Setup

```bash
cd amazon_cd_tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and fill in:

```
AMAZON_CREDENTIAL_ID=...
AMAZON_CREDENTIAL_SECRET=...
AMAZON_PARTNER_TAG=yourtag-20
AMAZON_COUNTRY=US
```

`AMAZON_COUNTRY` picks the Amazon marketplace to search (`US`, `UK`, `DE`,
`FR`, `JP`, `CA`, and others).

## Usage: command line

```bash
python -m src.cli --days 30
```

Useful flags:

- `--keywords "artist or genre"` — narrow the search
- `--days N` — only show releases from the last N days (default 60)
- `--since YYYY-MM-DD` / `--until YYYY-MM-DD` — explicit date range
- `--browse-node-id ID` — restrict to a specific Amazon browse node (e.g. a
  "CDs & Vinyl" category node) if you want to exclude digital-only music
- `--pages N` — how many pages of results to fetch from Amazon (1-10,
  default 3; each page is one API call)
- `--json` — print machine-readable JSON instead of a table
- `--limit N` — cap how many releases are shown

Example:

```bash
python -m src.cli --keywords "jazz" --days 45 --pages 5
```

## Usage: web app

```bash
python -m src.webapp
```

Then open http://127.0.0.1:5000/. The same filters are available as query
parameters (`keywords`, `days`), and results are also available as JSON at
`/api/releases`.

## How it works

`src/amazon_client.py` calls `SearchItems` against Amazon's Music catalog
(`SearchIndex=Music`), asking for `NewestArrivals` ordering and requesting
the `ItemInfo.ProductInfo` resource, which is where Amazon reports a
release's `ReleaseDate`. `src/releases.py` parses that date and is
responsible for the actual "sort/filter by date" behavior this app is
for — `NewestArrivals` reflects Amazon's catalog listing order, not
strictly the release date, so results are re-sorted client-side by parsed
release date (newest first) and filtered to your requested date range.

## Running tests

```bash
pip install pytest
python -m pytest tests/
```

The tests cover the date parsing, Amazon item -> Release conversion, and
filter/sort logic using fake in-memory items, so they don't need real
Amazon credentials or network access.

## Notes and limits

- Amazon rate-limits the API (especially for new/low-volume Associates
  accounts); the app stops early and returns what it has if it gets
  throttled rather than failing outright.
- Not every catalog entry has a fully-specified release date; those items
  are still shown (sorted last) unless you pass `--require-date`.
- Respect Amazon's Associates Program Operating Agreement when using or
  displaying this data (e.g. pricing/availability can change, and cached
  data should not be presented as live).
