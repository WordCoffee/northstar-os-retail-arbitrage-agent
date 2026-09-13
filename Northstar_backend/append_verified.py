import csv

verified = [
    ('B00JQRFOTA', '238120', 'Kirkland Signature Super B-Complex with Electrolytes, 500 Tablets', 18.49, 'exact'),
    ('B077LCPQ34', '238120', 'Kirkland Signature Super B-Complex with Electrolytes, 500 Tablets', 18.49, 'exact'),
    ('B08B5GZXHN', '692731', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L', 20.99, 'exact'),
    ('B0D9B4WRQT', '6262016', 'Kirkland Signature Bath Tissue, 2-Ply, 380 Sheets, 30 Rolls', 24.99, 'exact'),
    ('B07N6YF2SF', '887498', 'Kirkland Signature Wild Alaskan Fish Oil 1400 mg, 230 Softgels', 26.99, 'item_id_match'),
    ('B01CZ637O2', '249375', 'Kirkland Signature Glucosamine with MSM, 375 Tablets', 20.49, 'item_id_match'),
    ('B08JJV9M86', '1174112', 'Kirkland Signature USDA Organic Multivitamin, 80 Coated Tablets', 26.99, 'exact'),
    ('B0H9GL43LZ', '1985100', "Kirkland Signature Men's Stretch Tech Pant", 19.97, 'exact'),
    ('B0FVWFFTYV', '1947952', "Kirkland Signature Men's Pima Polo", 17.99, 'item_id_match'),
    ('B0H1Z5D4LC', '1992453', "Kirkland Signature Women's Travel Pant", 9.97, 'item_id_match'),
    ('B003FGTTUI', '692731', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L', 20.99, 'exact'),
    ('B075D6XMYW', '692731', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L', 20.99, 'exact'),
    ('B00U56JTPG', '692731', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L', 20.99, 'exact'),
    ('B01EWBH2VM', '926628', 'Kirkland Signature Fish Oil 1000 mg, 400 Softgels', 20.99, 'exact'),
    ('B008M2VYOE', '650382', 'Kirkland Signature Quit 2 mg or 4mg, Original Gum, 380 Pieces', 59.99, 'similar_item_id'),
]

csv_path = '../data/costco-items.csv'

# Read existing to check format
with open(csv_path, 'r', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('Header:', header)
    existing = list(reader)
    print('Existing rows:', len(existing))
    # Check for duplicates
    existing_keys = set()
    for row in existing:
        if len(row) >= 4:
            key = (row[0], row[1])  # asin, item_name
            existing_keys.add(key)

# Append new rows
new_rows = 0
with open(csv_path, 'a', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    for asin, item_id, item_name, price, confidence in verified:
        key = (asin, item_name)
        if key not in existing_keys:
            # Format: asin,item_name,costco_cost,costco_item_id,source,match_quality,notes
            writer.writerow([asin, item_name, price, item_id, 'openwebninja', confidence, 'verified_via_search'])
            existing_keys.add(key)
            new_rows += 1
            print('Added: ' + asin + ' | ' + item_name[:50] + ' | $' + str(price))

print('New rows added: ' + str(new_rows))