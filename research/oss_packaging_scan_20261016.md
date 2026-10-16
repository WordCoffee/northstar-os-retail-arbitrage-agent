# OSS scan — packaging/dieline tools like Packify + Canva-class editors (2026-10-16)

Operator questions answered here:
1. Can logging in for a scan be detected / is copying code a risk?
2. Is "their code" (Canva / Helium 10) already scanned somewhere on GitHub?
3. Are there other build programs like Packify.ai on GitHub we can actually use?

Method: GitHub API reads this session (stars / license / last push VERIFIED);
no logins, no browser automation, no leaked material.

## 1. Logins, scans, and copying (the safety answer)

- **Do not scan from a logged-in session.** Canva's and Helium 10's terms
  generally prohibit automated access; their servers log it; the account at
  risk is YOUR real account. The repo's Chrome-Connect guardrails already
  forbid the agent from entering credentials or driving a logged-in session.
- **Patterns, not code.** A compliant scan extracts layout/flow IDEAS (not
  copyrightable). Copying their code, text, images or assets is infringement
  and is never done here; every REA file records patterns + adopt/decline
  decisions only.
- **Minified bundles are not "code you can copy".** Even read from the browser,
  reusing it would be infringement — and pointless: see §2.

## 2. Is "their code" on GitHub?

**No — and any repo claiming to be it should be avoided** (infringement +
malware risk). Canva and Helium 10 are closed-source SaaS. What legitimately
exists is open-source lookalikes and building blocks (verified this session):

| Repo | License / facts | Verdict |
|---|---|---|
| `nihaojob/vue-fabric-editor` | MIT · 7,995★ · active | Closest OSS Canva-class editor (fabric.js + Vue). **Reference** for interaction patterns; not a drop-in (different stack). |
| `salgum1114/react-design-editor` | MIT · 1,710★ · active | React/Konva design editor. Reference. |
| `Davronov-Alimardon/canva-clone` | Apache-2.0 · 536★ | Template-driven SaaS starter. Reference. |
| `fabricjs/fabric.js` · `konvajs/react-konva` | MIT · 31.5k★ / 6.4k★ | Canvas engines (we use our own canvas; engines are an option, not a need). |
| `tldraw/tldraw` | NOASSERTION · 51k★ | **Custom license (watermark in production; paid to remove)** — NOT free for our use. Declined. |
| `excalidraw/excalidraw` | MIT · 134k★ | Whiteboard, not a design editor. Declined as a base. |
| Helium 10-like OSS | — | Nothing comparable exists; earlier scans found only tiny scripts. Declined as a category. |

## 3. Packify-like packaging tools that CAN be used (the useful part)

| Repo | License / facts | How we could use it |
|---|---|---|
| **`florianfesti/boxes`** (Boxes.py) | **GPL-3.0 · 1,282★ · pushed 2026-10-15 (very active)** | The real find: a huge library of parametric box/dieline generators (boxes, trays, shelves…) outputting **SVG/PDF**. Use as an **external local tool** (run it, import the SVG into the Dielines lane). GPL boundary: we consume its OUTPUT; we do not embed its code. |
| `stoneproof-tech/PackagingWorkbench` | LGPL-2.1 · FreeCAD | Parametric **FEFCO 0201/0301/0713** corrugated dielines (real industry standards). External tool (FreeCAD). |
| `artistCDMJ/carton_previz_helper` | GPL-2.0 · Blender addon | 3D carton visualization from Illustrator dielines — pairs with the Blender lane for packaging previews. |
| `DDR68/Rhino_Packaging_Toolkit` | MIT · Rhino 7/8 | Structural packaging toolkit — only if Rhino is ever in the stack (paid app). |
| `BrownBear127/open-dieline` | source-available (NOASSERTION) | Parametric dieline prototyping; **license terms must be read before any use**. |
| `sp1ritCS/vueBoxProgramm` | MPL-2.0 | Small FEFCO 200/201 calculator — pattern reference. |
| `frontsail-ai/aspicio` | MIT · pushed 2026-10-12 | DXF / vector-PDF **viewer** (TypeScript) — could render supplier DXFs in the web UI. |
| `minrogi/PLMPackLib` | no license shown · 2015 | Packaging-standard resizing libs; stale. Declined. |

**Recommendation:** adopt **Boxes.py as an external generator** for the
Dielines lane (new "Box library" picker: choose a structure, generate locally,
import the SVG into the existing dieline editor). Optionally add the Blender
carton addon for 3D previews. Everything else stays reference material.

**Gates honored:** no leaked code consulted; no logins; nothing adopted
embedded — external tools only, with licenses recorded.
