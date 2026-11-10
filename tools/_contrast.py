from PIL import Image
im = Image.open("reports/northstar_acceptance_20261023/screenshots/theme-desktop.png").convert("RGB")
w, h = im.size
def lum(c):
    def f(v):
        v /= 255
        return v/12.92 if v <= 0.03928 else ((v+0.055)/1.055)**2.4
    r,g,b = c
    return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b)
def ratio(a,b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la,lb), min(la,lb)
    return round((hi+0.05)/(lo+0.05), 2)
text = (247,243,236)
# panel interior sample (inside the chat column, away from text)
panel = im.getpixel((900, 700))
margin = im.getpixel((1850, 400))
print("size", w, h)
print("panel bg", panel, "contrast vs #f7f3ec:", ratio(text, panel))
print("right margin", margin, "contrast vs text:", ratio(text, margin))
# star presence: count pixels brighter than the local background in the right margin
box = im.crop((1450, 60, 1900, 900))
px = list(box.getdata())
bright = sum(1 for p in px if sum(p)/3 > 90)
print("bright pixels in margin:", bright, "of", len(px))
