from src.cart import cart_add_url, cart_add_url_multi, marketplace_domain


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
