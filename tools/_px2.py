from PIL import Image
im = Image.open("reports/northstar_acceptance_20261023/screenshots/theme-v8-desktop.png").convert("RGB")
w,h = im.size
print("size", w, h)
px = list(im.crop((int(w*0.86), 0, w, int(h*0.6))).getdata())
bright = sum(1 for p in px if sum(p)/3 > 70)
print("margin bright px:", bright, "/", len(px), f"({100*bright/len(px):.3f}%)")
print("top-centre:", im.getpixel((w//2, int(h*0.06))))
print("right-mid:", im.getpixel((int(w*0.95), int(h*0.25))))
print("bottom:", im.getpixel((w//2, int(h*0.9))))
