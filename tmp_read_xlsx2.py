import openpyxl

p = r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Downloads\Fabric Catalog By Pattern.xlsx"
wb = openpyxl.load_workbook(p, data_only=True)

all_rows = []
for ws in wb.worksheets:
    items = []
    for r in ws.iter_rows(min_row=1, values_only=True):
        if not r:
            continue
        a = r[0]
        if isinstance(a, (int, float)):
            items.append(int(a))
        elif isinstance(a, str) and a.strip().isdigit():
            items.append(int(a.strip()))
    all_rows.append((ws.title, items))
    print('%-14s %2d items: %s' % (ws.title, len(items), items))

total = sum(len(i) for _, i in all_rows)
print('\nTOTAL available patterns:', total)
