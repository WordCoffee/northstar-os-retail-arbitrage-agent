"""Rebuild costco-items.csv cleanly and search for correct matches."""
import csv
import sys
sys.path.insert(0, '.')
from costco_api_client import _search_openwebninja

# --- Step 1: Rewrite CSV removing malformed appended rows ---
csv_path = '../data/costco-items.csv'
clean_rows = []
with open(csv_path, 'r', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        # Keep only well-formed 2-column rows (item_name, costco_cost)
        if len(row) >= 2 and row[0] and not row[0].startswith('B0'):
            clean_rows.append(row)
        elif len(row) >= 2 and row[0] and row[1]:
            # A row that is ASIN-first is our malformed append -> drop
            continue

with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(clean_rows)
print('Cleaned CSV: kept ' + str(len(clean_rows)) + ' rows')

# --- Step 2: Search for the CORRECT Costco items matching actual Amazon titles ---
searches = [
    # Amazon title asin -> real product, search terms
    ('B00JQRFOTA', 'KIRKLAND Signature One Per Day Super B-Complex with Electrolytes,500 tablets', 'Kirkland Super B-Complex'),
    ('B077LCPQ34', 'KIRKLAND Signature One Per Day Super B-Complex with Electrolytes,500 tablets', 'Kirkland Super B-Complex'),
    ('B08B5GZXHN', 'KIRKLAND Kirkland Signature Organic Extra Virgin Olive Oil 2L Set of 2', 'Kirkland Organic Extra Virgin Olive Oil 2L'),
    ('B0D9B4WRQT', 'Generic BLUE RIBBON Kirkland Signature 2-Ply Bath Tissue, 30 Rolls 380', 'Kirkland Bath Tissue 2-Ply 30'),
    ('B07N6YF2SF', 'KIRKLAND Signature Wild Alaskan Fish Oil 1400 mg, 230 Softgels', 'Kirkland Wild Alaskan Fish Oil 1400'),
    ('B01CZ637O2', 'KIRKLAND Kirkland Signature Glucosamine with MSM, 375 Tablets', 'Kirkland Glucosamine MSM 375'),
    ('B08JJV9M86', 'KIRKLAND Kirkland Signature Women 50+ Multivitamin, 365 Tablets', 'Kirkland Women 50 Multivitamin'),
    ('B0H9GL43LZ', "KIRKLAND Signature Men's Water Resistant Stretch 5 Pocket Pant", 'Kirkland Mens Stretch Pant'),
    ('B0FVWFFTYV', "KIRKLAND Signature Men's Short Sleeve Pima Cotton Polo Shirt", 'Kirkland Pima Polo'),
    ('B0H1Z5D4LC', "KIRKLAND Signature Women's Travel Pant", 'Kirkland Women Travel Pant'),
    ('B003FGTTUI', 'KIRKLAND Kirkland Signature Extra Virgin Olive Oil Toscano 1 Liter', 'Kirkland Extra Virgin Olive Oil Toscano'),
    ('B075D6XMYW', 'KIRKLAND Kirkland Signature, Extra Virgin Olive Oil, 2 Units', 'Kirkland Extra Virgin Olive Oil 2'),
    ('B00U56JTPG', 'KIRKLAND Signature Extra Virgin Olive Oil Arbequina (33.8 fl oz)', 'Kirkland Extra Virgin Olive Oil Arbequina'),
    ('B01EWBH2VM', 'KIRKLAND Kirkland Signature CoQ10 300 mg, 200 Softgels', 'Kirkland CoQ10 300 mg'),
    ('B008M2VYOE', 'KIRKLAND Kirkland Signature Quit Smoking Nicotine Gum, 4 mg (380 Pieces)', 'Kirkland Quit Gum 380'),
]

new_rows = {}
for asin, amazon_title, query in searches:
    print('=== ' + asin + ' | ' + query + ' ===')
    result = _search_openwebninja(query)
    items = result.get('items', [])
    for item in items:
        item_id = item.get('costco_item_id', 'N/A')
        name = item.get('item_name', 'N/A')
        price = item.get('regular_price', 'N/A')
        pack = item.get('pack_size', 'N/A')
        unit = item.get('unit_count', 'N/A')
        print('  ' + str(item_id) + ': ' + name[:80] + ' | $' + str(price) + ' | pack=' + str(pack) + ' unit=' + str(unit))
    print()