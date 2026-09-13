"""Fixtures for amazon_seller_extract tests.

Minimal HTML fragments that exercise the seller extraction patterns.
No live network, no provider calls.
"""

import json
import os

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "seller_extract")
os.makedirs(FIXTURE_DIR, exist_ok=True)


# 1. Standard dp page with Buy Box seller, fulfillment, and total sellers
FIXTURE_STANDARD = """<html>
<head><title>Test Product - Amazon.com</title></head>
<body>
<div id="bylineInfo">
    <span>Sold by <a href="/sp?seller=A123456789">TestSeller Inc</a></span>
</div>
<div id="availability">
    <span>Fulfilled by Amazon</span>
</div>
<div id="olp_feature_div">
    <span>New (5) from $19.99</span>
</div>
<span id="productTitle">Test Product Title</span>
<span class="a-offscreen">$19.99</span>
</body>
</html>"""

# 2. FBM seller (Ships from / Sold by pattern)
FIXTURE_FBM = """<html>
<head><title>Test Product FBM - Amazon.com</title></head>
<body>
<div id="bylineInfo">
    Sold by <a href="/sp?seller=B987654321">FBM Seller LLC</a>
</div>
<div id="availability">
    <span>Ships from</span> <span>FBM Seller LLC</span> <span>Sold by</span> <span>FBM Seller LLC</span>
</div>
<div id="olp_feature_div">
    <span>New (3) from $24.50</span>
</div>
<span id="productTitle">Test Product FBM</span>
<span class="a-offscreen">$24.50</span>
</body>
</html>"""

# 3. Amazon Retail (seller = Amazon.com)
FIXTURE_AMAZON_RETAIL = """<html>
<head><title>Test Product Amazon - Amazon.com</title></head>
<body>
<div id="bylineInfo">
    Sold by <a href="/sp?seller=ATVPDKIKX0DER">Amazon.com</a>
</div>
<div id="availability">
    <span>Fulfilled by Amazon</span>
</div>
<div id="olp_feature_div">
    <span>New (2) from $15.00</span>
</div>
<span id="productTitle">Test Product Amazon</span>
<span class="a-offscreen">$15.00</span>
</body>
</html>"""

# 4. Sparse page - minimal markers (no seller name, no fulfillment, no count)
FIXTURE_SPARSE = """<html>
<head><title>Sparse Product - Amazon.com</title></head>
<body>
<span id="productTitle">Sparse Product</span>
<span class="a-offscreen">$9.99</span>
</body>
</html>"""

# 5. Variant count patterns
FIXTURE_VARIANT_COUNTS = """<html>
<head><title>Variant Counts - Amazon.com</title></head>
<body>
<div id="bylineInfo">Sold by Variant Seller</div>
<div id="availability">Fulfilled by Amazon</div>
<div id="olp_feature_div">
    <span>(10 new offers)</span>
    <span>12 new from $22.00</span>
    <span>New (8)</span>
    <span>(5) new</span>
</div>
<span id="productTitle">Variant Counts</span>
<span class="a-offscreen">$22.00</span>
</body>
</html>"""

# 6. Other sellers present markers
FIXTURE_OTHER_SELLERS = """<html>
<head><title>Other Sellers - Amazon.com</title></head>
<body>
<div id="bylineInfo">Sold by Main Seller</div>
<div id="availability">Ships from Main Seller Sold by Main Seller</div>
<div id="aod-offer">Offer 1</div>
<div class="aod-container">
    <h3>Other sellers on Amazon</h3>
    <a>See All Buying Options</a>
</div>
<span id="productTitle">Other Sellers Present</span>
<span class="a-offscreen">$30.00</span>
</body>
</html>"""

# 7. CLP / brand landing page (no seller data)
FIXTURE_CLP = """<html>
<head><title>Brand Landing - Amazon.com</title></head>
<body>
<div class="clp-brand-header">Kirkland Signature</div>
<div class="product-grid">
    <div data-asin="B00BH3HPZW">Product 1</div>
    <div data-asin="B081THWMDK">Product 2</div>
</div>
</body>
</html>"""

# Expected results for each fixture
EXPECTED = {
    "standard": {
        "buy_box_seller_name": "TestSeller Inc",
        "buy_box_fulfillment": "FBA",
        "total_sellers": 5,
        "other_sellers_present": False,
        "lowest_price": 19.99,
    },
    "fbm": {
        "buy_box_seller_name": "FBM Seller LLC",
        "buy_box_fulfillment": "FBM",
        "total_sellers": 3,
        "other_sellers_present": False,
        "lowest_price": 24.50,
    },
    "amazon_retail": {
        "buy_box_seller_name": "Amazon.com",
        "buy_box_fulfillment": "Amazon",
        "total_sellers": 2,
        "other_sellers_present": False,
        "lowest_price": 15.00,
    },
    "sparse": {
        "buy_box_seller_name": None,
        "buy_box_fulfillment": "Unknown",
        "total_sellers": None,
        "other_sellers_present": False,
        "lowest_price": None,
    },
    "variant_counts": {
        "buy_box_seller_name": "Variant Seller",
        "buy_box_fulfillment": "FBA",
        "total_sellers": 10,  # First match wins: (10 new offers)
        "other_sellers_present": False,
        "lowest_price": None,  # No price in variant patterns
    },
    "other_sellers": {
        "buy_box_seller_name": "Main Seller",
        "buy_box_fulfillment": "FBM",
        "total_sellers": None,  # No "New (N) from" pattern
        "other_sellers_present": True,
        "lowest_price": None,
    },
    "clp": {
        "buy_box_seller_name": None,
        "buy_box_fulfillment": "Unknown",
        "total_sellers": None,
        "other_sellers_present": False,
        "lowest_price": None,
    },
}

# Write fixture files
fixtures = {
    "standard.html": FIXTURE_STANDARD,
    "fbm.html": FIXTURE_FBM,
    "amazon_retail.html": FIXTURE_AMAZON_RETAIL,
    "sparse.html": FIXTURE_SPARSE,
    "variant_counts.html": FIXTURE_VARIANT_COUNTS,
    "other_sellers.html": FIXTURE_OTHER_SELLERS,
    "clp.html": FIXTURE_CLP,
}

for name, content in fixtures.items():
    with open(os.path.join(FIXTURE_DIR, name), "w", encoding="utf-8") as f:
        f.write(content)

# Write expected.json
with open(os.path.join(FIXTURE_DIR, "expected.json"), "w", encoding="utf-8") as f:
    json.dump(EXPECTED, f, indent=2)

print("Fixtures written to:", FIXTURE_DIR)
print("Files:", list(fixtures.keys()) + ["expected.json"])