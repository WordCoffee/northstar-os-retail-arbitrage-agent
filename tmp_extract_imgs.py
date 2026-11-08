import openpyxl, os, json
from openpyxl.utils import get_column_letter

p = r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Downloads\Fabric Catalog By Pattern.xlsx"
outdir = r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\tmp-patterns\avail"
os.makedirs(outdir, exist_ok=True)

wb = openpyxl.load_workbook(p)
mapping = []
for ws in wb.worksheets:
    # item no per row
    row_item = {}
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if v is None:
            continue
        s = str(v).strip()
        if s.isdigit():
            row_item[r] = int(s)
    imgs = getattr(ws, '_images', [])
    for im in imgs:
        try:
            r0 = im.anchor._from.row + 1
        except Exception:
            continue
        item = row_item.get(r0)
        if item is None:
            continue
        data = im._data()
        ext = 'png'
        fn = 'item%03d_%s.%s' % (item, ws.title.lower(), ext)
        with open(os.path.join(outdir, fn), 'wb') as f:
            f.write(data)
        mapping.append({'item': item, 'sheet': ws.title, 'file': fn, 'bytes': len(data)})

mapping.sort(key=lambda x: (x['sheet'], x['item']))
json.dump(mapping, open(os.path.join(outdir, '_mapping.json'), 'w'), indent=1)
print('images written:', len(mapping))
by = {}
for m in mapping:
    by.setdefault(m['sheet'], []).append(m['item'])
for k, v in by.items():
    print('%-12s %2d  %s' % (k, len(v), sorted(v)))
