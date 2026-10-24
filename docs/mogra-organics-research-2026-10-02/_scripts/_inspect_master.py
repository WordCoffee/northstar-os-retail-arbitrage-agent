import csv, os, collections
BASE = os.path.join("docs", "mogra-organics-research-2026-10-02")
rows = list(csv.DictReader(open(os.path.join(BASE, "supplier_master.csv"), newline="", encoding="utf-8")))
print("=== HQ COUNTRY ===")
for k, v in collections.Counter(r["hq_country"] for r in rows).most_common():
    print("  %-16s %d" % (k, v))
print()
print("=== SUPPLIER TYPE ===")
for k, v in collections.Counter(r["supplier_type"] for r in rows).most_common():
    print("  %-28s %d" % (k, v))
print()
print("=== ALL 51 (id | name | country | site) ===")
for r in rows:
    print("  %-4s %-34s %-14s %s" % (r["supplier_id"], r["legal_name"][:34], r["hq_country"][:14], (r["website"] or "-")[:52]))
print()
print("=== DISCOVERY SOURCE HOSTS ===")
import urllib.parse as up
h = collections.Counter(up.urlparse(r["source_url"]).netloc for r in rows)
for k, v in h.most_common():
    print("  %-40s %d" % (k, v))