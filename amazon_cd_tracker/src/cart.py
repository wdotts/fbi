from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

# Amazon's documented Associates "Add to Cart" form: a plain GET link to
# https://www.<marketplace>/gp/aws/cart/add.html with an AssociateTag and
# numbered ASIN.N / Quantity.N pairs. Opening it in a browser adds the
# item(s) to whichever Amazon account the browser is logged into - this is
# a real write to the user's actual cart, not something this app can do
# on its own without the user's Amazon login.
MARKETPLACE_DOMAINS = {
    "US": "amazon.com",
    "UK": "amazon.co.uk",
    "DE": "amazon.de",
    "FR": "amazon.fr",
    "JP": "amazon.co.jp",
    "CA": "amazon.ca",
    "IT": "amazon.it",
    "ES": "amazon.es",
    "IN": "amazon.in",
    "MX": "amazon.com.mx",
    "BR": "amazon.com.br",
    "AU": "amazon.com.au",
    "NL": "amazon.nl",
    "SE": "amazon.se",
    "PL": "amazon.pl",
    "TR": "amazon.com.tr",
    "AE": "amazon.ae",
    "SA": "amazon.sa",
    "SG": "amazon.sg",
    "BE": "amazon.com.be",
}

# Keep generated URLs a safe length for browsers/links.
MAX_ITEMS_PER_CART_LINK = 25


def marketplace_domain(country: str) -> str:
    return MARKETPLACE_DOMAINS.get((country or "US").upper(), "amazon.com")


def cart_add_url(asin: str, country: str, partner_tag: str, quantity: int = 1) -> str:
    domain = marketplace_domain(country)
    params = {"AssociateTag": partner_tag, "ASIN.1": asin, "Quantity.1": str(quantity)}
    return f"https://www.{domain}/gp/aws/cart/add.html?{urlencode(params)}"


def cart_add_url_multi(asins: list[str], country: str, partner_tag: str) -> str:
    """One add-to-cart link covering up to MAX_ITEMS_PER_CART_LINK ASINs."""
    domain = marketplace_domain(country)
    params = {"AssociateTag": partner_tag}
    for i, asin in enumerate(asins[:MAX_ITEMS_PER_CART_LINK], start=1):
        params[f"ASIN.{i}"] = asin
        params[f"Quantity.{i}"] = "1"
    return f"https://www.{domain}/gp/aws/cart/add.html?{urlencode(params)}"


def amazon_search_url(query: str, country: str = "US", partner_tag: Optional[str] = None) -> str:
    """A plain Amazon search results link - not automated access, just the
    same URL a person gets by typing into Amazon's search box. Used when
    we don't have an ASIN to build a real add-to-cart link with (e.g. a
    MusicBrainz/Discogs result with no known Amazon match)."""
    domain = marketplace_domain(country)
    params = {"k": query}
    if partner_tag:
        params["tag"] = partner_tag
    return f"https://www.{domain}/s?{urlencode(params)}"


def cart_url_for(
    asin: Optional[str],
    artist: Optional[str],
    title: str,
    country: str,
    partner_tag: Optional[str],
) -> str:
    """The best available Amazon link for an item: a real add-to-cart link
    when we have both an ASIN and a partner tag, otherwise a plain search
    link so there's still something useful to click."""
    if asin and partner_tag:
        return cart_add_url(asin, country, partner_tag)
    query = f"{artist} {title}".strip() if artist else title
    return amazon_search_url(query, country, partner_tag)
