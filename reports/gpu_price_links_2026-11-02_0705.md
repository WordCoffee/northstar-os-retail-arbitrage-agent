# GPU price scan — pass 2: real listings with links

**Run:** 2026-11-02 ~07:05–07:30 CST
**Method:** operator-authorized non-browser fetch (`websearch`/`webfetch`) for retailer + market pages,
plus `chromeconnect_run` for eBay (eBay returns 403 to plain HTTP clients).
**Scope:** RTX 3090 24GB · Tesla P40 24GB · Tesla V100 16GB · **modded RTX 2080 Ti 22GB**

Prices are as-shown on the page at read time. Amazon not checked (standing gate).

---

## RTX 3090 24GB

Market anchor, same day: **sold median $1,551** (295 US eBay sales / 14 days, gpusold.com);
used **asking** median $1,675, 25th pct $1,569, min $1,190.90 (cresvament.com, 65 active listings).

| Price | Condition | Listing |
|---|---|---|
| **$1,500** | Used | EVGA FTW3 ULTRA 24GB — https://www.ebay.com/itm/117499357260 |
| $1,549 | Used, tested, w/ box, free ship | EVGA FTW3 Ultra — https://www.ebay.com/itm/227593089976 |
| $1,559 + $45 | Used | Founders Edition — https://www.ebay.com/itm/128170284968 |
| $1,599.99 free ship | Used | Dell OEM (triple fan) — https://www.ebay.com/itm/206668595832 |
| $1,629 free ship | Refurb (Very Good) | Zotac Trinity OC — https://www.ebay.com/itm/287672018941 |
| $1,649 free ship | Refurb (Good) | Zotac Trinity — https://www.ebay.com/itm/287663726734 |

Cheapest *sightings* below that are auctions ($510 GALAX HOF, 6d left) or low-feedback sellers
($1,199 Belgium, 0 fb) — not safe "buy now" links.

---

## Tesla P40 24GB

| Price | Condition | Source |
|---|---|---|
| **$350** free ship, no bracket, 90-day | Refurbished | unixsurplus — https://unixsurplus.com/nvidia-tesla-p40-24gb-gddr5-gpu/ |
| $399, 1 in stock | Used | xByte — https://www.xbyte.com/products/cat-17069/ |
| $750 | Refurb | Catalyst Data Solutions — https://shop.catalystdatasolutionsinc.com/graphics-gpu/nvidia-tesla-p40-24gb-gddr5-gpu-accelerator/ |
| $331.99 — **OUT OF STOCK** | Used | The Server Store — https://parts.theserverstore.com/collections/graphics-cards-gpus |
| $184.99 — **OUT OF STOCK** | Used | PC Server & Parts — https://pcserverandparts.com/dell-nvidia-tesla-p40-24gb-gddr5x-graphics-card-used-km3c2-0km3c2/ |
| $273–275 free ship | Used | eBay China sellers — https://www.ebay.com/sch/i.html?_nkw=tesla+p40&_sop=15 |
| $200–227, MOQ 1–2 | Used, "tested" | Alibaba — https://www.alibaba.com/trade/search?SearchText=tesla%20p40%2024gb |

**US in-stock floor right now: $350.** The $185–332 prices are dead listings.

---

## Tesla V100 16GB PCIe (plug-in)

| Price | Condition | Source |
|---|---|---|
| **$389.99** free ship | Refurbished | Newegg — https://www.newegg.com/p/1WK-00TY-00088 |
| $399.99 free ship | Refurbished HP | Newegg — https://www.newegg.com/hp-tesla-v100-graphics-card/p/2VV-000F-003N1 |
| $419.99 free ship | Refurbished Dell VFJ45 | Newegg — https://www.newegg.com/p/1WK-0025-037S6 |
| £300 ex VAT (~$400) | Refurb, 90-day, 12 in stock | Bargain Hardware UK — https://www.bargainhardware.co.uk/nvidia-tesla-v100-pcie-x16-16gb-hbm2-gpu-accelerator |
| €437.82 ex VAT / €521 inc | Refurb Grade A | Serverschmiede DE — https://www.serverschmiede.com/en/nvidia-tesla-v100-16gb-gpu-computing-accelerator-ai-ki-llm-original-hbm2-pcie-x16 |
| €399 / US$450 DDP | Used, bench-tested | BIM Computing — https://bim-computing.com/products/nvidia-tesla-v100-16gb |
| $880–889 free ship | Refurbished | **32GB** versions on Newegg — https://www.newegg.com/p/pl?d=nvidia+tesla+v100 |

