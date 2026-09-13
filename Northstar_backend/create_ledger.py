import json
import os

# Verified ASIN -> Costco item_name mappings
verified = [
    ('B00JQRFOTA', 'Kirkland Signature Super B-Complex with Electrolytes, 500 Tablets'),
    ('B077LCPQ34', 'Kirkland Signature Super B-Complex with Electrolytes, 500 Tablets'),
    ('B08B5GZXHN', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L'),
    ('B0D9B4WRQT', 'Kirkland Signature Bath Tissue, 2-Ply, 380 Sheets, 30 Rolls'),
    ('B07N6YF2SF', 'Kirkland Signature Wild Alaskan Fish Oil 1400 mg, 230 Softgels'),
    ('B01CZ637O2', 'Kirkland Signature Glucosamine with MSM, 375 Tablets'),
    ('B08JJV9M86', 'Kirkland Signature USDA Organic Multivitamin, 80 Coated Tablets'),
    ('B0H9GL43LZ', "Kirkland Signature Men's Stretch Tech Pant"),
    ('B0FVWFFTYV', "Kirkland Signature Men's Pima Polo"),
    ('B0H1Z5D4LC', "Kirkland Signature Women's Travel Pant"),
    ('B003FGTTUI', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L'),
    ('B075D6XMYW', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L'),
    ('B00U56JTPG', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L'),
    ('B01EWBH2VM', 'Kirkland Signature Fish Oil 1000 mg, 400 Softgels'),
    ('B008M2VYOE', 'Kirkland Signature Quit 2 mg or 4mg, Original Gum, 380 Pieces'),
]

# Create or load existing ledger
ledger_path = os.path.join('..', 'data', 'costco-amazon-mapping.json')
if os.path.exists(ledger_path):
    with open(ledger_path, 'r', encoding='utf-8') as f:
        ledger = json.load(f)
else:
    ledger = {}

# Add verified entries
for asin, item_name in verified:
    ledger[asin.upper()] = item_name

# Save ledger
with open(ledger_path, 'w', encoding='utf-8') as f:
    json.dump(ledger, f, indent=2, ensure_ascii=False)

print('Ledger updated with ' + str(len(verified)) + ' entries')
print('Total ledger entries: ' + str(len(ledger)))
for asin, item in ledger.items():
    print('  ' + asin + ' -> ' + item[:60])