from PIL import Image
im = Image.open("reports/northstar_acceptance_20261023/screenshots/theme-v5-desktop.png").convert("RGB")
w,h = im.size
print("size", w, h)
# right margin band
box = im.crop((int(w*0.88), 0, w, int(h*0.55)))
px = list(box.getdata())
bright = sum(1 for p in px if sum(p)/3 > 70)
print("margin bright px:", bright, "/", len(px), f"({100*bright/len(px):.3f}%)")
# warm glow sample
print("glow sample:", im.getpixel((int(w*0.93), int(h*0.18))))
print("sky sample:", im.getpixel((int(w*0.97), int(h*0.75))))
