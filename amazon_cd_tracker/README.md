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
python -m src.cli search --days 30
```

### Get everything released on one date

```bash
python -m src.cli search --date 2026-08-01
```

`--date` shows releases on exactly that day. It automatically fetches
Amazon's full 10-page result depth for the search and shows every match
(no `--limit`), instead of the smaller default used for open-ended
browsing. See "How complete is 'everything'?" below for the real limit on
how exhaustive this can be.

Other search flags:

- `--keywords "artist or genre"` — narrow the search
- `--days N` — only show releases from the last N days (default 60; ignored if `--date` is set)
- `--since YYYY-MM-DD` / `--until YYYY-MM-DD` — explicit date range (ignored if `--date` is set)
- `--browse-node-id ID` — restrict to a specific Amazon browse node (e.g. a
  "CDs & Vinyl" category node) if you want to exclude digital-only music
- `--pages N` — how many pages of results to fetch from Amazon (1-10,
  default 3; each page is one API call; ignored if `--date` is set)
- `--cart-links` — print a real "add to cart" URL for each result
- `--save-wishlist` — save every displayed result to your local wishlist
- `--json` — print machine-readable JSON instead of a table
- `--limit N` — cap how many releases are shown (ignored if `--date` is set)

Example:

```bash
python -m src.cli search --keywords "jazz" --days 45 --pages 5
```

### Cart and wishlist

```bash
python -m src.cli wishlist add B000TEST      # look up an ASIN and save it
python -m src.cli wishlist list              # show saved items
python -m src.cli wishlist remove B000TEST   # drop an item
python -m src.cli wishlist cart-link         # one Amazon link that adds your whole wishlist to your real cart
```

See "Cart and wishlist, and what they actually do" below for what's real
(your actual Amazon cart) versus local-only (the wishlist).

## Usage: web app

```bash
python -m src.webapp
```

Then open http://127.0.0.1:5000/. The same filters are available as query
parameters (`keywords`, `days`, `date`), and results are also available as
JSON at `/api/releases`. Each result has an **Add to Cart** button (a real
Amazon link) and a **Wishlist** button (saved locally); your saved items
live at `/wishlist`, including a link to add all of them to your Amazon
cart at once.

## How it works

`src/amazon_client.py` calls `SearchItems` against Amazon's Music catalog
(`SearchIndex=Music`), asking for `NewestArrivals` ordering and requesting
the `ItemInfo.ProductInfo` resource, which is where Amazon reports a
release's `ReleaseDate`. `src/releases.py` parses that date and is
responsible for the actual "sort/filter by date" behavior this app is
for — `NewestArrivals` reflects Amazon's catalog listing order, not
strictly the release date, so results are re-sorted client-side by parsed
release date (newest first) and filtered to your requested date range.

### How complete is "everything" for `--date`?

Amazon's `SearchItems` API has **no server-side "filter by release date"
parameter**, and caps any single search at 10 pages of 10 results (100
items), returned in whatever order the chosen sort produces. This app asks
for `NewestArrivals` order and filters those 100 items down to the exact
date you asked for — that's the most complete answer this API can give.

In practice:

- For **recent dates** (roughly the last couple of months), this is
  reliable: `NewestArrivals` surfaces recently-catalogued items first, so
  a day's new CDs are very likely within that 100-item window.
- For **older dates**, it gets less reliable: thousands of newer catalog
  entries can exist between "now" and an old date, so 100 results ordered
  by recency may never reach that far back. The CLI and web UI both flag
  this (`Scanned N Amazon catalog listing(s)...`) whenever the scan hit
  the 100-item cap, and suggest adding `--keywords` (an artist or label) to
  dig further into the catalog for that specific date — a keyword-scoped
  search is a different, smaller pool of results, so it can reach items a
  broad unscoped search can't.

This is a limit of Amazon's public API, not something this app can work
around.

### Cart and wishlist, and what they actually do

Amazon doesn't offer a public API for writing to a customer's real
Amazon cart or wish list — those require the user's own logged-in Amazon
session, which is separate from the Associates/Creators API credentials
this app uses to search the catalog. So:

- **Add to Cart** is a real, Amazon-documented redirect link
  (`https://www.<marketplace>/gp/aws/cart/add.html?...`, built in
  `src/cart.py`) that opens Amazon in your browser and adds the item to
  whichever Amazon account you're logged into there. This actually puts
  the CD in your real cart.
- **Wishlist** is **local to this app** (stored as JSON in `data/`, not
  synced to Amazon), because there's no current public, documented way for
  a third-party app to write to your actual Amazon wish list. Every saved
  item still links to its real Amazon product page, and `wishlist
  cart-link` builds one add-to-cart link for your whole saved list, so you
  can turn it into a real order in one click when you're ready.

## Running tests

```bash
pip install pytest
python -m pytest tests/
```

The tests cover date parsing, Amazon item -> Release conversion,
filter/sort logic, cart-link generation, and wishlist storage, all using
fake in-memory items or a temp directory, so they don't need real Amazon
credentials or network access.

## Notes and limits

- Amazon rate-limits the API (especially for new/low-volume Associates
  accounts); the app stops early and returns what it has if it gets
  throttled rather than failing outright.
- Not every catalog entry has a fully-specified release date; those items
  are still shown (sorted last) unless you pass `--require-date`.
- Respect Amazon's Associates Program Operating Agreement when using or
  displaying this data (e.g. pricing/availability can change, and cached
  data should not be presented as live).
