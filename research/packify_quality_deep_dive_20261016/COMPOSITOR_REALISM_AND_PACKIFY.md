# COMPOSITOR REALISM & PACKIFY — deep dive

- **Date:** 2026-10-16
- **Author:** Northstar research subagent (Packify-quality deep dive)
- **Question:** How do we make a designed label/logo look *truly printed on a product photo* — lift `scripts/compose_mogra_complete.py` (clean 4-point homography, reads "sticker-like") to Packify.ai-grade realism, using Python/OpenCV/PIL only?
- **Method:** (a) re-read repo evidence; (b) live re-verification of Packify/Pacdora public surfaces this session (marketing pages, live static JS assets on the public CDN — no app interaction, no API calls, no credential use); (c) web research on mockup-engine technique canon + OSS implementations; (d) GitHub metadata verification for the curated repo shortlist (public API + repo pages).
- **Honesty legend (applies to every claim below):**
  - **VERIFIED** — I read it directly in a live public source this session (or in repo evidence), and quote/point to it.
  - **REPORTED** — stated by a cited third-party/marketing source; plausible but not independently confirmed.
  - **UNKNOWN** — not established by any source found; speculation is marked as such.
- **Scope discipline:** no installs; no paid API calls; no Packify/Pacdora app interaction by this agent; no credentials; only public sources + this repo's own prior evidence. Nothing competitor-owned was copied into our code.

--------------------------------------------------------------------------------

## 1) PROVEN vs INFERRED — what Packify's "photoshoot coordinates" actually do

### 1.1 The public API documentation (the authoritative text)

Source: `research/packify_dyp_re_20261016/packify_public_api_docs_extract.txt` (earlier REA capture of the public docs SPA), cross-checked **live on 2026-10-16** against the docs bundle actually served today: `https://www.packify.ai/mpa/assets/index-xR4wZ2wm.js` (same build hash as the earlier capture; still current).

Exact doc lines (extract file line numbers):

| # | Doc text | What it proves |
|---|---|---|
| L6–7 | "Generate Photoshoots: **Place existing product images** into realistic, AI-generated scenes." | Input is an existing product image; output is a generated scene. |
| L46 | "This endpoint **generates a photorealistic scene around your existing product image**, based on a text prompt or style you provide." | The scene is generated *around* the product image. |
| L47 | `packaging_url` — "URL to the **packaging image or design file**." | One source image (not a mesh/design layer). |
| L48 | `packaging_coordinates` — "A list of coordinate objects describing **how the packaging should be cropped, scaled, and placed**." | 2D placement semantics: crop → scale → place. |
| L51–52 | "Packaging Coordinates Object — Each coordinate object defines how the packaging should be **cropped, scaled, and placed**." | Same. |
| L53–54 | `x`, `y` — "X/Y-position of the packaging **on the final output canvas**." | Placement position on the output canvas. |
| L55–56 | `width`, `height` — "**Display** width/height of the packaging on the final canvas." | Uniform scale box (one width + one height — not 4 corners). |
| L57–60 | `cropX/cropY` — "X/Y-coordinate for cropping from the original packaging source image"; `cropWidth/cropHeight` — "Width/Height of the crop area." | Sub-rectangle crop of the source image. |
| L61 | `rotation` — "Rotation angle in degrees." | Single in-plane rotation. |
| L62–63 | `totalWidth`, `totalHeight` — "Width/Height of the **source image**." | Source dimensions carried for normalization. |

**Live re-verification (2026-10-16, `index-xR4wZ2wm.js`):** the docs table today uses exactly these field names in camelCase — `x, y, width, height, cropX, cropY, cropWidth, cropHeight, rotation, totalWidth, totalHeight` — with the same descriptions. Request body: `image_count, callback_url, packaging_url, packaging_coordinates[], background_url, background_prompt`. Response body: `{ "code": 0, "msg": "SUCCESS", "data": { "project_id": "..." } }`. Async completion via webhook (`Webhook` / `retry-policy` doc sections; callback carries a `request_id`). API credit rates as documented today: **Create a design 20 credits; Create a photoshoot 10 credits** (the app UI, by contrast, advertises Photoshoot at 5 credits on the homepage FAQ — API metering differs).

**Critical negative finding:** there is **no per-corner quad, no homography, no mesh, no UV field, and no transparency/shadow parameter** in the public photoshoot contract. It is a *single transformed rectangle* (crop + uniform scale + rotate + translate) of the product image onto an output canvas. A 4-corner perspective warp onto a pouch *face inside a photo* is **not** what this endpoint exposes.

### 1.2 What the live client adds (same build served today; static public asset only)

Source: `https://www.packify.ai/mpa/assets/index-2t_0hD9_.js` (fetched and searched in-memory this session; same posture as the prior REA bundle analysis).

1. **`extracted_coordinates` is a served object, round-tripped by the client.** The client code destructures `{width, height, x, y, totalWidth, totalHeight, cropWidth, cropHeight, rotation}`, and maps each element to a canvas layer as:
   `{ imgW: width, imgH: height, left: x - width/2, top: y - height/2, originW: cropWidth, originH: cropHeight, backW: totalWidth, backH: totalHeight, rotation: rotation * -1 }`.
   → **`x,y` are CENTER coordinates**; `rotation` in degrees with a client-side sign flip; the object can be an **array** (multiple placed items) or a single object. This is canvas-layer semantics, i.e. exactly the "paste a cropped, scaled, rotated piece of the source image" model from §1.1. **VERIFIED.**
2. **Photoshoot pipeline events (chat flow):** `photoshootHello`, `photoshootCutImage`, `photoshootCutImageError`, `photoshootRecommend`, `photoshootTaskStart` — i.e. **cut out the product image → recommend backgrounds → start task**. Client endpoints observed in code: `POST /api/photoshoot/image/test {image_url, project_id}`; `GET /api/photoshoot/template/list`; `GET /api/photoshoot/landing/template/list`; `POST /api/photoshoot/background {project_id, background_url, extracted_coordinates}` (the client **sends the extracted coordinates back** when a background is applied). **VERIFIED (names/keys only).**
3. **The mockup flow has its own realism vocabulary.** Editor state `mockupConfig` initializes with: `eraseScale: 50`, `lumin_url: ""`, `depthData: ""`, `uvData: []`, `elementData: []`, `default_design_area: 0`, `mockup_template_id: 0`, plus `whiteModelImage` in project info and `transparentUrl` in photoshoot state. Chat events: `mockupRemovebg → mockupGenerate → mockupErase → mockupHandle → mockupInpaint → mockupCustom`; endpoints `POST /api/generate/mockup/removebg {image_url, project_id, pacdora_project_id}`, `POST /api/mockup/erase {…, project_id}`, `POST /api/mockup/result {project_id, mockupConfig, photoShootInfo…}`. **VERIFIED that these fields/events exist; semantics INFERRED** (see below).

### 1.3 Proven / inferred / unknown table

| Claim | Label | Basis |
|---|---|---|
| Photoshoot places ONE cropped, uniformly scaled, rotated rectangle of the packaging image at a position on the output canvas (x,y = center), N of them via `coordinates[]`. | **PROVEN** | Docs fields L48–63 + live bundle; client mapping `left=x-width/2`. |
| The scene around the product is AI-generated from `background_prompt` (or supplied by `background_url`). | **PROVEN** | Docs L46, L49–50 + marketing ("keep your product as it is while generating a new AI background"). |
| Background removal of the uploaded product happens first ("cut image" events; `/api/generate/mockup/removebg`). | **PROVEN** (exists) | Live bundle events + endpoint; marketing page states it explicitly. |
| Coordinates come from the system (`extracted_coordinates` returned by their service) and are reused when a background is applied. | **PROVEN** (round-trip) | Live bundle: `/api/photoshoot/background` receives `extracted_coordinates`; loader sets them from response data. |
| No perspective/homography/mesh surface warp in the photoshoot API. | **PROVEN (by absence)** | Complete docs tables in live bundle contain no such fields. |
| The final output is a **generative re-render around the product** (inpaint/outpaint conditioned on the composited product), not a pure photomontage. | **INFERRED** | "Generates a scene around your product"; ~15 s for 4 images (Packaging School walkthrough); `photoshootTaskStart` after background selection. |
| An explicit relight/harmonization pass on the pasted product exists (e.g., an img2img "harmonize" step). | **UNKNOWN** | No public evidence found; marketing claims "consistency in lighting, angles" only. Do not assert. |
| Mockup studio warps a design onto a photographed surface using `lumin_url` (shading), `depthData` (surface shape), `uvData` (surface parametrization), after erasing the old artwork (`eraseScale`) and on a `whiteModelImage`, with `mockupInpaint`/`mockupGenerate` for finishing. | **INFERRED (strong)** | Field/event names are literal; semantics not documented publicly. This is the single most important inference in this report — and §3 mirrors it with our own deterministic code. |
| Photoshoot itself solves "label looks printed on a pouch". | **NO — disproven** | The photoshoot input is your *already-correct* product image; it never re-warps artwork onto a photographed surface. Packify's surface-realism path is (a) the mockup studio above and (b) Pacdora 3D (§2.8). |

