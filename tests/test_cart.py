from src.cart import amazon_search_url, cart_add_url, cart_add_url_multi, cart_url_for, marketplace_domain


def test_marketplace_domain_known_and_unknown():
    assert marketplace_domain("US") == "amazon.com"
    assert marketplace_domain("uk") == "amazon.co.uk"
    assert marketplace_domain("ZZ") == "amazon.com"


def test_cart_add_url_contains_required_params():
    url = cart_add_url("B000TEST", "US", "mytag-20")
    assert url.startswith("https://www.amazon.com/gp/aws/cart/add.html?")
    assert "AssociateTag=mytag-20" in url
    assert "ASIN.1=B000TEST" in url
    assert "Quantity.1=1" in url


def test_cart_add_url_multi_numbers_each_item_and_caps_length():
    asins = [f"ASIN{i}" for i in range(30)]
    url = cart_add_url_multi(asins, "UK", "mytag-21")
    assert url.startswith("https://www.amazon.co.uk/gp/aws/cart/add.html?")
    assert "ASIN.1=ASIN0" in url
    assert "ASIN.25=ASIN24" in url
    assert "ASIN.26=" not in url


def test_amazon_search_url_includes_query_and_optional_tag():
    url = amazon_search_url("Radiohead OK Computer", "US")
    assert url.startswith("https://www.amazon.com/s?")
    assert "k=Radiohead" in url
    assert "tag=" not in url

    tagged = amazon_search_url("Radiohead OK Computer", "US", partner_tag="mytag-20")
    assert "tag=mytag-20" in tagged


def test_cart_url_for_prefers_real_cart_link_when_asin_and_tag_present():
    url = cart_url_for("B000TEST", "Radiohead", "OK Computer", "US", "mytag-20")
    assert url.startswith("https://www.amazon.com/gp/aws/cart/add.html?")
    assert "ASIN.1=B000TEST" in url


def test_cart_url_for_falls_back_to_search_without_asin_or_tag():
    no_asin = cart_url_for(None, "Radiohead", "OK Computer", "US", "mytag-20")
    assert no_asin.startswith("https://www.amazon.com/s?")

    no_tag = cart_url_for("B000TEST", "Radiohead", "OK Computer", "US", None)
    assert no_tag.startswith("https://www.amazon.com/s?")
