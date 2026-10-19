# Creative Pipeline v2 — operator guide

Everything below runs **locally** on this machine. Nothing here calls a paid
provider or spends money. Written 2026-10-19 after the overnight build; every
command was run and its output is in `renders/` or the commit history.

---

## 1. What you can do now that you could not yesterday

| Capability | One command |
|---|---|
| See the realism difference on a real mockup | `python scripts/compositor_realism_ab.py` |
| Edit a render's scene/lighting without touching the product | `python scripts/smoke_qwen_edit2511.py` |
| Cut a product out and frame it for an Amazon MAIN slot | `python scripts/smoke_cutout_main.py --size 2000` |
| Ask "is this package retail-ready?" | `python scripts/package_readiness_live.py` |
| Check a file for print (CMYK, gamut, ink limit) | `python -m Northstar_backend.prepress --in <png> --cmyk-out out.tif` |
| Learn from public pages / PDFs into the local corpus | `python Northstar_backend/corpus_learner.py --seed <url> --max 20` |
| Search the 57k-source research index | `python -c "…corpus search…"` or the corpus API |

---

## 2. The readiness verdict — start here

```powershell
python scripts/package_readiness_live.py
```

It writes `renders/package_readiness_live.json` and prints one verdict:

```
VERDICT: needs_work
  - prepress: 18.09% of pixels move more than 8.0 dE through the press profile
  - copy: copy 'MOGRA ORGANICS' matched only fuzzily (OCR ratio 0.96) - eyeball …
  - dieline: proportion: gusset 40mm is far below the published 80mm …
```

**Read the blockers, not the verdict.** Three kinds exist:

1. **Real print risks** — the 18 % out-of-gamut number is the dark green and
   near-black film colours against SWOP. Ask the co-packer what profile they
   print to and put *their* `.icc` in `C:\Windows\System32\spool\drivers\color`.
2. **Eyeball warnings** — a fuzzy OCR hit means the wordmark is stylised enough
   that OCR read it one character off. Look at the render.
3. **Dieline cautions** — the gusset warning is the blueprint's §2.5 finding:
   the 8 oz spec's 40 mm gusset is half the published 80 mm for that fill weight.
   **Measure a competitor pouch before any plate is cut.**

---

## 3. The lanes, in the order the pipeline uses them

```
brief ──► generate (clean plate) ──► [optional] edit scene/light ──► upscale
      ──► compose deterministic type (compositor) ──► cutout ──► MAIN framing
      ──► prepress ──► readiness
```

**Generate a clean plate** (no lettering — the model must never draw copy):
```powershell
$env:MEDIA_GEN_LIVE="1"
python -c "import sys; sys.path.insert(0,'Northstar_backend'); import studio_generation as sg; open('renders/plate.png','wb').write(sg.generate_image('matte stand-up pouch on a wooden table, soft window light')['bytes'])"
```

**Edit the scene** (Qwen-Image-Edit-2511 — keep the product, change the world):
```powershell
python scripts/smoke_qwen_edit2511.py --input renders/plate.png --tier draft
```
The sidecar records a `copy_preservation` verdict. **If it is `false`, the output
is not shippable without re-compositing the text layer** — that is the whole
point of the gate. Use this lane on a *clean plate*, then compose type.

**Compose the type** (deterministic — real fonts, real logo, exact spelling):
```powershell
python -c "import sys; sys.path.insert(0,'Northstar_backend'); import mockup_compositor as mc; print(mc.compose_mockup(template_id='mogra-forest-dusk', plate_path='renders/plate.png', logo_path='Northstar_backend/assets/brand/mogra_logo.png', out_path='renders/composed.png', quads=[[[124,455],[558,452],[568,1002],[112,1006]]], skus=[{'title':'ORGANIC LION\'S MANE','weight':'6 oz (170 g)','gold':[196,160,74]}]))"
```
`shading=0.5` (the default) is the research-recommended realism dial. `0.0` is a
flat paste (useful for A/B). Every knob is in the returned `realism` block.

**Cut out + frame for MAIN**:
```powershell
python scripts/smoke_cutout_main.py --input renders/composed.png --size 2000
```
Verdict `compliant` means white background, ≥85 % fill, ≥2000 px.

**Prepress**:
```powershell
python -m Northstar_backend.prepress --in renders/composed.png --cmyk-out renders/composed_cmyk.tif --proof-out renders/composed_proof.png
```

---

## 4. API surface (for the UI session)

All under `/api/design-studio`, auth = the studio session like every other route:

```
GET  /lanes/status                 which lanes are usable + why
POST /lanes/cutout                 {asset_id, fill, size, min_fill, min_side, persist_framed}
POST /lanes/upscale                {asset_id, factor}   (deterministic, no GPU)
POST /lanes/main-check             {asset_id, min_fill, min_side, require_square}
POST /lanes/readiness              {asset_id, main_asset_id, expected_terms, template_id, params}
GET  /print/prepress/profiles      CMYK profiles on this machine
POST /print/prepress/check         {asset_id, profile, limit_pct, tolerance_dE76, persist_cmyk}
POST /compose/mockup               {template_id, plate_asset_id, realism, shading, …}
```

The cutout lane returns **409 with the engine's own words** when
`MEDIA_GEN_LIVE` is not 1 — it never silently degrades.

---

## 5. Research corpus

```powershell
python tools/ingest_wave2.py                        # re-ingest (idempotent)
python research/research_wave2_20261019/analyze_repos.py   # category analysis
```

57,355 records are already indexed: 47,323 GitHub repos, 9,148 Hugging Face
assets, 884 YouTube rows. Search hits them through the existing corpus routes
(`/api/corpus/*`) and the `corpus_search` chat tool.

**Learn something new from the web** (signed-out public pages only; robots
honoured; throttled):
```powershell
python Northstar_backend/corpus_learner.py --urls my_urls.txt --tags packaging,print
python Northstar_backend/corpus_learner.py --seed https://example.com/guide --max 15
python Northstar_backend/corpus_learner.py --dry-run --seed https://example.com/guide
```
HTML **and PDF** (pypdf). A scanned PDF with no text layer is reported as a
failure with the reason — never stored as an empty document.

---

## 6. Things that are deliberately NOT automatic

- **Nothing is ever bought, listed, or priced.** Those still need your explicit
  approval per the constitution.
- **Model upscaling is off.** RealESRGAN x4 aborted the ComfyUI process on a
  1216 px input; the deterministic LANCZOS path replaced it and the incident is
  in `00_STATE.json` → `known_issues`. Revisiting is your call.
- **Blender is not installed**, so there is no 3D mockup lane yet. The research
  wave lists the candidates (Hunyuan3D-2, img2threejs, Blender headless).
- **The doypack dieline is a planning dieline, not a die.** Only your co-packer's
  drawing (or a measured pouch) makes it a manufacturing master.
