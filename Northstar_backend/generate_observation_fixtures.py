"""Generate synthetic HTML fixtures for Chrome Connect observation layer testing.

Creates 20+ HTML snapshots representing typical pages from allowlisted sites.
These are synthetic (not real page captures) for Phase 1 testing only.
Tagged source: synthetic.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chromeconnect_observation as obs

# Synthetic HTML templates for allowed sites
FIXTURES = {
    "costco_product_page": """
<html><head><title>Costco - Product Detail</title></head><body>
  <nav><a href="/">Home</a><a href="/cart">Cart (0)</a></nav>
  <h1>Kirkland Signature Organic Extra Virgin Olive Oil, 2L</h1>
  <div class="price">$14.99</div>
  <div class="item-number">Item #1234567</div>
  <button id="add-to-cart">Add to Cart</button>
  <button id="check-availability">Check Warehouse Availability</button>
  <div class="description">Cold-pressed olive oil from Italy.</div>
  <div class="reviews"><a href="#reviews">4.5 stars (234 reviews)</a></div>
  <select name="qty"><option>1</option><option>2</option><option>3</option></select>
  <a href="/similar">Similar Items</a>
</body></html>
""",
    "costco_search_results": """
<html><head><title>Costco - Search Results</title></head><body>
  <h1>Search: olive oil</h1>
  <ul class="results">
    <li><a href="/p1">Kirkland Olive Oil 2L</a><span class="price">$14.99</span><button>Add</button></li>
    <li><a href="/p2">Pompeian Olive Oil 1.5L</a><span class="price">$12.49</span><button>Add</button></li>
    <li><a href="/p3">California Olive Ranch 500ml</a><span class="price">$8.99</span><button>Add</button></li>
    <li><a href="/p4">Bertolli Olive Oil 1L</a><span class="price">$9.99</span><button>Add</button></li>
    <li><a href="/p5">Filippo Berio 750ml</a><span class="price">$7.99</span><button>Add</button></li>
  </ul>
  <a href="/page2">Next Page</a>
</body></html>
""",
    "sellersprite_dashboard": """
<html><head><title>SellerSprite - Dashboard</title></head><body>
  <nav><a href="/dashboard">Dashboard</a><a href="/research">Research</a><a href="/export">Export</a></nav>
  <h1>Product Research</h1>
  <input type="text" name="keyword" placeholder="Enter keyword" />
  <button id="search-btn">Search</button>
  <table>
    <tr><th>ASIN</th><th>Title</th><th>Price</th><th>BSR</th><th>Sales</th></tr>
    <tr><td>B0ABC123</td><td>Turmeric Powder 16oz</td><td>$12.99</td><td>5432</td><td>340</td><td><button>Export</button></td></tr>
    <tr><td>B0DEF456</td><td>Ginger Root 8oz</td><td>$8.99</td><td>12045</td><td>120</td><td><button>Export</button></td></tr>
    <tr><td>B0GHI789</td><td>Cinnamon 4oz</td><td>$6.49</td><td>8901</td><td>210</td><td><button>Export</button></td></tr>
  </table>
  <button id="export-all">Export All</button>
  <a href="/next">Next Page</a>
</body></html>
""",
    "selleramp_analysis": """
<html><head><title>SellerAmp - SAS</title></head><body>
  <h1>Sales Analysis</h1>
  <div class="asin-input"><input type="text" name="asin" placeholder="Enter ASIN" /><button>Analyze</button></div>
  <div class="results">
    <div class="metric"><span>Buy Box Price</span><span>$15.99</span></div>
    <div class="metric"><span>Amazon Fees</span><span>$4.50</span></div>
    <div class="metric"><span>Net Profit</span><span>$6.49</span></div>
    <div class="metric"><span>ROI</span><span>68%</span></div>
    <div class="metric"><span>BSR</span><span>3,456</span></div>
    <div class="metric"><span>Sellers</span><span>12</span></div>
  </div>
  <a href="/history">View History</a>
  <button id="save">Save Analysis</button>
</body></html>
""",
    "agentconnect_home": """
<html><head><title>AgentConnect</title></head><body>
  <nav><a href="/">Home</a><a href="/docs">Docs</a><a href="/app">App</a></nav>
  <h1>AgentConnect - Multi-Agent Platform</h1>
  <p>Connect AI agents across Slack, Telegram, and GitHub.</p>
  <a href="/docs/getting-started">Getting Started</a>
  <a href="/docs/api">API Reference</a>
  <button id="sign-up">Sign Up Free</button>
  <div class="features">
    <div><h3>Daemons</h3><p>Background agent processes</p></div>
    <div><h3>Relay</h3><p>Message routing between agents</p></div>
    <div><h3>Control Plane</h3><p>Central management</p></div>
  </div>
