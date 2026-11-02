# Tesla V100 32GB — global sourcing brief

Prepared 2026-11-02 · procurement role: enterprise GPU / datacenter accelerator sourcing
Basis: live prices pulled today (linked, verified) + market structure knowledge. Items marked
**[live]** were read off the page today; **[est]** are structural estimates.

---

## 1. Target baseline & variants

V100 has one silicon (GV100, 5120 CUDA, 640 Tensor, sm_70) in several physical packages.
**VRAM is bundled with package**: 16GB was the volume SKU, 32GB was the specialty SKU.

| Variant | Form factor | Power | Typical use | **[live] floor** | **[est] realistic floor** |
|---|---|---|---|---|---|
| **V100 PCIe 32GB** | dual-slot PCIe 3.0 x16, passive | 250 W | any server/workstation | **$848.88** (eBay used), **$880–889** refurb Newegg | $780–900; sub-$750 only on auctions or 0-feedback sellers |
| **V100 SXM2 32GB** | SXM2 mezzanine, no bracket, no cooler | 300 W | HGX-1 / DGX-1 / C4140 | $1,284.79 (AliExpress Dell PG500-216) | **$550–750** direct from CN; $450–600 on Xianyu via agent |
| **V100 SXM3 32GB** | SXM3, NVLink 2.0 (6 links) | 300 W | HGX-2 / DGX-2 only | none listed in retail channels today | $400–700, but only usable inside an HGX-2 tray |
| V100 PCIe 16GB (reference) | same as PCIe 32GB | 250 W | — | **$389.99** refurb Newegg | $330–400 |
| V100 SXM2 16GB (reference) | SXM2 | 300 W | — | $188–235 (eBay CN) | $170–230 |

**Key pricing law for V100:** 32GB carries a 2.2–2.4× premium over 16GB, not 2×.
The 16GB card is the volume dump; the 32GB card is the shortage. Every sourcing trick below
exists to arbitrage that spread.

**Cheapest *legitimate* 32GB acquisition right now:** refurbished PCIe 32GB from a US refurbisher
at **$848–889** with 90-day warranty. Everything cheaper involves China, an adapter, or a whole node.

---

## 2. Global sourcing channels

### US / North America
| Channel | Notes | V100 32GB reality |
|---|---|---|
| **UnixSurplus** (Sunnyvale) | eBay store `plusboards`, 90-day seller warranty, no-bracket stock common | V100 16GB $350-class; 32GB intermittent |
| **xByte Technologies** | Dell-specialist, 1-in-stock listings, warranty | 32GB appears as PG500-216 pulls |
| **PC Server & Parts** (pcsnp) | Deep Dell/HPE pull inventory, 90-day RMA | Listings frequently out of stock — check weekly |
| **The Server Store / ServerMonkey / IT Creations / TekBoost / SaveMyServer** | Classic refurb tier | 32GB $900–1,400 |
| **eBay liquidators** | Highest volume, best mislabels | **$848.88** is today's floor |
| **GovDeals / PublicSurplus / GSA Auctions** | Decommissioned university/lab nodes; no warranty, as-is | Best per-card price when a whole node is listed |
| **LabX / BioSurplus** | Lab/compute disposals, slow turnover | Occasional DGX-1 |

### China / Asia-Pacific
- **Alibaba** — MOQ 1–5 from Shenzhen/Guangzhou traders; $200–227 for P40-class, V100 32GB typically
  $600–800 quoted. Reorder-rate ≥20% and 2+ years trading are the only trust signals that matter.
- **Taobao / 1688** — domestic retail and wholesale; needs a CN payment path (Alipay) or an agent.
- **Xianyu (闲鱼)** — the real floor. Consumer-to-consumer, individual sellers dumping pulls.
  Requires an agent (Superbuy / CSSBUY / Wegobuy class). Expect 20–35% under Taobao.
- **Huaqiangbei (Shenzhen)** — physical market, same goods as Alibaba at cash prices; only viable in person.

