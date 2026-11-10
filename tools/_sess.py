import sqlite3
db = sqlite3.connect("Northstar_backend/data/northstar.db"); db.row_factory = sqlite3.Row
cols = [r["name"] for r in db.execute("pragma table_info(sessions)")]
print("sessions cols:", cols)
for r in db.execute("select * from sessions order by rowid desc limit 3"):
    d = dict(r)
    print({k: (v[:24] + "..." if isinstance(v, str) and len(str(v)) > 24 else v)
           for k, v in d.items() if k not in ("token", "refresh_token", "password_hash")})
