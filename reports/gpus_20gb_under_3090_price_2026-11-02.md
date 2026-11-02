# 20 GB+ GPUs better than a Tesla P40, under the RTX 3090 price (~$1,500)

Live prices read 2026-11-02 (rackbites / gpusold / cresvament eBay trackers, Newegg, AliExpress).

## Correction first

**Tesla P40 bandwidth is 346 GB/s, not 694.** The 694 figure I used earlier came from a retailer
listing that mixed P40 and P100 specs. This changes the ranking: nearly everything below is a
2–3× bandwidth upgrade over the P40, not a modest one.

P40 baseline: 24 GB GDDR5 · 346 GB/s · 12.0 TFLOPS FP32 · ~0.18 TFLOPS FP16 · CUDA 12 only · **$283–353**

## The field

| Card | VRAM | BW GB/s | FP32 TF | Tensor FP16 TF | Live price | $/GB |
|---|---|---|---|---|---|---|
| **MI50 32GB** (CN) | 32 HBM2 | **1,024** | 13.3 | 26.5 | **$236–320** | **$9.4** |
| **2080 Ti 22GB mod** | 22 GDDR6 | 616 | 13.4 | **107** | **$463–680** | $25 |
| MI60 32GB | 32 HBM2 | 1,024 | 14.7 | 29.5 | ~$450–600 | $16 |
| Arc Pro B60 24GB | 24 GDDR6 | 456 | 15.9 | 197 TOPS INT8 | $1,000 new | $42 |
| Quadro RTX 6000 24GB | 24 GDDR6 | 672 | 16.3 | 130 | **$980** low | $41 |
| Titan RTX 24GB | 24 GDDR6 | 672 | 16.3 | 130 | **$904** sold | $38 |
| **Tesla V100 32GB** | 32 HBM2 | 900 | 15.7 | **125** | **$869** low | $27 |
| Radeon Pro W6800 32GB | 32 GDDR6 | 512 | 17.8 | 35.7 | **$990** low | $31 |
| RTX A4500 20GB | 20 GDDR6 | 640 | 23.7 | 94.5 | $1,269 low | $63 |
| Instinct MI100 32GB | 32 HBM2 | **1,229** | 11.5 | 184 | $1,378 low | $43 |
| *RTX 3090 (reference)* | 24 GDDR6X | 936 | 35.6 | 285 | *$1,500* | *$62.5* |
| Quadro RTX 8000 48GB | 48 GDDR6 | 672 | 16.3 | 130 | $2,000 — over | $42 |

Also under budget: V100 32GB SXM2 ($550–750 + $130 adapter, needs an SXM2 baseboard),
modded RTX 3080 20GB (~€899, 760 GB/s, 29.8 TFLOPS — the fastest thing this cheap).

Excluded: Tesla M40 24GB (6.8 TFLOPS — slower than P40), Quadro P6000 24GB (432 GB/s —
slower, not better), RTX A5000/A6000 (price), CMP 170HX (price).

## Picks

| Goal | Buy |
|---|---|
| Absolute cheapest 20 GB+ | MI50 32GB, $236–320 from CN |
| Cheapest with real CUDA | 2080 Ti 22GB, $463 |
| Best 24 GB on CUDA under $1k | Quadro RTX 6000 ($980 blower, server-friendly) |
| Best 32 GB with live software support | **Radeon Pro W6800, $990** — ROCm-supported gfx1030, 250 W |
| Best 32 GB on CUDA | V100 32GB, $869 |
| Max bandwidth per dollar | MI50 (1,024 GB/s ÷ $300 ≈ 3,400 GB/s per $1k) |
| Max VRAM per dollar | MI60 32GB (~$16/GB) if you can find it under $500 |

**The 3090 remains the answer when you need modern CUDA + 936 GB/s + tensor throughput in one card.**
Nothing under $1,500 beats it on software; several beat it on $/GB and VRAM.