### Europe
- **Bargain Hardware (UK)** — 12 in stock 16GB at £300 ex VAT; 32GB £700–900 class, 90-day RTB.
- **Stonetaskin (UK)** — HPE/Dell pulls, VAT-inclusive quotes.
- **Serverschmiede (DE)** — Grade A refurb, publishes condition tier; €437 ex VAT for 16GB.
- **BIM Computing (EU/BVI)** — DDP delivery, duties included; the only channel where the quoted price
  is the landed price.
- **ITZoo, ETB Technologies (UK)** — smaller, good for single units with invoice + VAT reclaim.

**Duty note:** US import of CN-origin GPUs carries Section 301 tariffs; EU import carries 0% duty on
computer parts but 19–21% VAT. A $600 Xianyu card becomes ~$700–780 landed in the EU.

---

## 3. Alternative sourcing strategies

### A. DIY: SXM2 32GB + adapter board
| Line item | Cost |
|---|---|
| V100 SXM2 32GB (CN direct) | $550–750 |
| SXM2→PCIe x16 adapter (with VRM + cooler) | **$129.99** [live, Newegg] – $250 |
| Blower/shroud if adapter is passive | $30–80 |
| 8-pin EPS + 2× PCIe power adapters | $10–20 |
| **Total** | **$720–1,100** |

vs native PCIe 32GB at **$848–889 with warranty**. Conclusion: **the SXM2 route is not worth it for 32GB**
unless you find a card under ~$550. For 16GB it is strictly worse ($188 + $130 + $40 = $358 vs $390 with warranty).

Adapter caveats that kill the economics: most SXM2→PCIe boards are PCIe 3.0 x8 or x16 with marginal
12V VRM, run the card at 250 W instead of 300 W, ship with no bracket, and have no thermal design for
sustained load. Failure rate is the hidden cost.

### B. Off-lease complete nodes — the real arbitrage
| Node | GPU config | Typical whole-node price | **Per 32GB card** |
|---|---|---|---|
| **Dell PowerEdge C4140** | 4× V100 SXM2 32GB | $4,000–8,000 | **$1,000–2,000** + free chassis/CPUs/RAM |
| **NVIDIA DGX-1** | 8× V100 SXM2 16GB (some 32GB) | $6,000–12,000 | $750–1,500/card *plus* dual Xeon, 512GB RAM, 4× NVMe, IB |
| **HPE Apollo 6500** | 4–8× SXM2 | $6,000–12,000 | similar |
| **NVIDIA DGX-2** | 16× V100 SXM3 32GB | $25,000–45,000 | $1,500–2,800 — rarely beats buying cards |

The DGX-1 path is the classic move: 8× 16GB (128GB aggregate, NVLink-hybrid) for the price of
3–4 loose 32GB cards. Per-GB it wins; per-card-capacity it does not.

### C. Timing
V100 supply is end-of-life pull stock. Prices are bottoming, not falling: the 16GB has already
flattened (~$390 refurb), the 32GB is being held up by the same AI-demand wave that pushed the
RTX 3090 to a $1,551 sold median. Do not wait for a 32GB crash that is not coming; buy the
warranty, not the discount.

---

## 4. Exact search parameters

### eBay (the highest-yield channel)
URL pattern: `https://www.ebay.com/sch/i.html?_nkw=<QUERY>&_sop=15&LH_BIN=1&LH_ItemCondition=3000`

| Purpose | Query |
|---|---|
| Catch-all | `tesla v100 32gb` · `v100 32g` · `v100-32gb` |
| **Part-number hunt (best signal/noise)** | `699-2G500-0216` · `900-2G500-0216` · `PG500-216` · `699-2G503-0204` |
| SXM2 | `v100 sxm2 32` · `v100 sxm2` |
| OEM pulls | `dell pg500-216` · `hp v100 32gb` · `lenovo v100 32gb` · `supermicro v100` |
| Mislabels | `v100 32gb hbm2` · `tesla v100 gpu` (no size) · `nvidia v100 accelerator` |
| Comps (what it actually sold for) | add `&LH_Sold=1&LH_Complete=1` |