</body></html>
""",
    "packify_home": """
<html><head><title>Packify - Package Design</title></head><body>
  <nav><a href="/">Home</a><a href="/design">Design</a><a href="/pricing">Pricing</a></nav>
  <h1>AI Package Design</h1>
  <p>Design product packaging with AI.</p>
  <button id="start-design">Start Designing</button>
  <div class="templates">
    <div><a href="/template/box">Box</a></div>
    <div><a href="/template/bottle">Bottle</a></div>
    <div><a href="/template/pouch">Pouch</a></div>
    <div><a href="/template/can">Can</a></div>
    <div><a href="/template/label">Label</a></div>
  </div>
  <a href="/gallery">View Gallery</a>
</body></html>
""",
    "costco_business_delivery": """
<html><head><title>Costco Business Delivery</title></head><body>
  <nav><a href="/">Home</a><a href="/search">Search</a><a href="/account">Account</a></nav>
  <h1>Business Delivery</h1>
  <input type="search" name="q" placeholder="Search products" />
  <button type="submit">Search</button>
  <div class="categories">
    <a href="/cat/office">Office Supplies</a>
    <a href="/cat/cleaning">Cleaning</a>
    <a href="/cat/food">Food & Beverage</a>
    <a href="/cat/paper">Paper Products</a>
  </div>
  <div class="deals">
    <a href="/deal/1">Bulk Paper Towels - $24.99</a>
    <a href="/deal/2">Office Chairs - $149.99</a>
  </div>
</body></html>
""",
    "oracle_home": """
<html><head><title>Oracle</title></head><body>
  <nav><a href="/">Home</a><a href="/products">Products</a><a href="/cloud">Cloud</a></nav>
  <h1>Oracle Cloud Infrastructure</h1>
  <p>Enterprise cloud solutions.</p>
  <a href="/try-free">Try Free</a>
  <a href="/contact">Contact Sales</a>
  <div class="products">
    <a href="/product/database">Database</a>
    <a href="/product/compute">Compute</a>
    <a href="/product/storage">Storage</a>
  </div>
</body></html>
""",
    "dash_cloudflare": """
<html><head><title>Cloudflare Dashboard</title></head><body>
  <h1>Cloudflare Dashboard</h1>
  <div class="login-prompt">
    <p>Sign in to manage your account.</p>
    <input type="email" name="email" placeholder="Email" />
    <input type="password" name="password" placeholder="Password" />
    <button type="submit">Log In</button>
  </div>
  <a href="/sign-up">Create Account</a>
</body></html>
""",
    "account_squarespace": """
<html><head><title>Squarespace - Account</title></head><body>
  <h1>Sign In to Squarespace</h1>
  <div class="login-form">
    <input type="email" name="email" placeholder="Email address" />
    <input type="password" name="password" placeholder="Password" />
    <button type="submit">Log In</button>
  </div>
  <a href="/forgot-password">Forgot password?</a>
  <a href="/signup">Create account</a>
</body></html>
""",
    "primenationaldistribution": """
<html><head><title>Prime National Distribution</title></head><body>
  <h1>Prime National Distribution</h1>
  <div class="login-prompt">
    <p>Member login required.</p>
    <input type="text" name="username" placeholder="Username" />
    <input type="password" name="password" placeholder="Password" />
    <button type="submit">Sign In</button>
  </div>
  <p>Wholesale pricing available for members.</p>
</body></html>
""",
    "alibaba_search": """
<html><head><title>Alibaba - Search</title></head><body>
  <nav><a href="/">Home</a><a href="/products">Products</a><a href="/suppliers">Suppliers</a></nav>
  <h1>Search Results: turmeric powder</h1>
  <div class="product-card">
    <a href="/product/1">Organic Turmeric Powder 1kg</a>
    <span class="price">$3.50-5.00</span>
    <span class="moq">Min. Order: 100 kg</span>
    <button>Contact Supplier</button>
  </div>
  <div class="product-card">
    <a href="/product/2">Turmeric Powder Bulk 25kg</a>
    <span class="price">$2.80-4.00</span>
    <span class="moq">Min. Order: 500 kg</span>
    <button>Contact Supplier</button>
  </div>
  <div class="product-card">
    <a href="/product/3">Premium Turmeric 5kg</a>
    <span class="price">$4.20-6.00</span>
    <span class="moq">Min. Order: 50 kg</span>
    <button>Contact Supplier</button>
  </div>
  <a href="/page2">Next</a>
</body></html>
""",
    "northstar_ui_home": """