**SXM2 shortcut:** eBay 16GB SXM2 $188–235 + SXM2→PCIe adapter board $129.99
(https://www.newegg.com/p/1WK-01AD-000T9) ≈ **$320 total** — but adapter boards are the weak link
(power delivery, cooling, flaky firmware). Warranty-free in that path.

---

## Modded RTX 2080 Ti 22GB — the options

| Price | Where | Notes |
|---|---|---|
| **$463.09** | AliExpress — https://www.aliexpress.us/item/3256813224488132.html | "Service Graphics Card 2080 TI 22GB" — cheapest sighting, variant risk |
| $612.69 | AliExpress — https://www.aliexpress.us/item/3256812866779898.html | Used, "non-mining" claim |
| $678 + $2.97 | eBay, seller `ujianggt752` (100%, 80 fb) | Pick the board: Gigabyte https://www.ebay.com/itm/366761939162 · Zotac https://www.ebay.com/itm/366766157841 · MSI https://www.ebay.com/itm/366761938313 · Dell https://www.ebay.com/itm/366761936953 · Leadtek https://www.ebay.com/itm/366762117665 · Colorful https://www.ebay.com/itm/366684597209 |
| $680 free ship | eBay — https://www.ebay.com/itm/227523856969 | "Turbo Modified for AI Mapping", China |
| £463.04 + £9.99 | eBay UK/HK — https://www.ebay.com.hk/itm/407301750164 | London, 3-month warranty, 2 in stock |
| €699 / US$780 DDP | BIM Computing — https://bim-computing.com/products/retrofitted-rtx-2080-ti-22gb | Bench-tested with published numbers, EU duties included, warranty |
| ¥60,840 (~$395) | Japan — https://www.codeminos.io/?shop=8c9b81762544 | Asus 22GB retrofit, secondhand shop |
| ¥2,000–3,500 CNY (~$280–490) | Taobao | Domestic CN pricing; 3200 CNY ≈ $450 is the typical non-mining unit |
| $699 | UBB store — https://www.ubbthreads.com/store/item/22GB-VRAM-Mod-PNY-RTX-2080-Ti-Blower-Fully-Tested-Local-AI-LLM_800808110669.html | Individual seller, MATS/OCCT/FurMark reports, 30-day |

### What "modded" actually means here
- Physical swap: eleven 1 GB GDDR6 modules → 2 GB modules, plus strap-resistor rework and a BIOS edit.
  Not a BIOS unlock. Works with stock signed NVIDIA drivers (no patched driver, Secure Boot stays on).
- **300A core** in the titles = TU102-300A, the higher-binned die with the raised power limit. Prefer it.
- Specs: 22 GB GDDR6, 352-bit, **616 GB/s**, 250 W, 2× 8-pin, 4,352 CUDA / 544 Tensor (2nd gen).
- Bandwidth reality check: 3090 = 936 GB/s, V100 32GB = 900 GB/s, 2080 Ti 22GB = 616 GB/s.
  For token generation, bandwidth dominates; for "does the model fit at all", capacity dominates.

### Risk notes specific to this card
- 22 GB is the whole point and the whole risk: a failed memory reball shows up as VRAM errors weeks later.
  Sellers offering 30-day to 3-month warranty (BIM, maplepointltd, UBB seller) are worth the premium over $463.
- Chinese marketplace listings with 10+ variants often price the *cheapest* variant on the card ($463 may be an
  11 GB or accessory SKU). Confirm in the variant selector before paying.
- Cost per GB at $678: $30.8/GB — vs 3090 at $1,500 = $62.5/GB, V100 16GB at $390 = $24.4/GB,
  P40 24GB at $350 = $14.6/GB.

---

## Bottom line

| Card | Buy this | $/GB VRAM |
|---|---|---|
| RTX 3090 24GB | $1,500 used EVGA FTW3 (eBay) — or $1,190 ask if you'll buy from a 0-feedback seller | $62.50 |
| Tesla P40 24GB | $350 refurb, unixsurplus (in stock) — or $273 China BIN on eBay | $14.58 |
| Tesla V100 16GB PCIe | $389.99 refurb, Newegg | $24.37 |
| RTX 2080 Ti 22GB modded | $678 eBay (ujianggt752) for cheapest; €699/$780 BIM for tested + warranty | $30.82 |
