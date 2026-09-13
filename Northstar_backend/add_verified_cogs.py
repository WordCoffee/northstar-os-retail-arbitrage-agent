import csv
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Verified ASIN -> Costco item with Amazon title
verified = [
    ('B00JQRFOTA', 'Kirkland Signature Super B-Complex with Electrolytes, 500 Tablets', 18.49),
    ('B077LCPQ34', 'Kirkland Signature Super B-Complex with Electrolytes, 500 Tablets', 18.49),
    ('B08B5GZXHN', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L', 20.99),
    ('B0D9B4WRQT', 'Kirkland Signature Bath Tissue, 2-Ply, 380 Sheets, 30 Rolls', 24.99),
    ('B07N6YF2SF', 'Kirkland Signature Wild Alaskan Fish Oil 1400 mg, 230 Softgels', 26.99),
    ('B01CZ637O2', 'Kirkland Signature Glucosamine with MSM, 375 Tablets', 20.49),
    ('B08JJV9M86', 'Kirkland Signature USDA Organic Multivitamin, 80 Coated Tablets', 26.99),
    ('B0H9GL43LZ', "Kirkland Signature Men's Stretch Tech Pant", 19.97),
    ('B0FVWFFTYV', "Kirkland Signature Men's Pima Polo", 17.99),
    ('B0H1Z5D4LC', "Kirkland Signature Women's Travel Pant", 9.97),
    ('B003FGTTUI', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L', 20.99),
    ('B075D6XMYW', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L', 20.99),
    ('B00U56JTPG', 'Kirkland Signature, Organic Extra Virgin Olive Oil, 2 L', 20.99),
    ('B01EWBH2VM', 'Kirkland Signature Fish Oil 1000 mg, 400 Softgels', 20.99),
    ('B008M2VYOE', 'Kirkland Signature Quit 2 mg or 4mg, Original Gum, 380 Pieces', 59.99),
]

# Read existing to check for duplicates
with open('../data/costco-items.csv', 'r', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    existing = [row for row in reader]

# Append new rows
with open('../data/costco-items.csv', 'a', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    for asin, item_name, price in verified:
        writer.writerow([item_name, price])

print('Appended ' + str(len(verified)) + ' new COGS entries')
print('Total rows: ' + str(len(existing) + len(verified)))