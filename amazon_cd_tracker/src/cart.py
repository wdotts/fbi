from __future__ import annotations

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