<html><head><title>NorthstarOS</title></head><body>
  <nav><a href="/ui/">Home</a><a href="/ui/product-finder">Product Finder</a><a href="/ui/golden-goose">Golden Goose</a></nav>
  <main>
    <h1>Dashboard</h1>
    <div class="metric-tiles">
      <div class="tile"><span>Revenue</span><span>$12,345</span></div>
      <div class="tile"><span>Margin</span><span>70.2%</span></div>
      <div class="tile"><span>Products</span><span>42</span></div>
    </div>
    <div data-testid="chat-input"><input type="text" placeholder="Ask anything..." /></div>
  </main>
</body></html>
""",
    "northstar_signin": """
<html><head><title>NorthstarOS - Sign In</title></head><body>
  <div class="signin-form">
    <input id="signin-id" type="text" placeholder="Email" />
    <input id="signin-pw" type="password" placeholder="Password" />
    <button type="submit">Sign In</button>
  </div>
</body></html>
""",
    "empty_page": """
<html><head><title>Empty</title></head><body>
  <p>No interactive elements here.</p>
</body></html>
""",
    "canvas_page": """
<html><head><title>Canvas App</title></head><body>
  <canvas id="main-canvas" width="800" height="600"></canvas>
  <p>This page uses canvas rendering.</p>
</body></html>
""",
    "heavy_js_page": """
<html><head><title>JS Heavy</title></head><body>
  <div id="app"></div>
  <script>
    // Dynamic content loaded via JS
    document.getElementById('app').innerHTML = '<button>Dynamic Button</button>';
  </script>
</body></html>
""",
    "login_page_generic": """
<html><head><title>Login</title></head><body>
  <div class="login-form">
    <h2>Sign In</h2>
    <input type="email" name="email" placeholder="Email" />
    <input type="password" name="password" placeholder="Password" />
    <button type="submit">Log In</button>
    <a href="/forgot">Forgot password?</a>
    <a href="/signup">Create account</a>
  </div>
</body></html>
""",
    "product_listing": """
<html><head><title>Product Listing</title></head><body>
  <h1>Product Catalog</h1>
  <div class="filters">
    <select name="category"><option>All</option><option>Electronics</option><option>Home</option></select>
    <input type="text" name="search" placeholder="Search products" />
    <button>Filter</button>
  </div>
  <div class="products">
    <div class="product"><a href="/p1">Widget A</a><span class="price">$19.99</span><button>Add to Cart</button></div>
    <div class="product"><a href="/p2">Widget B</a><span class="price">$24.99</span><button>Add to Cart</button></div>
    <div class="product"><a href="/p3">Widget C</a><span class="price">$14.99</span><button>Add to Cart</button></div>
  </div>
  <div class="pagination"><a href="/page2">Next</a></div>
</body></html>
""",
    "large_table": """
<html><head><title>Data Table</title></head><body>
  <h1>Sales Data</h1>
  <table>
    <thead><tr><th>Date</th><th>Product</th><th>Units</th><th>Revenue</th></tr></thead>
    <tbody>
""" + "\n".join(
    f"      <tr><td>2026-10-{i:02d}</td><td>Product {i}</td><td>{i*10}</td><td>${i*100}.00</td></tr>"
    for i in range(1, 51)
) + """
    </tbody>
  </table>
</body></html>
""",
    "minimal_page": """
<html><head><title>Minimal</title></head><body>
  <h1>Hello</h1>
  <p>Just text, no interactive elements.</p>
</body></html>
""",
    "form_page": """
<html><head><title>Contact Form</title></head><body>
  <h1>Contact Us</h1>
  <form action="/submit" method="POST">
    <input type="text" name="name" placeholder="Name" required />
    <input type="email" name="email" placeholder="Email" required />
    <textarea name="message" placeholder="Message"></textarea>
    <select name="topic">
      <option>General</option>
      <option>Support</option>
      <option>Sales</option>
    </select>
    <button type="submit">Send</button>
  </form>
</body></html>
""",
    "navigation_page": """
<html><head><title>Navigation Test</title></head><body>
  <nav>
    <a href="/">Home</a>
    <a href="/about">About</a>
    <a href="/products">Products</a>
    <a href="/contact">Contact</a>
    <a href="/blog">Blog</a>
  </nav>
  <main><h1>Welcome</h1><p>Navigation test page.</p></main>
  <footer><a href="/privacy">Privacy</a><a href="/terms">Terms</a></footer>
</body></html>
""",
}

if __name__ == "__main__":
    count = 0
    for name, html_text in FIXTURES.items():
        path = obs.save_fixture(name, html_text.strip())
        count += 1
        snap = obs.snapshot(html_text.strip())
        print(f"{name}: {snap['total_elements']} elements, {snap['token_count']} tokens, truncated={snap['truncated']}")
    print(f"\nTotal fixtures saved: {count}")
    print(f"Fixture dir: {obs.FIXTURE_DIR}")
    print(f"Fixtures available: {len(obs.list_fixtures())}")