### 1.4 Where Packify's realism actually comes from (for our purposes)

1. **AI mockup generator**: upload flat design/logo → Packify *generates the whole packaging image* around your artwork, then you refine with prompts; dieline export + 3D preview at the end. Their own comparison text: "Traditional mockup tools usually replace a layer inside a fixed image. The artwork can look like it is floating on the surface… Packify generates the complete mockup around your artwork…" — i.e. they *avoid* the deterministic-composite look by regenerating the image (REPORTED, their marketing; consistent with our earlier teardown's "deep agents" layered generation).
2. **Photoshoot**: product photo in, generated scene out; product pixels preserved; 2D placement coordinates. (PROVEN.)
3. **Mockup Studio** (deterministic editor): erase old design → edit new design → generate/inpaint, with luminance/depth/UV data available. (INFERRED semantics, PROVEN vocabulary.)
4. **Dielines & 3D preview**: the Pacdora engine — a true GPU ray-traced surface with textures, lighting and materials (§2.8), embedded in the client (`Pacdora-v1.1.7-*.js` per the earlier REA teardown).

Takeaway: **the realism gap we must close is the deterministic one** (our lane: no cloud gen calls, no 3D engine) — and the industry-standard deterministic recipe is precisely: *crop/scale/warp is table stakes; displacement to surface + luminance multiply + specular + grain + contact shading is what makes it read "printed"* (§2, §3).

--------------------------------------------------------------------------------

## 2) REALISM TECHNIQUES CATALOG (with OSS references and VERIFIED / REPORTED / UNKNOWN labels)

Notation: **[V]** verified mechanics from cited source; **[R]** reported; **[U]** unknown. Star counts/licenses were fetched this session (2026-10-16) via the public GitHub API or repo pages; "activity" = last push date where fetched.

### 2.1 Grayscale displacement-map warping — the core "printed on fabric" trick

The technique (Photoshop canon, trivially portable to `cv2.remap`): build a blurred grayscale copy of the surface photo (shadow=dark, highlight=light), then displace the artwork's pixels by map intensity (default scale 10% ≈ ±5–15 px at photo scale); then **blend the artwork with the underlying surface (Multiply / Soft-Light / "Blend If" partial blend) so fabric shading shows through the ink**; blur the map to follow broad folds without roughening on fabric micro-texture; optionally clip a copy of the surface layer as an overlay to carry shadow across the print. All cited tutorials independently converge on this exact stack:

| # | Source | Label | Key detail |
|---|---|---|---|
| 1 | Adobe — "How to create a displacement map" | **[V]** | Desaturate + contrast a copy → save as PSD → `Filter > Distort > Displace` on the design; fine-tune with blend modes "start with Multiply, Overlay, or Soft Light"; blur the map to avoid jagged edges. |
| 2 | creativepro (Claudia McCue) | **[V]** | "…artwork seems to be floating above the shirt. Change the blending mode … to Multiply, and then the shading of the underlying image shows through." |
| 3 | ncoughlin tutorial | **[V]** | Displace only works on rasterized/smart-object art; then sandwich a copy of the background, clipped, in Multiply — "now it actually looks like the graphic is on the paper instead of floating above it." |
| 4 | Brent Galloway | **[V]** | Displacement map from the channel with most shadow separation; blur; Displace strength 5–10 (15 = drastic); **"Blend If → Underlying Layer" slider split with Alt** as the advanced blend step. |
| 5 | Garment Printing UK | **[V]** | Same recipe; recommends offsets 5–10 and the Blend-If slider "so the fabric of the T-Shirt will now start to show through your design." |
| 6 | Ray Dombroski (T-shirt mockup panels) | **[V]** | Commercial mockup packs ship *per-panel displacement maps* (displacement scale 30 in their guide) + a "Magic Fabric Texture" overlay "to increase the realism of your mockup images". |
| 7 | iDevie creased-text tutorial | **[V]** | Full stack showcase: converted texture → grayscale blur 2px → Displace (stretch to fit) → Bevel/Emboss + Color Overlay + Drop Shadow; "although the fabric's folds are showing through the text, it still looks a bit flat" → then the displacement + layering fixes it. |
| 8 | GIMP Displace reference | **[V]** | Precise algorithm: map gray 0–255, neutral 127.5; displacement = coefficient × scaled intensity; fractional displacement with interpolation; Cartesian + polar modes. This is literally what `cv2.remap` must reproduce. |
| 9 | ImageMagick displacement guide (snibgo) | **[V]** | Relative vs absolute displacement-map math; red/green channels as x/y offsets via `-compose Displace`; `compose:args` = max shift in px. |
| 10 | ImageMagick Examples — mapping/displace | **[V]** | Same model, worked examples (e.g. `dy=10*(2*v-1)` via `-fx`). |
| 11 | ImageMagick Examples — displacement bugs | **[V]** | Implementation caveats/masking pitfalls (alpha vs color channels) — useful for our own remap implementation. |

**OSS implementations to copy the *approach* from (not the code):**

| Repo | ★ | License | Activity | Why it matters for us |
|---|---|---|---|---|
| `JohnAnon9771/mockup-generator` (Ruby) | 22 | none declared | pushed 2025-10-05 | Generates **adjustment, displacement and lighting maps** from template+mask, then composites — a named blueprint of the exact three passes. |
| `kashifulhaque/product-mockup-node-python` | 48 | none declared | 2023-06-10 | ImageMagick pipeline: `convert … $displacement_map -compose displace -set option:compose:args 20x20 -composite`, then color-adjust via multiply + CopyOpacity, then composite over template with mask. The "-compose displace 20x20" is our `cv2.remap` max-shift parameter. |
| `rmenon1008/mockupgen` | 66 | MIT | 2023-07-18 | Device mockups via template corner points + brightness/contrast adjustment; shows the "bake params into a JSON template" pattern we should adopt. |
| `smile101603/Automated_Mockup_Generator` | 0 | MIT | 2026-03-30 | Placeholder-color detection + rotation support + batch; relevant if we ever auto-detect print areas by marker. |

**Note for `compose_mogra_complete.py`:** `warp_panel()` currently samples the panel through the inverse homography only. The upgrade is a *second* sampling offset: build `D(x,y)` = Gaussian-blurred luminance of the base plate inside the face quad (radius ≈ fold scale, ~6–10 px at our 1216×832 plate), minus its local mean, scaled to a max shift (start 0.02 of face width, tune to match PS default-10% feel), and sample the panel at `(u + kx·Dw, v + ky·Dv)` in *panel space*. Our panel is authored at 2.5× so 1 render-px of displacement = 2.5 panel-px of UV — convert accordingly. This alone removes most of the "sticker" reading (all 11 sources above say so).

### 2.2 Non-rigid / mesh warps fitted to detected geometry (TPS)

For creases that corner-homography can't follow (wrinkled pouches, pillow-shaped film), fit a smooth non-linear map to a sparse set of correspondences (e.g., 6–20 control points placed along crease ridges, or the four corners plus midpoints pulled toward the crease path). TPS is the standard choice; it is the same warp used by garment virtual try-on to deform a flat garment into photographed fabric.

| Tool/library | ★ | License | Activity | Note |
|---|---|---|---|---|
| `scipy.interpolate.RBFInterpolator` (kernel `'thin_plate_spline'`, `r²·log r`, smoothing, `neighbors`) | — (SciPy) | BSD-3 (SciPy) | SciPy 1.18 docs | **Stock-dependency TPS fitting.** Sample a coarse grid (e.g. 40×60), fit displacement field, feed `cv2.remap` or PIL. Zero new deps. |
| `raphaelreme/tps` | 38 | MIT | 2026-02-12 | NumPy/SciPy TPS with a **dedicated image-warping example** (`example/image_warping.py`) — closest drop-in. |
| `raphaelreme/torch-tps` | 41 | MIT | 2026-02-12 | GPU variant if we ever batch. |
| `scikit-image` `ThinPlateSplineTransform` (+ `warp`) | 6,613 | BSD-3-Clause | 2026-10-09 | Documented TPS class w/ estimation from src→dst point sets; official "TPS deformation" example notebook. Note: skimage `warp` needs the **inverse** transform — pass dst,src. |
| `AlanLuSun/TPS-Warp` | 20 | none declared | 2021-08-25 | Shows `cv2.createThinPlateSplineShapeTransformer` usage — **requires `opencv-contrib-python`** (mainline `opencv-python` lacks it). Our constraint says OpenCV+PIL; scipy route avoids the contrib dependency question entirely. |
| `olt/thinplatespline` | 48 | README says MIT; GitHub metadata shows none | 2022-03-31 | GDAL-derived `from_control_points`/`transform`, tiny API. |
| `xmba15/thin_plate_spline_warping` | 2 | none declared | 2024-06-05 | Minimal TPS warping samples incl. blending with the reference. |
| `xthan/VITON` | 582 | none declared | (2018 paper code) | Precedent: flat garment warped by TPS control points (shape-context) onto a photographed body — "warp the cloth while preserving original details, conforming to shape". Same math applies to "flat label → photographed pouch". |
| `NerdFNY/MCG-VITON` | 9 | (see repo) | 2022 | Contains a clean NumPy `TPS_STN` (grid control points, `r²log r`, `np.linalg.inv(W)`) — a compact TPS reference implementation. |

**Note for our compositor:** our `FACES` quads are hand-measured per SKU. A TPS upgrade path is: keep the 4 corners (still the best global registration), insert 4–8 additional control points derived from crease/pinch detection (see §3 step 5), fit TPS over the *render-px displacement* of a coarse grid, and reuse the existing sampler. Do not replace the homography with TPS wholesale — TPS extrapolates badly outside control hulls; use it only to refine inside the face quad.

### 2.3 Lighting transfer: Multiply / Soft-Light / specular passes — and the harmonization gap

| Technique | Evidence | Label |
|---|---|---|
| Multiply the print by the surface shading (darkens print where the surface is dark; the classic step) | Adobe/creativepro/ncoughlin (§2.1) | **[V]** |
| **Soft-Light / Overlay instead of pure Multiply** to keep midtone print color from going muddy | Adobe help: "start with Multiply, Overlay, or Soft Light" | **[V]** |
| **Blend If (Underlying Layer)** to let deep shadows punch through only where the surface is dark (protects white/cream inks) | Galloway; Garment Printing UK | **[V]** |
| **Specular pass**: add the surface's highlights ON TOP of the print (screen/add, thresholded luminance) — real film/pouch sheen lies over the ink | iDevie layering; Ray Dombroski "Magic Fabric Texture"; MCue's clipped-overlay trick (copy of the surface above the art) | **[R]** (canon practice, described in tutorials as the finishing pass) |
| Industry mockup APIs expose exactly these knobs for smart objects: per-object `blending_mode` (full PS set incl. `MULTIPLY`, `SOFT_LIGHT`…), `adjustment_layers {brightness, contrast, opacity, saturation, vibrance, blur}`, and state that **"scene lighting and shading still apply"** | Dynamic Mockups public API reference + help center | **[V]** |
| **Harmonization is a real, benchmarked problem** — "image harmonization" is the academic name for making a composite read as one photo; iHarmony4 (HCOCO/HAdobe5k/HFlickr/Hday2night) is the standard benchmark; input composites score fMSE ≈1387 vs ≈179–238 for the best models — i.e. *naive compositing is measurably far from real, and the gap is dominated by color + light transfer*, not geometry. | `bcmi/Image-Harmonization-Dataset-iHarmony4` (812★, MIT, active 2026-08-20); paper CVPR 2020 | **[V]** |
| ML relighting that we could eventually use offline (not today's Python-only lane): IC-Light — background-conditioned relighting diffusion; "Imposing Consistent Light"; can even merge relightings into normal maps. | `lllyasviel/IC-Light` (8,546★, Apache-2.0, pushed 2025-02-20) | **[V]** |
| Photoshop 2026 product side: "Rotate Object → Harmonize → Generative shadow" — Adobe's own narrative confirms the three composite tells: wrong angle, wrong ambient light, **missing contact shadow**. | PHLEARN 2026 tutorial | **[R]** |

**Note for our compositor:** today `main()` applies `lum_ratio` (clamped 0.90–1.08) at 55% strength over the *whole face bbox*, after warping both SKUs. Upgrade: (a) compute the shading field from the plate, blur radius ≈ face height/40; (b) blend the *printed region only* at 85–100% via a Soft-Light-style operator `out = base * (1 - a) + screened(print, shade) * a` (implement soft-light as `x + (2m-1)·x·(1-x)` per channel on normalized values) rather than a plain multiply at 55%; (c) add the specular pass: `hi = clip((blur(base_lum) - 0.85)·k, 0..1)`; `out += hi·print` (screen-like) inside the mask — this is what sells "glossy film with print under it"; (d) keep the clamp tiny so we never blow the print's contrast.

### 2.4 Depth / normals from a single photo → conformal warp + correct shading

The limiting case of 2.1: instead of a luminance proxy, get the actual surface geometry of the pouch from the plate, then (a) displace the print by the depth gradient (like a sculpted displacement), and (b) light the print with the same normals the real pouch would have (Lambert + specular). Both are deterministic post-hoc computations over a monocular-depth/normal map.

| Tool | ★ | License | Activity | Note |
|---|---|---|---|---|
| `DepthAnything/Depth-Anything-V2` | 8,967 | Apache-2.0 code; **v2-Small weights Apache-2.0**, Base/Large/Giant weights **CC-BY-NC-4.0** | 2026-03-24 | Best quality/size tradeoff for offline; use Small for the commercial-safe lane. |
| `LiheYoung/Depth-Anything` (v1) | ~8k | Apache-2.0 (weights investigated in issues) | — | Fallback. |
| `isl-org/MiDaS` | 5,419 | MIT | **ARCHIVED** (2024-08-23) | Legacy fallback; archived = note for maintenance. |
| `Stable-X/StableNormal` | 785 | Apache-2.0 | 2025-08-02 | SIGGRAPH Asia 2024 monocular **normal** estimation, "stable and sharp"; paper states normals enable "relighting or intrinsic decomposition" directly — exactly our use. |
| `baegwangbin/DSINE` | 930 | license shows "Other" (custom) on GitHub | 2024-07-10 | CVPR 2024 crisp normals; check the license file before shipping. |

Academic anchors: Depth Anything V2 (NeurIPS 2024, arXiv 2406.09414) — "affine-invariant inverse depth", robust to transparent surfaces (pouches!); StableNormal (arXiv 2406.16864) — normal maps as "2.5D representation bridging 2D and 3D… enables relighting". **[V]**

**Note for our compositor:** today's base plate already *contains* the pouch's shading; we don't strictly need a net to start — a finite-difference gradient of the blurred luminance gives a serviceable pseudo-normal field (`N ≈ normalize(-∂L/∂x, -∂L/∂y, k)`). Steps: (1) pseudo-normals from luminance now (§3 step 5); (2) optional offline pass with Depth Anything V2-Small (Apache-2.0) to get depth for a true cross-check, especially on the two-pouch scene where luminance mixing hides geometry; (3) drive both displacement and a specular map from the same normals.

### 2.5 Shadows & occlusion where the label meets the pack

| Technique | Evidence | Label |
|---|---|---|
| Shadow anatomy: **contact shadow** (tight, dark, at the junction) + **mid falloff** (low-flow, larger) + **ambient** (very soft, offset) + **a clipped pass painting shade onto the object itself** | PHLEARN "Realistic shadows"; pslover "contact/cast/ambient"; pslover warns: drop-shadow effect alone reads artificial; sample shadow color from the object, not pure black | **[V]** |
| The #1 "looks fake" tell is the missing contact shadow ("the object appears to hover a few millimeters above the ground — that's the effect people describe as 'looking fake' without knowing why") | PHLEARN 2026 | **[V]** |
| **Soft-shadow generation from a mask** (SSN), **controllable shadow via pixel-height maps** (ECCV 2022), ShadowGAN, and the 2024–2026 diffusion line (SGDiffusion → GPSDiffusion, DESOBAv2; one-step controllable shadow arXiv 2412.11972) | `bcmi/Awesome-Object-Shadow-Generation`; `bcmi/Object-Shadow-Generation-Dataset-DESOBAv2`; `bcmi/GPSDiffusion-Object-Shadow-Generation` (152★, MIT); `bcmi/libcom` (741★, Apache-2.0, active 2026-10-05 — open-source image-composition toolbox with shadow generation integrated); note their own caveat: GPSDiffusion "performance is unstable — generate multiple and pick" | **[V]** (existence + scope), **[R]** (quality claims) |
| **Ambient occlusion by darkening the surface at the print's boundary** — for a printed label the junction is not a cast shadow but a subtle occlusion/crease darkening at the print's edge and in local folds; in PSD practice this is the "paint shadow onto the object, clipped" layer, generalized | PHLEARN shadow stack | **[R]** (standard practice; no single canonical paper for the label-edge case) |
| Wrinkle shadows *over* print: where a fold crosses the print, the fold's shadow must darken the print **and** its specular highlight must brighten it, or the fold looks like a print distortion | iDevie (crease lighting stack); 2.1 sources | **[R]** |

**Note for our compositor:** our discs/badges already get soft alpha-black drop shadows (SS'd at `build_panel`); real printed badges don't cast shadows — replace those with (a) an **edge AO pass**: darken 1–3 px *inside* the panel boundary by 3–6% and add a 1–2 px slightly-darker rim on the surface *outside* the print (a faint seam, not a shadow); (b) our roundel discs should get a tiny emboss if the brand prints raised varnish — UNKNOWN whether they do, so keep flat and let the shading do the work; (c) for folds crossing the print, the §3 step-1 displacement plus the §3 step-3 grain and a directional fold-shadow pass (threshold the negative curvature of the shading field; offset along light direction; multiply only where the fold darkens the surface) gives the "ink goes into the crease" read.

### 2.6 Print texture & ink simulation (why clean vector print reads "digital")

| Technique | Evidence | Label |
|---|---|---|
| **Grain/micro-texture overlay on the print** (multiply a tileable grain at low amplitude) syncs the print with the photo's own grain and kills the "vector-clean" look; mockup packs ship this as "Magic Fabric/Every Day textures" | Ray Dombroski guide; iDevie (soften + re-texture steps) | **[V]** |
| **Print-process simulation as a first-class API concept**: Dynamic Mockups' `decoration_method` — `universal`, `screen_print`, `dtg`, `uv_print`, `laser_engrave_surface/deep`, `deboss` — with the documented statement that these "simulate a physical print or engraving process and **intentionally alter the artwork's colors (ink absorption, desaturation, fabric show-through)**… most visibly on dark garments"; deboss exposes `depth, shadow_falloff, shadow_darkness, highlight_brightness, center_darkening` | Dynamic Mockups docs (public) | **[V]** |
| **Halftone / screen angle / dot gain** for a screen-print look: `rosette-halftone` (PyPI; CMYK separations, US/EU screen angles, TAC cap, SWOP ICC via lcms2/`PIL.ImageCms`, gamma/dot curve; AGPL-3.0-or-later — mind the license), `philgyford/python-halftone` (103★, Pillow, CMYK channels + angles, no license declared), `schwanksta/Halftones` (Tauri app, spot-color separation, key plate, dot gain compensation), `souheyell/bwLabSP` (browser RIP: OKLab luminance, **Kubelka-Munk ink simulation**, AM/FM screening, dot gain/dot ellipticity — a full model of "ink physically sitting on fabric"), plus academic tooling "Raster Halftone Lab" (Zenodo, 2026: AM/FM screens, rosette generation/detection, TVI = tone value increase) | see sources list | **[V]** (projects exist and do this), **[R]** (fidelity for our use case) |
| **Color management basics**: author in sRGB → approximate print appearance (gamut compression, slight desaturation for flexo/roto film, TAC ceiling); precise soft-proofing via ICC needs a profile file and LittleCMS (`Pillow.ImageCms`; `rosette-halftone` demonstrates lcms2 + SWOP in pure Python). `colour-science/colour` (2.7k★, BSD-3-Clause) for color-space math | Pillow ImageCms docs; rosette-halftone "How it works"; colour repo | **[V]** (capabilities), **[R]** (exact film-print simulation fidelity) |
| Screen-print vs digital-print *visual* difference for our purpose: screen/flexo = slightly irregular edges, dot gain on fine type, ink show-through on dark film; digital/HP Indigo = cleaner, higher gamut. For our matte dark film pouch with cream ink, the tell is **soft-edged ink with slight show-through + micro dot texture on fine strokes** — approximated by (a) 0.5–1 px blur of the ink alpha at print scale, (b) 4–8% opacity noise keyed to the ink mask, (c) tiny saturation drop | synthesis of the above; specific values from us | **[R]** (technique direction), values are our proposal |

**Note for our compositor:** our panel is authored at 2.5×; apply texture at *print* scale (panel-space), not render-space: (1) multiply the panel by `1 + g·grain` where grain = high-pass of the existing `grain_patch` (already measured in `heal_regions`!) tiled at the panel's native scale; (2) slight ink-edge softening: blur the panel's ink alpha by 0.4×PANEL_SCALE before compositing (currently a global 0.6 blur on the whole panel); (3) if we want the *craft* look: 2–5% amplitude ordered-dither noise on the ink mask only (cheap multi-level halftone, no separate lib needed); (4) optional soft-proof lane: convert authored cream/gold through a sRGB→CMYK(→sRGB) round-trip with TAC clamp to discover out-of-gamut colors before they surprise us.

### 2.7 Matte/compositing utilities

| Tool | ★ | License | Note |
|---|---|---|---|
| `danielgatis/rembg` | 25.1k | MIT | U²-Net-family background removal (CLI/library/server). Mirrors their `mockup/removebg`; useful for cutout-based scene lanes. |
| OpenCV `seamlessClone` (Poisson editing) | — | Apache-2.0 (OpenCV) | Verified in the public docs this session. For softly inserting shadows/patches with gradient continuity (used in PHLEARN-style shadow stacks and IM examples). |
| `psd-tools` | 1.5k | MIT | Reads/composes PSD; **explicitly does not support smart objects** — if we ever adopt PSD templates, this is a hard limitation; our parametric approach avoids it. |
| `kornia/kornia` | 11,432 | Apache-2.0 | GPU `warp_perspective` / `remap` / transforms if any part of the lane ever moves to torch. |
| Pillow `Image.transform` (QUAD/PERSPECTIVE/**MESH**) & `ImageTransform` | — | HPND (Pillow) | Verified transform documentation; MESH gives a pure-PIL mesh warp (slower than `cv2.remap`, but zero new deps). |

### 2.8 The 3D route — what Pacdora (Packify's parent engine) actually does

Pacdora's public engineering write-up ("Revolutionizing 3D Rendering with Pacdora Technology", ≥2024-11-17) states their pipeline is a **true GPU ray tracer**: GGX BRDF sampling, rectangular/spherical light sampling, "maximum of … reflections and 8 refractions per ray", a two-level acceleration structure, server-side dieline/material/render task distribution, preview/offline renderer integration (2022→2023 timeline), and packaging-specific finishes — **foil stamping, UV, embossing**. Their dieline tooling folds cut-and-crease SVG/DXF into an interactive 3D model with configurable fold direction/animation; the Editor SDK embeds the real-time 3D editor; the Illustrator plugin previews 3D in-app. Marketing (PR Newswire, 2025-07-09): Editor API = 3D preview + dieline generation + quote parameters. **[V]** for the claims as published; **[R]** for implementation details beyond the article.

**Implication (UNKNOWN whether it matters for us):** Packify's photo-real label rendering is *3D texture-mapping + PBR lighting* with curated materials, i.e. it sidesteps the 2D-composite problem entirely — but it requires meshes and rendering infrastructure we deliberately do not have. Our 2D path must therefore emulate the *result* (surface-conforming warp + shading + ink physics), which is exactly §2.1–2.6. Their client's `lumin_url`/`depthData`/`uvData` in the mockup editor suggests even they mix a 2D luminance/depth/UV composite path for real-photo mockups — supporting our investment in the 2D lane.

--------------------------------------------------------------------------------

## 3) RECOMMENDED UPGRADE PATH for `scripts/compose_mogra_complete.py` (ordered by realism-per-effort)

Baseline recap (current file): hand-measured 4-corner quads per SKU (`FACES`); panel authored at 2.5× with real brand assets; per-pouch `lum_ratio` (blurred plate luminance / median, clamped 0.90–1.08) blended at **0.55** over the whole face bbox after warping; `heal_regions()` already measures high-frequency grain from a clean patch and re-injects it into healed areas; `warp_panel()` bilinear-samples through the inverse homography; one global 0.6 blur on the panel before warp.

Each step below: **what changes, why it works (evidence), effort S/M/L, risk.**

### Step 1 — Luminance-driven displacement inside the warp (S)
- **What:** in `warp_panel()`, after computing `(u,v)` for each destination pixel, offset by `(u + kx·Dj, v + ky·Dj)` where `Dj` is the blurred plate luminance (radius ≈ 6–10 px at render scale) minus local mean, normalized to a max shift (~1.5–3 render px = 4–7 panel px at 2.5×). Generate once per face, same code that already computes `lum_ratio`.
- **Why:** the core "printed on fabric" mechanism in every cited source (§2.1) — artwork follows folds instead of floating over them. This is the single biggest visual gain in the whole list.
- **Effort S. Risk:** over-displacement waffles text; keep max shift ≤ 0.6% of face height initially; add a sidecar parameter `displacement_kx/ky` and clamp; verify against the debug stage images already emitted with `--debug`.

### Step 2 — Print-grain sync + ink micro-texture (S)
- **What:** reuse the grain field measured in `heal_regions()` (`grain_patch`) and (a) add it to the panel's RGB at ±2–4/255 amplitude in panel space before warping, keyed to the panel's ink alpha (so it interacts with ink, not just luminance); (b) soften ink edges by blurring only the panel's **alpha** by ~0.4×PANEL_SCALE px before the existing global blur.
- **Why:** matches the plate's own grain (kills "clean vector"), and matches how screen/flexo ink edges read (§2.6). The plate is matte film; its grain is already measured — this is a pure code reuse.
- **Effort S. Risk:** grain in the wrong scale doubles up; verify by differencing a print-only crop at 200% zoom.

### Step 3 — Lighting upgrade: Soft-Light shading + specular pass (S–M)
- **What:** replace the 0.55 blend of `lum_ratio` with (a) a Soft-Light-type operator applied at ~0.9 strength inside the panel mask (implement `softlight(b, s) = b + (2s-1)·b·(1-b)` on normalized channels, with `s` = blurred plate shading normalized to 0..1 around its median); (b) a specular pass: `hi = clip((blur(plate_lum) - p)·q, 0, 1)`, screened **onto** the printed region (`out = 1 - (1-out)·(1-hi)`) — the plate's sheen sits on top of the ink.
- **Why:** Multiply-only darkens and kills cream ink; the canon says "Multiply, Overlay, or Soft Light, start" and the overlay-copy-of-surface trick is specifically for the sheen (§2.3). Dynamic Mockups exposes exactly this as per-object controls and states scene lighting still applies.
- **Effort S–M (two operators + mask plumbing; the plate blur already exists). Risk:** over-bright speculars; cap `hi` at ~0.35 and restrict to the face quad.

### Step 4 — Print-edge grounding: AO rim + seam (S)
- **What:** (a) darken 2–4 px inside the panel boundary by 3–6% (multiply with a soft-edged rim mask derived from the panel alpha); (b) add a 1–2 px, 8–12% darkening just **outside** the panel alpha on the surface (faint junction seam); (c) keep the existing badge/disc shadows but reduce them ~50% (they are print, not floating discs) or replace with the same AO rim per disc.
- **Why:** the "hovering" tell is a missing junction/contact term (§2.5 canon; PHLEARN 2026 explicitly). For print, the analog is a subtle occlusion/seam, not a drop shadow.
- **Effort S. Risk:** a visible black outline looks worse than nothing — keep ≤6% and check at 100%.

### Step 5 — Crease-fitted TPS refinement + pseudo-normals (M)
- **What:** detect crease candidates as ridges of the blurred luminance gradient inside the face quad (DoG + hysteresis, or simply the top-k gradient magnitude pixels with NMS); fit `scipy.interpolate.RBFInterpolator(kernel='thin_plate_spline', smoothing=ε)` mapping a coarse grid (e.g. 48×72) to displaced positions (push sampling points along crease normals by a fixed fraction of the fold's luminance amplitude); feed the resulting field into the same `cv2.remap`-style sampler as Step 1 (Step 1 becomes the low-frequency term, TPS the high-frequency term). Additionally derive `N ≈ normalize(-∂L/∂x, -∂L/∂y, k)` from the blurred plate to modulate the specular pass in Step 3 directionally.
- **Why:** TPS is the established warp for conforming flat art to photographed fabric (VITON family, §2.2), and it is the exact mechanism Packify's editor vocabulary hints at (`uvData`, `depthData` in `mockupConfig`). Stock SciPy — no new deps.
- **Effort M. Risk:** bad control points create weird warps; constrain control points inside the face convex hull; keep TPS ≤ 40% of total displacement; add `--tps` debug overlay.

### Step 6 — Fold shadows *over* the print (M)
- **What:** from the negative-curvature regions of the plate shading, build a fold-shadow mask (where the surface darkens relative to local median beyond a threshold); multiply the print in those regions by the same darkening factor (currently partially covered by `lum_ratio`, but only globally); optionally offset the darkening by 1–2 px along the estimated light direction.
- **Why:** where a real fold crosses print, the ink darkens in the fold and highlights on the ridge (§2.5 [R]); the current global ratio can't express this.
- **Effort M. Risk:** double-darkening with Step 3; make the passes complementary (Step 3 = low-frequency shading; Step 6 = local folds only).

### Step 7 — Depth/normal model pass (optional offline, M–L)
- **What:** run Depth Anything V2-Small (Apache-2.0 code+weights; or StableNormal if normals are wanted directly) once per base plate, cache the maps in `renders/` next to the plate, and use depth for (a) a true conformal displacement, (b) normal-based Lambert+specular instead of the luminance proxy.
- **Why:** highest ceiling for pillow-shaped film where luminance is ambiguous; enables correct relighting (§2.4). Also mirrors the `depthData`/`lumin_url` pattern Packify's own editor carries.
- **Effort M–L (model run + caching; no live calls — local inference only). Risk:** model license nuance — keep to V2-Small (Apache-2.0) for commercial use; larger weights are CC-BY-NC-4.0.

### Step 8 — Print-process simulation knobs (M, optional/cosmetic)
- **What:** a small `print_sim` block: (a) ink show-through on dark film = blend 3–6% of the surface luminance into the ink; (b) dot-gain: dilate the ink mask by ~0.02% of face width (sub-pixel at plate scale, simulated via alpha gamma ≈ 1.05); (c) optional ordered-dither micro-halftone on the ink alpha (4–8 levels) if we ever want a visible screen-print texture; (d) TAC/gamut guard: flag authored colors that would clamp in CMYK and auto-nudge (cream #F3EAD6 is safely in gamut; gold #C4A04A near the edge — verify).
- **Why:** Dynamic Mockups exposes `decoration_method` semantics exactly because it changes consumer perception on dark substrates (§2.6); benefits us most on the *cream-on-near-black film* case, which is precisely our SKUs.
- **Effort M. Risk:** over-doing it turns premium matte into cheap print; keep amplitudes tiny; gate behind flags (their "deterministic + parameter sidecar" ethos) and A/B against the current output.

### Step 9 — Scene-level finish (S, once steps 1–4 land)
- **What:** micro-vignette and white-balance snap: measure the plate's white balance/black point in the quad, and grade the *composited region* with the same 2-point curve for tonal consistency; ensure the print's blacks/whites match the plate's curve endpoints.
- **Why:** harmonization evidence (§2.3) — most composite mismatch is tonal, not geometric; a 2-point match is a poor-man's "Harmonize" and free to implement.
- **Effort S. Risk:** avoid globally re-grading the whole photo; only the composite needs it if authored assets are "too clean".

Ranking sanity check (realism gain ÷ effort): **1 → 2 → 3 → 4 → 5 → 6 → 8 → 9 → 7**. Do 1–4 in one commit (they are all local to `warp_panel`/`main`), validate with `--debug` stage images and a side-by-side, then decide on 5+.

Cheap validation harness (S): render a 3-up comparison (current / +steps1-2 / +steps1-4) at 100% crop of the front panel + full frame, write into `renders/` with a JSON sidecar of parameters — matches the repo's evidence discipline without new deps.

--------------------------------------------------------------------------------

## 4) SPEC — passive REA capture of the Packify photoshoot + mockup flows (for later; DO NOT RUN as part of this deep dive)

**Goal:** confirm with first-hand request/response shapes what §1 infers: real `extracted_coordinates` values and array behavior; what `/api/photoshoot/background` does with them; what the mockup editor actually receives in `lumin_url` / `depthData` / `uvData` / `default_design_area` / `elementData`; the true order of cut → recommend → background → task → result; and (secondary) whether any harmonization/relight step exists visually.

**Posture (non-negotiable):** operator drives every click; agent only observes passively (REA attached to the operator's Chrome via CDP); no credentials entered by tooling; no CAPTCHA; no form submission by the agent; value-free body *shapes* only (URLs/tokens/UUIDs scrubbed); no API-key usage; the public B2B API is documented in §1 and should NOT be called — the paid endpoint test is out of scope.

**Preconditions:**
- Operator signed into Packify in the dedicated REA Chrome profile (as in the 2026-10-16 session).
- Note the currently served build hashes first (they may change): Docs/app chunk `index-xR4wZ2wm.js` and shell `index-2t_0hD9_.js` (fetched 2026-10-16). If hashes differ, re-read them (they define the field vocabulary).
- Have a *test* product image the operator owns (e.g. our own `renders/mogra-forest-dusk-mockup-complete.png` — a render we own; do not upload third-party assets).

**Pages/actions to observe (operator-driven):**
1. `https://www.packify.ai/photoshoot` — landing: capture `/api/photoshoot/landing/template/list` (categories, params).
2. Photoshoot flow: upload the test image → observe `POST /api/photoshoot/image/test` (request `{image_url, project_id}`; response schema — this is where an initial `extracted_coordinates` may arrive). If the UI shows a "cut/remove background" step, note the event and any credit delta.
3. Choose a background template, then a second run with a custom prompt; observe `GET /api/photoshoot/template/list`, `POST /api/photoshoot/background {project_id, background_url, extracted_coordinates}` — **capture the exact `extracted_coordinates` payload** (single object vs array; numeric ranges; rotation values; whether crop fields equal source bounds or a sub-rect). Capture `photoshootRecommend` / `photoshootTaskStart` socket frames, then the result delivery (socket vs polling; `result_list` structure; timings; credits consumed).
4. Mockup Studio (AI mockup flow in the chat app): start a mockup for a pouch/bag; upload the test photo; trigger the erase step if offered (observe `POST /api/mockup/erase` request keys — expect an erase area/scale); place/replace the design; press Generate; observe `POST /api/mockup/result` **request and response** — specifically the formats of `lumin_url` (URL to what kind of image?), `depthData` (URL? inline array? resolution?), `uvData` (array of what?), `default_design_area` (shape/units), `elementData`/`item_list`, `whiteModelImage`, `transparentUrl`; also `POST /api/generate/mockup/removebg` request/response, and `POST /api/pacdora/link` (bridge payload) if triggered by "3D/Edit dieline".
5. Dieline/3D: open the dieline editor for the mockup and note the 3D preview trigger (Pacdora engine load; any `/api/pacdora/*` calls).
6. Optional: one AI Mockup Generator run from `/aimockup` to record its request shapes (chat/deep-agent endpoints) — secondary.

**Extraction targets (value-free shapes, with numeric ranges where non-sensitive):**
- Request/response JSON schemas for: `/api/photoshoot/image/test`, `/api/photoshoot/template/list`, `/api/photoshoot/landing/template/list`, `/api/photoshoot/background`, `/api/mockup/erase`, `/api/mockup/result`, `/api/generate/mockup/removebg`, `/api/pacdora/link`.
- Socket.io frames (path `/io/`): event names + payload shapes for `photoshootHello`, `photoshootCutImage`, `photoshootCutImageError`, `photoshootRecommend`, `photoshootTaskStart`, and the mockup legend (`mockupRemovebg`, `mockupGenerate`, `mockupErase`, `mockupHandle`, `mockupInpaint`, `mockupCustom`).
- `extracted_coordinates`: element count, key set, value ranges, center-vs-topleft confirmation (compare to on-screen placement at two canvas sizes), rotation sign, crop ratios vs `totalWidth/Height`. **Redact nothing here numerically — coordinates are geometry, not secrets — but scrub any URLs/UUIDs/tokens.**
- Asset URLs found in responses (lumin/depth/UV/transparent/white-model): record the *kind* (PNG? JSON? size?) and hotspots, not the full signed URLs (scrub query strings).
- UI + result evidence: screenshots (before/after each step), output images, credit badge before/after, wall-clock durations.
- Visual realism checklist on outputs: shadows under the product (contact), perspective match, any visible re-lighting of the product, whether the product's logo/text stayed pixel-identical (their "keep product as is" claim).

**REA command shapes (from the earlier session, reuse as-is; operator drives):**
```bash
rea inspect-web-page http://127.0.0.1:9222 <TARGET_ID> --observation-ms 1500 --include-script-sources --json
rea inspect-web-page http://127.0.0.1:9222 <TARGET_ID> --observation-ms 360000 --include-json-body-shapes --include-websocket-shapes --json
rea capture-web-screenshot http://127.0.0.1:9222 <TARGET_ID> --json
rea export-web-scripts <capture.json> <outdir> --json
rea analyze-web-bundle http://127.0.0.1:9222 <TARGET_ID> --fetch-source-maps --json
```

**Acceptance criteria:** ≥1 real `extracted_coordinates` payload with ≥4 numeric fields documented; response schema for `image/test`; observed cut→recommend→background→task sequence with timing; mockup generate request/response captured with the formats of `lumin_url`/`depthData`/`uvData`; ≥1 credit-delta observation per flow; screenshots of each step; all evidence value-free (no cookies/auth headers/URL tokens) and stored under `research/packify_quality_deep_dive_20261016/` (or a dated pack next to it).

**Circuit breaker:** if any capture window ends without completing (as happened on 2026-10-16), persist the partial envelope and STOP — no auto-retry (per constitution).

--------------------------------------------------------------------------------

## 5) TOP FINDINGS TABLE (the ~24 that matter, with metadata as of 2026-10-16)

| # | Finding / source | Type | ★ / activity | License | Note for our compositor |
|---|---|---|---|---|---|
| 1 | Packify photoshoot docs fields (LIVE bundle §1.1–1.2) | doc | build 2026-10-16 | — | Confirms 2D crop/scale/rotate/place; copy the rectangle model for our API lane, but realism must come from §3 passes. |
| 2 | Packify app `mockupConfig`: `lumin_url, depthData, uvData, eraseScale, default_design_area, whiteModelImage` | bundle | 2026-10-16 | — | The exact realism stack to mirror: luminance multiply + depth/UV warp + erase/inpaint. |
| 3 | Dynamic Mockups Render API (`decoration_method`, blending modes, adjustment layers) | API docs | 2025–2026 | — | Names the industry knobs: `screen_print`/`dtg`/`uv_print`/`deboss` + per-object blend/adjust; implement analogous params on our panel. |
| 4 | `bcmi/libcom` | repo | 741★, 2026-10-05 | Apache-2.0 | Composition toolbox incl. shadow generation + harmonization reference for evaluation, not runtime. |
| 5 | `bcmi/Image-Harmonization-Dataset-iHarmony4` | dataset | 812★, 2026-08-20 | MIT | Quantifies the realism gap (fMSE 1387→179); justifies investing in lighting transfer, not just geometry. |
| 6 | `bcmi/GPSDiffusion-Object-Shadow-Generation` | repo | 152★ | MIT | Modern shadow-from-mask model; use for a *study* of plausible contact shadows; unstable per authors — pick-best. |
| 7 | `bcmi/Object-Shadow-Generation-Dataset-DESOBAv2` | dataset | (repo active 2024+) | (see repo) | Backing data for #6; useful if we train/benchmark a lightweight 2D shadow assist. |
| 8 | PHLEARN contact-shadow anatomy (+2026 Harmonize workflow) | tutorial | 2021–2026 | — | Our badge/disc "drop shadows" should become junction AO + layered falloff (§3 step 4). |
| 9 | Adobe displacement-map guide | doc | — | — | Canon: blur map → Displace → Multiply/Overlay/Soft-Light; the exact pipeline for §3 steps 1+3. |
| 10 | GIMP Displace reference | doc | — | — | Algorithm spec (map 0–255, neutral 127.5, coefficient×intensity, interpolation) to reproduce in NumPy. |
| 11 | ImageMagick displacement guides | doc | — | — | Relative/absolute map math + `compose:args` max-shift semantics (= our remap scale). |
| 12 | `raphaelreme/tps` (+`torch-tps`) | repo | 38★/41★, 2026-02-12 | MIT | Ready TPS fitting + image-warp example → §3 step 5. |
| 13 | `scikit-image` `ThinPlateSplineTransform` + TPS example | repo/docs | 6,613★, 2026-10-09 | BSD-3 | Alternative TPS; remember `warp()` wants the inverse transform. |
| 14 | SciPy `RBFInterpolator(kernel='thin_plate_spline')` | docs | v1.18 | BSD-3 | Zero-new-dep TPS via stock SciPy; `neighbors=` for speed. |
| 15 | `DepthAnything/Depth-Anything-V2` | repo | 8,967★, 2026-03-24 | Apache-2.0 (Small) / CC-BY-NC (big) | Offline depth for conformal warp; stay on Small for commercial safety. |
| 16 | `Stable-X/StableNormal` | repo | 785★, 2025-08-02 | Apache-2.0 | Normals → directional specular (§3 steps 5/7). |
| 17 | `lllyasviel/IC-Light` | repo | 8,546★, 2025-02-20 | Apache-2.0 | The ML "harmonize" lane if we ever add a gen step; not needed for deterministic pass. |
| 18 | `baegwangbin/DSINE` | repo | 930★, 2024-07-10 | custom ("Other") | Check license before any use. |
| 19 | `JohnAnon9771/mockup-generator` | repo | 22★, 2025-10-05 | none declared | Blueprint: adjustment + displacement + lighting maps from template+mask. |
| 20 | `kashifulhaque/product-mockup-node-python` | repo | 48★, 2023-06-10 | none declared | Concrete ImageMagick commands incl. `-compose displace 20x20` + multiply adjust. |
| 21 | `danielgatis/rembg` | repo | 25.1k★ | MIT | Cutouts for scene lanes / erase-prep. |
| 22 | `philgyford/python-halftone` + `datatimp/rosette-halftone` + `schwanksta/Halftones` + `souheyell/bwLabSP` | repos | 103★ / 0★ / 0★ / — | none / AGPL-3.0+ / none / — | Halftone/ink-simulation cluster; use only if we want the screen-print look; mind AGPL. |
| 23 | `colour-science/colour` | repo | 2.7k★ | BSD-3 | Color math if we add soft-proof/TAC lanes. |
| 24 | `psd-tools` | repo | 1.5k★ | MIT | Reminder: smart objects unsupported — stay parametric. |

--------------------------------------------------------------------------------

## 6) SOURCES (numbered; 126 entries + a 6,060-row machine inventory in Appendix A)

**A. Repo-internal evidence (read this session or prior session, referenced):**
1. `research/packify_dyp_re_20261016/packify_public_api_docs_extract.txt` — Packify public API docs text (all §1.1 quotes/L-numbers).
2. `research/packify_dyp_re_20261016/packify_docs_endpoint_scan.txt` — docs-SPA chunk scan (asset `index-xR4wZ2wm.js`; `/api/open/2025-10/*`).
3. `research/packify_dyp_re_20261016/packify_app_endpoint_scan.txt` — app bundle endpoint inventory (`/api/photoshoot/*`, `/api/mockup/*`).
4. `research/packify_dyp_re_20261016/packify_web_endpoint_scan.txt` — web bundle scan (294 URLs / 115 API paths).
5. `reports/competitor_re_packify_dyp_20261016.md` — prior Packify/DYP teardown (REA workflow commands reused in §4).
6. `scripts/compose_mogra_complete.py` — our current compositor (baseline for §3).
7. `research/packify_quality_deep_dive_20261016/gh_sweep.py` — prepared GitHub sweep script (breadth inventory across ComfyUI/product-photo/mockup/dieline terms; long-running background job this session).
8. `research/packify_dyp_re_20261016/runtime_dyp_live_capture.json` — DYP credit-poll envelope (context for the shared recipe).
9. `research/packify_dyp_re_20261016/packify_api_docs_page.png` / `packify_design_chat_view.png` / `dyp_mockup_studio_result.png` — operator-generated UI evidence from the prior session.

**B. Packify / Pacdora public surfaces (live this session unless noted):**
10. https://www.packify.ai/ — homepage (FAQ: "AI Photoshoot costs 5 credits"; Mockup Studio; 3D mockup claims).
11. https://www.packify.ai/aimockup — "system will automatically align and adjust"; "front-facing image with minimal perspective distortion".
12. https://www.packify.ai/tools/lifestyle-mockup-generator — background-replacement caveats ("does not guarantee realistic… fabric folds").
13. https://www.packify.ai/tools/merch-maker — "Traditional mockup tools usually replace a layer inside a fixed image. The artwork can look like it is floating…" (their own statement of our exact problem).
14. https://www.packify.ai/photoshoot — photoshoot product page (bg removal in one step; "keep your product as it is while generating a new AI background"; snapshots via search index).
15. https://www.packify.ai/docs — live docs shell HTML (assets: `Docs-Coqq3bpA.js`, `index-xR4wZ2wm.js`).
16. https://www.packify.ai/mpa/assets/index-xR4wZ2wm.js — **live docs bundle, fetched this session**: photoshoot request table, coordinates table (camelCase), example curls, credits (design 20 / photoshoot 10), webhook/retry sections.
17. https://www.packify.ai/mpa/assets/index-2t_0hD9_.js — **live app shell chunk, fetched this session**: event enums, `extracted_coordinates` → canvas mapping, `mockupConfig` (`eraseScale, lumin_url, depthData, uvData, elementData, default_design_area, mockup_template_id`), endpoint call sites.
18. https://www.packify.ai/api/open/2025-10/packaging-photoshoot — SPA route (404 to non-browser fetch; client-routed).
19. https://www.packify.ai/api/open/2025-10/packaging-design — SPA route (same).
20. https://www.pacdora.com/ — mockup/dieline platform (counts: 1169+ box mockups etc.).
21. https://www.pacdora.com/introduction-to-pacdora-3d-rendering-technology — GGX BRDF, ray tracing, foil/UV/emboss, preview↔offline pipeline history.
22. https://www.pacdora.com/tools/dieline-to-3d-mockup — SVG/DXF dieline auto-folds into interactive 3D; fold direction/animation.
23. https://www.pacdora.com/3d-creator — 5,000+ models, real-time 3D previews, 2K/4K/8K export.
24. https://www.pacdora.com/tools/3d-box-template — materials, renders up to 8K, live 3D.
25. https://www.pacdora.com/enterprise/solutions/packaging — Editor SDK/real-time 3D + pricing engine.
26. https://www.pacdora.com/de/packaging-editor-api — Editor API FAQ (2D/3D previews; PDF/AI export; API keys via sales).
27. https://www.pacdora.com/enterprise/pacdora-plugin — Illustrator plugin with in-app 3D preview.
28. https://www.postman.com/pacdora/pacdora-developers/documentation/wfs1a17/pacdora-api-05-28-2024 — public Pacdora API docs (dieline export endpoints: `/open/v1/user/projects/export/*`).
29. https://www.prnewswire.com/news-releases/pacdora-empowers-packaging-industry-with-advanced-3d-api-and-dieline-generator-302500400.html — Editor API = 3D preview + dieline + quoting params.
30. https://www.linkedin.com/posts/pacdora_pacdoraapi-pacdora-packagingdesigner-activity-7049626997311885312-_L2c — 2023: "3D-Rendering function is not included in our first API" (historical scope).
31. https://www.linkedin.com/posts/raymond-wang87_pacdoras-api-integration-in-action-activity-7199571720184160257-V1td — 2024: 6,000+ mockups, 360° views via API.
32. https://packagingschool.com/lessons/how-to-use-ai-for-packaging-photoshoots — independent walkthrough (bg removal → 40+ backgrounds → ~15 s → 4 outputs; realism commentary).
33. https://www.youtube.com/watch?v=vIbfFt1FTvw — Packify tutorial (mug example; flow: upload mockup or flat design → pick background → generate).

**C. Packify public docs / API odd-ends (routes probed):**
34. https://www.packify.ai/api/open/2025-10/packaging-photoshoot/ (with slash) — 404 probe.
35. https://packify.ai/api/open/2025-10/ — 404 probe (www-only).
36. https://web.archive.org/web/2026/https://www.packify.ai/api/open/2025-10/packaging-photoshoot — no snapshot found (UNKNOWN archive coverage).

**D. Technique canon (displacement, lighting, shadows, print simulation):**
37. https://www.adobe.com/products/photoshop/displacement-map.html — Adobe displacement-map guide.
38. https://creativepro.com/add-realistic-artwork-wrinkled-surface-photoshops-displacement-map/ — McCue: displace + Multiply "shading shows through".
39. https://ncoughlin.com/posts/photoshop-displacement-map-tutorial — displace + clipped multiply.
40. https://www.brentgalloway.me/blog/how-to-use-displacement-maps-to-mockup-your-t-shirt-designs — Blend-If technique.
41. https://www.garmentprinting.co.uk/blog/how-to-use-photoshop-to-create-realistic-printed-t-shirt-mockups/ — 5–10 offsets; Blend-If slider.
42. https://idevie.com/tutorials/how-to-create-a-realistic-creased-text-effect-using-the-displace-filter — full crease realism stack (bevel, shadow, displace).
43. https://raydombroski.com/user-guides-adobe/t-shirt-mockup-panels-photoshop — per-panel displacement maps (scale 30) + "Magic Fabric Texture".
44. https://docs.gimp.org/3.2/en/gimp-filter-displace.html — displace algorithm spec.
45. http://im.snibgo.com/displace.htm — IM displacement math (relative vs absolute maps).
46. https://usage.imagemagick.org/mapping/ — IM mapped effects (LUT-based distortion).
47. https://usage.imagemagick.org/bugs/displace/ — IM displace pitfalls (alpha/masking).
48. https://phlearn.com/tutorial/realistic-shadows-photoshop/ — layered shadow anatomy (contact/mid/multiply/clipped).
49. https://phlearn.com/tutorial/photoshop-2026-the-right-way-to-rotate-and-composite-objects/ — "Rotate → Harmonize → shadow"; "hovering" tell.
50. https://pslover.com/tips-and-tricks/realistic-shadows-made-easy/ — contact/cast/ambient definitions + method.
51. https://www.youtube.com/watch?v=KCeV05TlyVA — "Inserting people in Photoshop: Ambient occlusion".
52. https://www.youtube.com/watch?v=Hx6C3FJUMZM — "Composite Ambient Occlusion in Photoshop".
53. https://www.youtube.com/watch?v=Da4axkDKzxQ — "Master Shadows & Lighting in Compositing".
54. https://www.youtube.com/watch?v=rfje7NRVJAY — realistic displacement mapping tutorial (T-shirt).
55. https://www.reddit.com/r/photoshop/comments/i2nlf7/… — "embedded smart object with a displacement map"; "retouched masks and displacement maps, then scripts on the server".
56. https://www.reddit.com/r/webdev/comments/g9h704/… — mockup sites: server-side image manipulation w/ templates.
57. https://placeit.net/learn/tutorials/how-to-create-mockup — Placeit flow (browser editor, upload, crop, download).
58. https://placeit.net/mockups — 43,000+ graphics library (scale of template economy).
59. https://oryndex.co/tools/placeit — "proprietary technology to warp flat images onto 3D objects… with realistic folds and shadows" (third-party characterization).
60. https://codefinity.com/courses/…/05f086c8-… — "best templates handle perspective correction, lighting adjustment, and shadow rendering".
61. https://runway.com/resources/ai-product-mockups — template mockups vs AI restage; industry framing.
62. https://mockupgenerator.com/create/studio-shot — AI studio-shot generator ("realistic warping, lighting and materials").
63. https://docs.dynamicmockups.com/api-reference/render-api — Render API schema (`decoration_method`, blending modes, adjustment layers…).
64. https://docs.dynamicmockups.com/knowledge-base/photoshop-api-feature-support — smart-object support matrix (nested not supported).
65. https://docs.dynamicmockups.com/getting-started/how-does-the-api-work — smart-object mental model.
66. https://help.dynamicmockups.com/en/articles/13483136-photoshop-integration — PSD prep guidance.
67. https://help.dynamicmockups.com/en/articles/13251427-dynamic-mockups-api-complete-guide — API capability list.
68. https://docs.dynamicmockups.com/api-reference/render-print-files-api — print-file (300 DPI) rendering for smart objects.
69. https://doi.org/10.5281/zenodo.20369545 — Raster Halftone Lab (halftone prepress simulator, 2026).
70. https://pypi.org/project/rosette-halftone/ — CMYK separations, screen angles, TAC, SWOP ICC, gamma; AGPL-3.0+.
71. https://mrutyunjaypatil.dev/projects/nanostudio — NanoStudio (Gemini-image product-imagery app) — reference architecture for AI lane.

**E. Libraries / docs (Python lane):**
72. https://pillow.readthedocs.io/en/stable/reference/Image.html — Pillow 13 Image module.
73. https://pillow.readthedocs.io/en/stable/_sources/reference/Image.rst.txt — confirms `Image.transform` (+ MESH/QUAD/PERSPECTIVE in the API surface).
74. https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.RBFInterpolator.html — TPS kernel, smoothing, neighbors; v1.18.
75. https://docs.opencv.org/4.x/da/d54/group__imgproc__transform.html — `cv2.remap` reference (verified live).
76. https://docs.opencv.org/4.x/df/da0/group__photo__clone.html — `seamlessClone` (Poisson) reference (verified live).
77. https://github.com/scikit-image/scikit-image/blob/v0.25.0/skimage/transform/_thin_plate_splines.py — TPS class source (solver details).
78. https://scikit-image.org/docs/stable/auto_examples/transform/plot_tps_deformation.html — TPS warp example (inverse-transform note).
79. https://libcom.readthedocs.io/en/latest/shadow_generation.html — libcom shadow-generation docs.
80. https://stable-x.github.io/StableNormal/ — StableNormal project page.
81. https://baegwangbin.github.io/DSINE/ — DSINE project page.
82. https://github.com/huggingface/transformers/blob/main/docs/source/en/model_doc/depth_anything_v2.md — HF integration notes for DAv2.

**F. Papers / research (labels):**
83. https://arxiv.org/html/2406.09414v1 — Depth Anything V2 (NeurIPS 2024).
84. https://arxiv.org/html/2406.16864 — StableNormal (SIGGRAPH Asia 2024).
85. https://doi.org/10.1109/cvpr52734.2025.00712 — GPSDiffusion (CVPR 2025).
86. https://arxiv.org/html/2412.11972 — Controllable shadow generation, single-step diffusion (2024).
87. https://www.alphaxiv.org/abs/1711.08447 — VITON (TPS warp of garments; CVPR 2018).
88. https://openreview.net/forum?id=SHyfcZp0by — DSINE (inductive biases; real-time).
89. https://link.springer.com/article/10.1007/s00521-022-07173-w — MCG-VITON (coarse-to-fine TPS deformation).
90. https://www2.eecs.berkeley.edu/Research/Projects/CS/vision/shape/sc_digits.html — shape-context matching (VITON's TPS control-point source; cited in repo #100).

**G. GitHub repositories (metadata verified 2026-10-16 unless noted; [API] = GitHub API, [page] = repo page):**
91. `raphaelreme/tps` — 38★, MIT, pushed 2026-02-12 [API].
92. `raphaelreme/torch-tps` — 41★, MIT, pushed 2026-02-12 [API].
93. `AlanLuSun/TPS-Warp` — 20★, no license declared, pushed 2021-08-25 [API] (needs opencv-contrib for TPS transformer).
94. `xmba15/thin_plate_spline_warping` — 2★, none, pushed 2024-06-05 [API].
95. `olt/thinplatespline` — 48★, README claims MIT, GitHub metadata none, pushed 2022-03-31 [API + snippet] (discrepancy noted).
96. `scikit-image/scikit-image` — 6,613★, BSD-3-Clause (API shows NOASSERTION; project license BSD-3), pushed 2026-10-09 [API].
97. `kornia/kornia` — 11,432★, Apache-2.0, pushed 2026-10-16 [API].
98. `DepthAnything/Depth-Anything-V2` — 8,967★, Apache-2.0 code + Small weights; Base/Large/Giant CC-BY-NC-4.0, pushed 2026-03-24 [API + page].
99. `isl-org/MiDaS` — 5,419★, MIT, **archived**, pushed 2024-08-23 [API].
100. `xthan/VITON` — 582★, no license shown, 2018-era [page].
101. `NerdFNY/MCG-VITON` — 9★ [search], includes NumPy `TPS_STN` [snippet].
102. `Stable-X/StableNormal` — 785★, Apache-2.0, pushed 2025-08-02 [API].
103. `baegwangbin/DSINE` — 930★, custom license ("Other"), pushed 2024-07-10 [API].
104. `lllyasviel/IC-Light` — 8,546★, Apache-2.0, pushed 2025-02-20 [API].
105. `bcmi/Image-Harmonization-Dataset-iHarmony4` — 812★, MIT, pushed 2026-08-20 [API].
106. `bcmi/libcom` — 741★, Apache-2.0, pushed 2026-10-05 [API].
107. `bcmi/GPSDiffusion-Object-Shadow-Generation` — 152★, MIT [page].
108. `bcmi/Object-Shadow-Generation-Dataset-DESOBAv2` — repo page read via search; stars not re-fetched (limit) [REPORTED].
109. `bcmi/Awesome-Object-Shadow-Generation` — curated list (contents quoted) [search snapshot].
110. `danielgatis/rembg` — 25.1k★, MIT [page].
111. `philgyford/python-halftone` — 103★, no license declared [page].
112. `datatimp/rosette-halftone` — 0★, AGPL-3.0-or-later (PyPI text), 6 commits [page + PyPI].
113. `schwanksta/Halftones` — 0★, license not shown, pushed 2026-09-15 [API partial + page].
114. `sefatlmn/halftone` — p5.js halftone/dither/risograph workshop (static site) [search snapshot].
115. `souheyell/bwLabSP` — browser screen-print RIP: OKLab, Kubelka-Munk, AM/FM screening, dot gain [search snapshot].
116. `adambarla/halftone` — SVG halftone generator (pen plotter) [search snapshot].
117. `psd-tools/psd-tools` — 1.5k★, MIT; smart objects unsupported [page].
118. `colour-science/colour` — 2.7k★, BSD-3-Clause [page].
119. `JohnAnon9771/mockup-generator` — 22★, no license declared, pushed 2025-10-05 [API].
120. `kashifulhaque/product-mockup-node-python` — 48★, none, pushed 2023-06-10 [API].
121. `dynamicmockups/mockup-generator-api` — 9★, MIT, pushed 2024-05-07 [API].
122. `cboatri2/mockup` — 0★, none, pushed 2025-05-14 (Photopea automation) [API].
123. `smile101603/Automated_Mockup_Generator` — 0★, MIT, pushed 2026-03-30 [API].
124. `rmenon1008/mockupgen` — 66★, MIT, pushed 2023-07-18 [API].
125. `zenseact/R3D2` — one-step diffusion asset insertion (shadows/lighting) — license not fetched [search snapshot].
126. `iwyoo/TPS_STN-tensorflow` — TPS Spatial Transformer reference (cited by #101) [snippet].

(Entries numbered to 126; several bundle two URLs of the same artifact type — conservative unique-URL count ≥110.

**Appendix A — machine-generated GitHub inventory (completed 2026-10-16):** `SOURCES_GITHUB.csv` + `sweep_summary.json` (same folder) from `gh_sweep.py`: **90 search terms → 6,060 unique repos**, run at 2026-10-16T21:04Z; 159 repos with ≥1k★, 931 with ≥100★. Caveats: (a) four queries returned 0 new due to GitHub unauthenticated search rate limits (`comfyui relight`, `mockup generator`, `box mockup`, `super resolution`) — no retry attempted (circuit-breaker discipline), so those families are under-covered; (b) the inventory is term-based and carries noise (e.g., "packaging template" surfaces Python-packaging tooling such as `cookiecutter`) — it is a *candidate pool* for future scouting, not a vetted list. Rows were metadata-verified (stars/language/pushed_at) but not individually reviewed for this report.)

--------------------------------------------------------------------------------

## 7) HONEST LIMITATIONS

- **No live API interaction with Packify/Pacdora was performed by this agent** (no app driving, no key usage). Behavioral claims about *runtime* photoshoot behavior rest on the live static bundle + docs + the packaged-school walkthrough; §4 is the plan to confirm them.
- **"extracted_coordinates" semantics beyond field names** (who computes it, from what, at what stage) are inferred from client call sites and state flow — the strongest available evidence short of a live capture, but still inference.
- **The relight/harmonize question (does photoshoot re-light the product?) remains UNKNOWN.** Marketing is consistent with a fully generated background around untouched product pixels; no evidence of an explicit relight pass was found.
- **Star counts/licenses** were fetched 2026-10-16 and will drift; several small repos declare **no license** — do not vendor code without a license review (per constitution, GPL/AGPL items stay at arm's length; `rosette-halftone` is AGPL).
- **Values suggested in §3 (strengths, radii, amplitudes) are starting points from the cited tutorials' conventions**, not measured optima for our plates; every one is behind a parameter and must be validated on the MOGRA render with the `--debug` stage images before being trusted.
- Competitor marketing claims (their own pages) are labeled REPORTED where not independently verified; nothing here should be represented to customers as fact about competitors beyond what their public pages state.
