# Cheapest China-sourced GPU that beats a Tesla P40 with 20 GB+ VRAM

Read 2026-11-02 · sources: AliExpress search pages (live prices + item links), eBay market trackers,
retailer pages. No Chrome Connect used; plain fetch + search only.

---

## Answer

**AMD Radeon Instinct MI50 32GB** — roughly **$280–330 delivered** from Chinese AliExpress sellers,
**~$200–250** if you buy through a Xianyu/Taobao agent. It beats the P40 on every spec that matters for
inference except software support.

| | Tesla P40 (baseline) | **MI50 32GB** | Delta |
|---|---|---|---|
| VRAM | 24 GB GDDR5 | **32 GB HBM2** | +33% |
| Bandwidth | 694 GB/s | **1,024 GB/s** | **+47%** |
| FP32 | 12.0 TFLOPS | 13.3 TFLOPS | +11% |
| FP16 | ~0.18 TFLOPS (1:64 crippled) | **26.5 TFLOPS** | ~145× |
| Bus | 384-bit GDDR5 | 4096-bit HBM2 | — |
| TDP | 250 W | 300 W | +50 W |
| Interface | PCIe 3.0 x16 | PCIe 4.0 x16 | — |
| Software | CUDA (still works, EOL-track) | **ROCm 7 dropped gfx906** | P40 wins |

Price per GB of VRAM: **~$9/GB** vs the P40's ~$11.4/GB and the 3090's ~$62/GB.

---

## Live China listings (AliExpress, prices as shown)

| Price | Listing | Note |
|---|---|---|
| **$236.69** | [MI50 32GB/16GB HBM2 ECC, PCIe 4.0 x16, 300 W, 8-pin](https://www.aliexpress.us/item/3256812101577738.html) | cheapest 32GB-titled listing; verify variant |
| $283.79 | [MI50 16G/32G GPU accelerator](https://www.aliexpress.us/item/3256811457171553.html) | 5 sold |
| $292.49 | [MI50 32GB AI training / MI60 / Radeon VII](https://www.aliexpress.us/item/3256812977029088.html) | 5.0 rating |
| **$299.39** | [MI50 32GB deep-learning card, MI60/Radeon VII compatible](https://www.aliexpress.us/item/3256812598064997.html) | "lowest in 60/90 days" |
| $310.09 | [MI50 16GB/32GB HBM2 accelerator](https://www.aliexpress.us/item/3256812461017084.html) | 13 sold, 4.8★ |
| $313.09 | [MI50 16GB/32GB HBM2, 99% new](https://www.aliexpress.us/item/3256810360497248.html) | 12 sold |
| $481.49 | [MI50 32GB "brand new" compute card](https://www.aliexpress.us/item/3256812499527916.html) | 35 sold — most-proven seller |
| $585.39 | [MI50 32G, free shipping](https://www.aliexpress.us/item/3256811504720490.html) | 41 sold, 5.0★ — the "safe" buy |
| $145.79 | [MI50 32gb/16gb dual 8-pin Vega20](https://www.aliexpress.us/item/3256812429093909.html) | **almost certainly the 16 GB variant price** |

**Variant trap warning:** almost every one of these listings sells *both* the 16 GB and 32 GB card under one
SKU. The tile price is the 16 GB variant. Open the listing, select "32GB", and re-read the price before
concluding anything. A genuine 32 GB MI50 below ~$250 is a red flag, not a bargain.

### Reference points outside China
- eBay US, live asking: **$670 low / $828 median** (52 single-card listings, 2026-11-02)
- eBay US, sold: **$624 median** (14 sales / 30 days)
- German classifieds: €310
- The "MI50 is $120–250" blog posts are quoting late-2025 prices — that market is gone.

---

## Alternatives, ranked by price (all 20 GB+, all faster than a P40)

| Card | China price | VRAM | BW | Why / why not |
|---|---|---|---|---|
| **MI50 32GB** | **$280–330** | 32 GB | 1,024 | Cheapest 20 GB+ card that beats P40. ROCm 7 dropped gfx906. |
| MI50 16GB | $145–236 | 16 GB | 1,024 | **Fails your 20 GB requirement** — but the same listing, half price. |
| Modded 2080 Ti 22GB | **$463–680** | 22 GB | 616 | The CUDA answer. 107 TFLOPS FP16 tensor — 4× the MI50 on tensor math. Less VRAM. |
| MI60 32GB | $400–500 | 32 GB | 1,024 | Same die, better bin (14.7 TFLOPS FP32), same dead ROCm path. |
| Tesla V100 32GB | $600–850 | 32 GB | 900 | Only card here with tensor cores **and** a live CUDA path (until CUDA 13). |
| Modded 3080 20GB | ~€899 / $1,000 | 20 GB | 760 | Fastest of the lot, worst $/GB. |
| CMP 170HX 64GB | €4,999 | 64 GB | 1,355 | Exists, pointless at this budget. |

**Decision rule:** if your stack is CUDA-only, buy the **2080 Ti 22GB at $463** and stop reading.
If you can live in Linux + llama.cpp/Vulkan, the **MI50 32GB at ~$300** is 35% cheaper with 45% more VRAM.

---

## The MI50's actual catch (read before buying)

1. **ROCm 7.x dropped gfx906.** AMD's own system-requirements page lists MI50 as unsupported and warns
   prebuilt ROCm libraries will throw runtime errors. Working paths: llama.cpp **Vulkan** backend (works today),
   or copying gfx906 files forward from ROCm 6.4.4. vLLM/fine-tuning are painful to impossible.
2. **Linux only.** Windows support is effectively nil.
3. **No cooling, no bracket.** These are bare passive server cards expecting 1.5–2 m/s forced airflow.
   Budget a blower/shroud + fan: $30–60.
4. **Above 4G Decoding** must be enabled in BIOS, and you need 2× 8-pin (some SKUs ship with a non-standard
   power header — check photos).
5. **No display output.** Headless compute only; you need iGPU or a second card for a display.

Total realistic build cost, one card: **~$300 card + $50 cooling + shipping ≈ $380–420 landed** in the US
(AliExpress prices shown are usually pre-tariff; add Section 301 duty).

---

## Verification checklist for a China-sourced 20 GB+ card

- **Confirm the variant before paying.** Same SKU, two capacities, one price shown.
- On arrival: `rocm-smi --showmeminfo vram` (MI50) must report ~32,768 MiB, then actually allocate 24 GB.
- `rocminfo` / `clinfo` should show `gfx906`. A card reporting `gfx900` or nothing is a reflash or a dud.
- Run `gpu-burn` 30–60 min; HBM2 failures show as ECC/parity storms under load, not at idle.
- Check for mining history: MI50s were used in Ethash rigs — look at fan wear, BIOS version, and dust pattern.
- Buy from a seller with ≥20 sold on that exact listing; AliExpress dispute windows are the only warranty.

---

## Bottom line

| Question | Answer |
|---|---|
| Cheapest China GPU > P40, 20 GB+ | **MI50 32GB, ~$280–330** |
| Cheapest if you must have CUDA | Modded **2080 Ti 22GB, ~$463** |
| Cheapest 20 GB+ that's still supported software-wise | Used **RTX 3090, ~$1,500** (or V100 32GB ~$700 if CUDA-12-only) |
| Trap to avoid | The $145 MI50 — that's the 16 GB variant |
