# Adding an MI50 32GB as an eGPU to an MSI Vector 16 HX AI (RTX 5080 laptop)

2026-11-02 · target: MSI Vector 16 HX AI A2XW (Core Ultra 9 275HX, RTX 5080 Laptop 16 GB GDDR7,
2× Thunderbolt 5 @ 120 Gbps, 1× M.2 Gen4 + 1× M.2 Gen5, 330 W adapter) + AMD Instinct MI50 32GB.

---

## The blunt answer first

**There is no "unified VRAM" between an RTX 5080 and an MI50.** Nothing merges 16 GB of GDDR7 with
32 GB of HBM2 into one 48 GB pool:

- **Ollama** — no cross-vendor pooling.
- **vLLM** — no cross-vendor pooling.
- **llama.cpp** — *can* list a CUDA device and a Vulkan device in one build and split layers across them
  (`--split-mode layer`), but it is experimental, and every token's activations cross both the backend
  boundary and the Thunderbolt link. Expect 2–5× slower generation than running the model on one card.
  It is not a unified pool; it is two pools with a slow bridge.

What "unified VRAM" actually requires: **same vendor, same backend**. Two NVIDIA cards in one llama.cpp
process split cleanly. An NVIDIA + an AMD card do not.

Second blunt fact: **the MI50 has no Windows driver.** AMD never shipped one — Instinct MI-series are
Linux-only, and WSL2's ROCm passthrough supports only a short list of RDNA cards, not gfx906.
So this is a **native Linux** project. Windows stays for gaming.

---

## Three routes, ranked

### Route A — MI50 in its own cheap box (recommended)
Put the MI50 inside a $150–250 used SFF/workstation (Dell Precision 3630, HP Z2 G4, or a mini-ITX
build) with native PCIe x16. Run `llama-server` on it; the laptop talks to it over the LAN.

| | |
|---|---|
| Pros | No Thunderbolt, no BAR problems, no enclosure, full x16 bandwidth, box stays on 24/7 |
| Cons | Two machines; needs a spare socket/PSU |
| Cost | MI50 $300 + box $200 + PSU/cooling $100 ≈ **$600** |

This is what people actually do, and it gives you a permanent 32 GB inference server instead of a
laptop that must stay tethered.

### Route B — OCuLink eGPU into the M.2 slot
PCIe 4.0 x4 over an OCuLink cable into the Gen4 M.2 slot (you have two).

| Part | Cost |
|---|---|
| OCuLink M.2 adapter + cable | $35–60 |
| OCuLink eGPU dock / open frame + 750 W SFX PSU | $120–200 |
| MI50 32GB blower shroud + fan (card is passive) | $30–60 |
| MI50 32GB itself | $280–330 |
| **Total** | **$465–650** |

Best cost/performance of the two "on-laptop" options. Requires opening the laptop and giving up the
Gen4 SSD slot. Linux only.

### Route C — Thunderbolt 5 eGPU enclosure
TB5 is genuinely good here (the Vector has 2× TB5). But:

- TB5 eGPU enclosures are still scarce and run $300–500; a TB3/TB4 Razer Core X (~$150 used) works at
  40 Gbps and is fine for inference.
- **Risk #1: Above 4G Decoding / large BAR.** An MI50 exposes a very large BAR. MSI laptop BIOSes
  usually don't expose Above 4G Decoding or Resizable BAR, and without them a TB eGPU with a 32 GB card
  may fail enumeration outright. This is the single most likely reason the whole plan dies.
- Enclosure must supply **2× 8-pin, 300 W** and have real airflow — the MI50 ships fanless and expects
  server forced air.

---

## Software: skip ROCm, use Vulkan

ROCm 7.x dropped gfx906; AMD lists the MI50 as unsupported. You do **not** need ROCm:

1. Ubuntu 24.04 LTS (kernel 6.11+ for USB4/TB5) or 25.04. Secure Boot off.
2. `sudo apt install mesa-vulkan-drivers vulkan-tools`
3. `vulkaninfo --summary` → look for `AMD RADV VEGA20 (Radeon Instinct MI50 32GB)`.
4. Build llama.cpp with `-DGGML_VULKAN=ON` (or use a prebuilt Vulkan release).
5. `./llama-server -m model.gguf -ngl 999 --device Vulkan0 -c 16384`

Vulkan on gfx906 is community-maintained but working today, and it sidesteps the entire ROCm
end-of-life problem. It is also the only backend that will happily coexist in one process with CUDA —
which is what makes the (slow) hybrid split in Route B/C possible at all.

For CUDA on the 5080 in the same boot: install NVIDIA 570+ drivers normally; MSI's MUX switch
("Discrete Graphics Mode") works, and hybrid graphics under Linux is fine.

---

## If what you actually want is one big pool: buy NVIDIA, not AMD

| Want | Card | Cost | Result |
|---|---|---|---|
| 16 GB + 24 GB = 40 GB, **real** llama.cpp split | Used **RTX 3090 24 GB** via TB eGPU | ~$1,500 | Same CUDA backend, `--split-mode layer` works |
| 16 GB + 24 GB = 40 GB, cheap | **Tesla P40 24 GB** via TB eGPU | **$350** | Works but slow — Pascal has no fast FP16, and it's CUDA-12-only |
| 32 GB on one card, CUDA | **V100 32 GB** | ~$700–850 | Tensor cores, CUDA 12.x only |

That is the only path to something you can honestly call unified. The MI50's 32 GB is bigger than the
5080's 16 GB, so in practice **you don't need to pool it** — a 32B Q4 model (~19 GB) fits entirely on
the MI50 and never touches the 5080.

---

## Realistic expectations

- MI50 32GB: ~1,024 GB/s, ~100–110 tok/s generating on a 7B Q4; expect roughly **15–25 tok/s on a
  32B Q4** (~19 GB) and **~7–10 tok/s on a 70B Q4** split if it fits.
- If the model fits entirely in the MI50, Thunderbolt bandwidth barely matters for generation —
  it costs you prompt/prefill time and model load time, not token rate.
- If you hybrid-split across 5080 + MI50 over TB, generation will be *slower* than MI50 alone.

---

## Bill of materials (Route B)

| Item | Cost | Note |
|---|---|---|
| AMD Instinct MI50 32GB | $280–330 | AliExpress, confirm 32 GB variant at checkout |
| OCuLink M.2 adapter + cable | $35–60 | Gen4 slot |
| Open-frame dock + 750 W SFX PSU | $120–200 | 2× 8-pin mandatory |
| Blower shroud + 92 mm fan | $30–60 | card is passive; will throttle without it |
| **Total** | **$465–650** | |

## Pre-purchase checks

1. **BIOS**: confirm Above 4G Decoding exists (or accept OCuLink, which bypasses TB BAR allocation).
2. **PSU**: 2× 8-pin PCIe, ≥450 W on the GPU rail.
3. **Clearance**: MI50 is ~267 mm, dual-slot, no bracket — plan the mount.
4. **Variant**: many AliExpress SKUs sell 16 GB and 32 GB under one listing at the same tile price.
5. **Return path**: AliExpress dispute window is your only warranty. Test `vulkaninfo` + 30-min
   `gpu-burn` equivalent within it.
