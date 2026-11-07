import sqlite3, json
db = sqlite3.connect("Northstar_backend/data/northstar.db"); db.row_factory = sqlite3.Row
cols = [r["name"] for r in db.execute("pragma table_info(users)")]
print("users cols:", cols)
for r in db.execute("select * from users limit 5"):
    d = dict(r)
    keep = {k: v for k, v in d.items() if k in ("id","email","role","plan","org_id","tenant_id","created_at")}
    print(keep)
