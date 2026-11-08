import openpyxl, json

p = r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Downloads\Fabric Catalog By Pattern.xlsx"
wb = openpyxl.load_workbook(p, data_only=True)
print('sheets:', wb.sheetnames)
for ws in wb.worksheets:
    print('\n=== SHEET: %s  dims=%s ===' % (ws.title, ws.dimensions))
    rows = list(ws.iter_rows(values_only=True))
    print('rows:', len(rows))
    for r in rows[:12]:
        cells = ['' if c is None else str(c)[:38] for c in r]
        print(' | '.join(cells))