Bands to force the floor to the top: append `&_udhi=800`, then `_udhi=650`, then `_udhi=500` —
if a sub-$650 32GB exists it surfaces on page 1 of that band.

### Alibaba
`Tesla V100 32GB PCIe` · `V100 SXM2 32G` · `699-2G500-0216` · filter MOQ ≤ 5, supplier ≥ 2 yr,
"Reorder rate" ≥ 20%.

### Taobao / Xianyu
`V100 32G 显卡` · `V100 SXM2 32G` · `特斯拉 V100 拆机` (pulled) · `V100 32G 涡轮` (blower) · `GV100 32G`

### Surplus
`"V100" surplus lot` · `C4140 GPU` · `DGX-1 decommission` · `HGX-1 chassis`

---

## 5. Risk assessment & verification checklist

**Spoofing: 16GB sold as 32GB**
- Physical: 4 HBM2 stacks either way (4×4GB vs 4×8GB) — you cannot tell by looking.
- Software: `nvidia-smi -q -d MEMORY` reports the true total. Then **actually allocate**: a 16GB card
  fails a 24GB `cudaMalloc`/`torch.empty` even if it lies about capacity. Do this before the return window closes.
- Bandwidth is identical (900 GB/s) on both — bandwidth tests prove nothing.

**Engineering samples / BIOS tampering**
- GPU-Z / `nvidia-smi -q` should say `Tesla V100-PCIE-32GB` or `Tesla V100-SXM2-32GB`.
  Blank subsystem ID, "ES", or a Quadro string = walk away.
- VBIOS on a 32GB card should be a signed NVIDIA image; a modified BIOS usually breaks Secure Boot
  attestation and driver signing on newer branches.

**HBM2 damage (the most common real failure)**
- Run 30–60 min of `gpu-burn` + MATS. Check `nvidia-smi -q -d ECC` for corrected/uncorrected counts.
- Any Xid error in `dmesg` = reject. HBM2 reball failures show up as ECC storms under sustained load, not at idle.

**Thermal**
- Passive PCIe cards assume 1.5–2 m/s chassis airflow. In a desktop case they throttle to 60–70% clocks.
  Budget a blower shroud (~$40) or don't buy passive.

**SXM2/SXM3-specific**
- SXM3 will not fit an SXM2 baseboard (different mezzanine + NVLink 2.0). SXM2 ≠ plug-and-play.
- Adapter boards: verify 12V rail capacity, 8-pin EPS presence, and that the board isn't x8-only.

**Software lifecycle (decide this before you buy)**
- Volta (sm_70) is at end-of-life in the CUDA toolchain: deprecated in the CUDA 12.8 era and dropped
  from the CUDA 13 line. Pin your stack to a CUDA 12.x driver branch; verify against your framework's
  minimum before committing. This is the single biggest hidden cost of V100 in 2026.

**Commercial**
- US: Section 301 tariff on CN-origin goods; EU: 19–21% VAT. Get DDP quotes (BIM) or budget +25%.
- Warranty is the price of admission: 90-day (UnixSurplus/xByte/Bargain Hardware) is worth $100–150 over
  a no-warranty CN card, because return shipping to Shenzhen is often uneconomic.

---

## Decision summary

| If you want… | Buy |
|---|---|
| Lowest risk, deploy today | Refurb PCIe 32GB, $848–889, US refurbisher with 90-day |
| Lowest absolute price | Xianyu SXM2 32GB via agent, $450–600 — only with an SXM2 baseboard already owned |
| Lowest cost per GB of VRAM | DGX-1 node (8× 16GB), $750–1,500/card equivalent, chassis included |
| Do not bother | SXM2 32GB + adapter at current card prices — $720–1,100 vs $850 with warranty |
