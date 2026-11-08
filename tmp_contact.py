import json, os
from PIL import Image, ImageDraw, ImageFont

base = r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\tmp-patterns\avail"
mapping = json.load(open(os.path.join(base, '_mapping.json')))

def sheet(sheets, name, cols=6, cell=210):
    items = [m for m in mapping if m['sheet'] in sheets]
    items.sort(key=lambda m: (sheets.index(m['sheet']), m['item']))
    rows = (len(items) + cols - 1) // cols
    W, H = cols * cell, rows * (cell + 26) + 40
    img = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype('arialbd.ttf', 15)
    except Exception:
        font = ImageFont.load_default()
    d.text((8, 8), name, fill='black', font=font)
    for i, m in enumerate(items):
        r, c = divmod(i, cols)
        x = c * cell + 6
        y = r * (cell + 26) + 36
        try:
            im = Image.open(os.path.join(base, m['file'])).convert('RGB')
            im.thumbnail((cell - 12, cell - 12))
            img.paste(im, (x, y))
        except Exception as e:
            pass
        d.text((x, y + cell - 6), '#%d %s' % (m['item'], m['sheet']), fill='black', font=font)
    out = os.path.join(base, name.replace(' ', '_') + '.png')
    img.save(out)
    print(out, img.size, len(items))

sheet(['Fruit'], 'FOOD Fruit')
sheet(['Bee', 'Kitchenware', 'Figure'], 'FOOD Bee Kitchen Figure')
sheet(['Floral', 'Botanical'], 'FLORAL + BOTANICAL')
sheet(['Animal', 'Geometric'], 'ANIMAL + GEOMETRIC')
