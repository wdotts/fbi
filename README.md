# New CD Release Tracker

A small app that finds new CD releases, sorted by release date, across
three sources — **MusicBrainz** and **Discogs** (free, official, open
music-metadata APIs, no approval needed) and, if you have access,
**Amazon's Creators API**. It ships as both a CLI and a local web UI,
sharing the same search logic.

This app only talks to these services through their official,
authenticated/public APIs. It does not scrape any website or automate a
logged-in browser session, which would violate those sites' Terms of
Service (Amazon's explicitly prohibit "the use of any robot, spider,
scraper, or other automated means"). See "Why not just scrape Amazon?"
below for more on that tradeoff.

## Quick start (no account needed)

```bash
cd amazon_cd_tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional - MusicBrainz works with nothing filled in
python -m src.cli search --date 2026-08-01
```

That's it — MusicBrainz, the default source, needs no signup, no API key,
no waiting period. Discogs and Amazon are additional, optional sources;
see below for what each needs.

## The three sources

| Source | Setup needed | Exact-date completeness | Notes |
|---|---|---|---|
| **MusicBrainz** (default) | None (an `.env` contact email is recommended, not required) | Best — true server-side date-range search, no fixed results cap | Free, open, community-maintained |
| **Discogs** | None (a free personal token raises the rate limit) | Good, but capped — see below | Also a real marketplace, so results include pricing |
| **Amazon** | Creators API credentials (gated behind Amazon's approval) | Best-effort, capped at 100 results per search | Only source most people can't get instant access to |

Pick sources with `--sources musicbrainz,discogs,amazon` (CLI) or the
checkboxes on the web UI. Default is `musicbrainz` alone, since it's the
fastest and most complete for a specific date.

### MusicBrainz

No credentials required. Set `APP_CONTACT_EMAIL` in `.env` so this app's
requests identify themselves properly (MusicBrainz's etiquette asks
automated clients to do this; it isn't enforced, but it's the polite
default and reduces the odds of being rate-limited harder).

MusicBrainz's search API supports a **real server-side date-range filter**
(`date:[since TO until]`) and has no fixed results cap — this app pages
through everything it reports (bounded by `--musicbrainz-max-results`,
default 500, as a safety valve), so it's the most complete way to answer
"what came out on this exact date."

### Discogs

No credentials required either, but useful ones exist: set `DISCOGS_TOKEN`
(a free personal access token from
https://www.discogs.com/settings/developers) to raise the rate limit from
~25 to ~60 requests/minute.

Discogs' *search* endpoint only reports a release's **year**, not a full
date — there's no way around that, it's how their API works. To confirm an
exact day, this app fetches each candidate release's full detail page (one
extra request per candidate, capped by `--discogs-candidates`, default 30)
and checks its precise `released` field. That makes Discogs noticeably
slower than MusicBrainz and is why it's opt-in rather than a default. Pass
`--no-discogs-details` to skip the detail lookups (much faster, but you
only get year-precision, unconfirmed matches).

### Amazon

Optional, and gated: Amazon requires an approved Associates account with
Creators API access (typically a track record of qualifying referred
sales) before it issues `AMAZON_CREDENTIAL_ID`/`AMAZON_CREDENTIAL_SECRET`.
If you don't have these, just don't put `amazon` in `--sources` — the rest
of the app works fully without it. See `.env.example` for what to fill in
if/when you do have access.

Even without those credentials, if you set `AMAZON_PARTNER_TAG`, this app
can still build real Amazon links for items MusicBrainz/Discogs already
know the ASIN for (see "Cart and wishlist" below).

## Usage: command line

```bash
python -m src.cli search --date 2026-08-01
python -m src.cli search --keywords "jazz" --days 45
python -m src.cli search --sources musicbrainz,discogs,amazon --date 2026-08-01
```

Key flags:

- `--date YYYY-MM-DD` — releases on exactly that day; ignores `--limit` so
  every match is shown, and skips Amazon's page cap (see "Amazon" above)
- `--days N` / `--since` / `--until` — a date range instead of one exact day
- `--sources` — comma list from `musicbrainz`, `discogs`, `amazon` (default: `musicbrainz`)
- `--keywords "artist or genre"` — narrow the search
- `--formats CD` — comma list of formats to match on MusicBrainz/Discogs (default: `CD`)
- `--cart-links` — print a real Amazon cart/search link for each result
- `--save-wishlist` — save every displayed result to your local wishlist
- `--json` — machine-readable output
- Amazon-only: `--browse-node-id`, `--pages`, `--min-price`, `--max-price`
- Discogs-only: `--discogs-candidates`, `--no-discogs-details`
- MusicBrainz-only: `--musicbrainz-max-results`

### Cart and wishlist

```bash
python -m src.cli wishlist add B000TEST      # look up an Amazon ASIN and save it
python -m src.cli wishlist list              # show saved items (key shown as e.g. musicbrainz:<mbid>)
python -m src.cli wishlist remove musicbrainz:1234-5678
python -m src.cli wishlist cart-link         # one Amazon link adding every ASIN-linked item to your real cart
```

See "Cart and wishlist, and what they actually do" below.

## Usage: web app

```bash
python -m src.webapp
```

Open http://127.0.0.1:5000/. Filters are also query parameters
(`keywords`, `days`, `date`, `sources`), and results are available as JSON
at `/api/releases`. Each result has an Amazon link (a real **Add to Cart**
when we know its ASIN, otherwise a plain **Find on Amazon** search link)
and a **Wishlist** button (saved locally); saved items live at
`/wishlist`, including a link to add every ASIN-linked one to your Amazon
cart at once.

## Why not just scrape Amazon?

Amazon's Conditions of Use explicitly prohibit automated access
("robot, spider, scraper, or other automated means"), and its `robots.txt`
disallows crawling almost the entire site. That's true with or without a
login — automating a login specifically adds the risk of tripping
Amazon's bot detection with your real account. This app sticks to
official/public APIs (MusicBrainz, Discogs, and Amazon's own Creators API)
instead.

## How it works

Three independent client modules each return the same `Release` shape
(`src/releases.py`):

- `src/musicbrainz_client.py` — `GET /ws/2/release/` with a Lucene
  `date:[since TO until]` range query, paginated.
- `src/discogs_client.py` — `GET /database/search`, optionally followed by
  per-candidate detail fetches to confirm an exact date.
- `src/amazon_client.py` — `SearchItems` against `SearchIndex=Music`
  sorted by `NewestArrivals`, then filtered client-side (no server-side
  date filter exists in Amazon's API, and it caps at 100 results/search).

`src/aggregate.py` runs whichever sources are selected, merges their
results, and applies one shared, exact-day filter/sort
(`releases.filter_and_sort_releases`). Results are **not** deduplicated
*across* sources (e.g. the same album from both MusicBrainz and Discogs
will appear twice, tagged with different `source` badges) — matching the
same physical release across catalogs with different IDs is a real,
error-prone problem this app doesn't attempt to solve automatically.

A release date is only ever treated as day-precise when the source
reports a full `YYYY-MM-DD` (`releases.parse_release_date`); a bare year
or year-month is kept for display (`release_date_text`) but never silently
rounded to a specific day, since that would corrupt exact-date filtering.

### How complete is "everything" for `--date`?

- **MusicBrainz**: genuinely close to complete — it's the only one of the
  three with a real server-side date-range filter and no fixed cap.
- **Discogs**: complete *within* the candidate cap (`--discogs-candidates`,
  default 30); a date with more CD-format candidates than that in Discogs'
  catalog will miss some.
- **Amazon**: best-effort only, capped at 100 results per search, ordered
  by catalog-listing recency rather than release date. Reliable for recent
  dates, less so for older ones — the CLI/web UI print a note when the
  100-item cap is hit. This is a hard limit of Amazon's public API, not
  something this app can work around.

### Cart and wishlist, and what they actually do

None of these services offer a public API for writing to a customer's
*real* cart or wish list — that requires the user's own logged-in session,
separate from any API credentials this app uses to search a catalog. So:

- **Add to Cart** uses Amazon's real, documented redirect link
  (`https://www.<marketplace>/gp/aws/cart/add.html?...`, `src/cart.py`)
  whenever we know both an item's Amazon ASIN and you've set
  `AMAZON_PARTNER_TAG`. Amazon's own catalog search always has an ASIN;
  MusicBrainz releases sometimes do too (contributors link their entries to
  Amazon). Opening the link adds the item to whichever Amazon account
  you're logged into in your browser — a real write to your real cart.
  Without a known ASIN, the button instead links to a plain Amazon search
  for the artist/title (also a real, ordinary link, just not a direct add).
- **Wishlist** is **local to this app** (JSON in `data/`, not synced to
  Amazon or anywhere else), because there's no current public way for a
  third-party app to write to your actual Amazon wish list. Every item
  keeps its real source link, and `wishlist cart-link` builds one
  add-to-cart link for every ASIN-linked saved item at once.

## Running tests

```bash
pip install pytest
python -m pytest tests/
```

Tests cover date-precision parsing, each source's response parsing
(MusicBrainz/Discogs HTTP calls are mocked), the multi-source aggregator,
cart-link generation, and wishlist storage — all using fake data or a temp
directory, so they don't need real network access or credentials.

## Notes and limits

- Not every catalog entry has a fully-specified release date; those items
  are still shown (sorted last) unless you pass `--require-date`.
- The same physical release can appear once per source that has it, not
  merged into one row (see "How it works" above).
- Discogs and MusicBrainz are rate-limited; large date ranges with many
  matches will take longer to fetch, especially with Discogs detail
  lookups on.
- If you do use the Amazon source, respect Amazon's Associates Program
  Operating Agreement when displaying its data (pricing/availability can
  change; don't present cached data as live).
