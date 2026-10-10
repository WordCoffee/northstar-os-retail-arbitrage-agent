# UX Teardown: 10 Best Interaction Ideas to Copy, 10 to Avoid

Track E of the Design Studio research corpus. Pulled at 2026-10-10.
Sourced from documented help centre flows, documented pricing matrices,
documented review themes, and observed on-site patterns.

## Screen-by-screen observations

### Onboarding
- **Canva**: template grid home with a search bar; the editor search bar
  doubles as a Magic Design entry point (type an intent, get a first draft) ?
  the blank page never really appears [observed].
- **Figma**: draft-first. Unlimited drafts on all plans, so a new user creates
  before they configure anything [documented].
- **Holo**: URL input as the hero. The single highest-leverage onboarding in the
  set because it removes the first click entirely ? but it also removes
  visibility into what the model assumed [documented].
- **Adobe Firefly**: "Start creating for free" with free DAILY generations and
  no plan, so exploration is free but bounded per day rather than per month
  [documented].

### Project creation
- **Canva**: pick a template (1.6M+ free, 3.6M+ paid) or a custom dimension.
- **Figma**: file ? team-wide library if on a paid plan.
- **Creatify**: paste a product URL, or start from scratch, or use the Agent /
  Ad Flow (node-based editor) [documented].
- **Pacdora**: pick a mockup first, then upload your design onto it ? the
  structure is chosen BEFORE the artwork, which is the correct order for a
  print deliverable [documented].

### Template selection
- **Canva**: category-filtered grid; the documented weakness is that
  over-reliance on templates makes output look like everyone else's [documented
  in reviews].
- **Pacdora**: a library of real dieline structures, so the template IS the
  manufacturable geometry, not a look [documented].
- **Adobe Express**: "Resize for multiple formats ? at one time, in the same
  file" ? the template is a set of output formats [documented].

### Canvas editing
- **Figma**: auto-layout, components/variants, variables with modes (10/20/
  unlimited), compare-changes diff, and round-tripping where exported screens
  come back as auto-layout frames with editable text, real fills and named
  layers [documented]. The structural gold standard.
- **Photoroom**: batch editing of up to 250 images per run, applying
  backgrounds, shadows, branding and formatting in a single run [documented].
- **Canva**: drag-and-drop with a documented ceiling on fine control ? spacing,
  precise layer placement, fine-grained typography all hit limits [documented in
  reviews].

### AI generation panel
- **Adobe Firefly Image Editor**: ONE workspace with a tool rail (Generative
  Fill, Generative Remove, Generative Expand, Generative Upscale, Remove
  Background) and prompt-driven edits, over both AI-generated and uploaded
  images, so you can "shape composition, style and detail" without switching
  surfaces [documented]. Plus 25+ models selectable in one place, then straight
  into editing.
- **Creatify**: a third-party review notes the opposite ? "designed for
  automation rather than deep customization. The built-in editor feels fairly
  rigid compared with dedicated tools like CapCut or Premiere Pro", and some
  modes are "one-and-done unless you download and hand edit those" [documented
  in G2 review commentary].
- **Canva**: per-feature AI access controls in admin settings, with AI feature
  toggles including "Use team content to generate AI responses" [documented].

### Brand kit
- **Canva**: the most complete (see brand-voice-learning-loop.md section 1.1),
  with the notable UX gap that brand templates live in a general section rather
  than inside their kit [documented].
- **Holo**: Brand DNA inferred from a URL, with no way to inspect or correct.
- **Adobe**: Style references and Composition references as first-class
  conditioning, no training required.

### Resize / export
- **Adobe Express**: Resize for multiple formats at once in the same file, plus
  **Safe Zones** described as "format-aware guides to keep important text,
  visuals and logos visible" [documented]. This is the single most directly
  transferable UI primitive in the whole corpus.
- **Canva Magic Resize** (the renamed Magic Switch) does the same job with less
  format awareness [documented].
- **Canva export limits** are documented as a real weakness: exported projects
  cannot always be edited in professional tools, and premium images cannot be
  exported standalone [documented].
- **Pacdora**: exports both a high-res render AND the underlying dieline file
  from one brief [documented].

### Collaboration
- **Figma**: multi-cursor multiplayer, comment threads pinned to canvas objects,
  seat types that determine which surface you land in (Full/Dev/Collab/View)
  [documented].
- **Canva**: real-time collaboration with documented version-drift problems by
  the first review round; mitigated by Brand Folders, a single master file with
  Brand Controls, and Brand Templates per adaptation [documented in review].

---

## 10 BEST INTERACTION IDEAS TO COPY

1. **Format-aware safe-zone overlays** (Adobe Express). Directly applicable to
   Amazon's documented crop behaviour: Store hero images lose up to 16% left and
   right below 1500px and the logo covers a further 18% of the left; Store image
   tiles with link titles obscure ~19% (rectangle) or ~12% (square) at the
   bottom; Sponsored Brands video forbids text in the bottom-right corner.
   *Copy this first ? it is cheap and it prevents a class of rejection.*
2. **Resize to many formats in one file** (Adobe Express / Canva Magic Resize),
   BUT with a spec registry behind it so each target validates against the real
   Amazon size, colour space, DPI and file-size cap rather than merely scaling.
3. **Master-then-data bulk creation** (Canva Bulk Create: build one master with
   placeholders, then link a spreadsheet, up to 150 data fields). This is
   exactly the "bulk variation sets" requirement in the master directive, and
   it is the correct order.
4. **Structure chosen before artwork** (Pacdora: pick the dieline/mockup, then
   place the design). Enforces product fidelity by construction.
5. **Pre-flight that blocks, not a review that catches** (Canva Brand Controls
   + Design Approval stopped a wrong-font and an outdated-logo asset before
   they moved forward). Translate to: the compliance checker blocks export.
6. **One AI workspace with a tool rail over both generated and uploaded images**
   (Adobe Firefly Image Editor) instead of separate mode-specific tools that
   produce one-and-done output.
7. **Auto-layout + components/variants + variables with modes** (Figma) as the
   data model for "one master renders at every Amazon placement size" and "one
   component, six child-ASIN variants".
8. **Role-determined surfaces over one file** (Figma seat types) ? an operator
   lands on the canvas, a reviewer lands on an approval queue, a developer lands
   on a spec/export view. Northstar's equivalent: author surface vs review vs
   export-manifest.
9. **Zero-click onboarding via a real input** (Holo's URL) ? Northstar's
   equivalent is an ASIN or a keyword cluster as the project seed, which is
   strictly better because the operator can see and correct what was inferred.
10. **Free daily exploration separate from metered production** (Adobe Firefly's
    daily-refreshing free generations vs monthly credits). Northstar's equivalent
    is local ComfyUI generation, which is free and unlimited by construction ?
    this is the strongest structural advantage we have and the UI must make it
    visible.

## 10 WORST INTERACTION IDEAS TO AVOID

1. **Retired or renamed brands** (Canva Magic Studio ? Canva AI 2.0). Do not
   name a surface after a bundle that will be dissolved; name it after the
   action it performs.
2. **Feature bloat with AI additions competing for space** (documented Canva
   complaint: "blated interface: too many features and AI additions competing
   for space and attention"). Keep one primary action per surface.
3. **Credit opacity with no upfront cost** (Creatify's #1 complaint class:
   Credit Limitations 76, Credit Issues 76, Expensive 71, Insufficient Credits
   65; "dialing in the right combination of voice, avatar and script can become
   unexpectedly expensive"; "one-and-done... unless you download and hand
   edit"). Every Run must show a cost preview BEFORE the click.
4. **Credits that expire and do not roll over, with inadequate notice**
   (documented Creatify/Adobe behaviour; Pacdora resets at the start of each
   billing cycle). Northstar's local generation has no such trap ? do not
   introduce one.
5. **Refund-hostile cancellation** (documented Creatify Trustpilot complaints:
   refund refusals, multi-step offer-laden cancellation, continued billing after
   cancellation). Not applicable to us, but a benchmark for how NOT to treat an
   operator.
6. **Inference the user cannot inspect or correct** (Holo's Brand DNA). Every
   inference must be visible, editable and revertible.
7. **Export that cannot be re-edited downstream** (documented Canva limitation).
   Every export must carry its source project and provenance.
8. **Template-first output that looks like everyone else's** (documented Canva
   complaint). Start from the product and the keywords, not from a look.
9. **Seat-granularity pricing that charges for unused capability** (documented
   Figma forum complaint about Dev Mode at $35 with ">75% of the available
   features useless"). Charge for what is used, or be local and free.
10. **Tool churn that breaks workflows mid-year** (Creatify sunset AI Shorts,
    Product Video and Video Translation at the end of May 2026; Adobe reserves
    the right to discontinue any partner model at any time). Northstar's
    defence is the local pipeline plus an adapter layer, so a model swap is a
    config change rather than a rebuild.

## Specific patterns to adopt verbatim
- A **spec registry** as the single source of truth for every export format
  (already required by the master directive), surfaced in the UI as the format
  picker's only source.
- **Empty states with a Run button** (already required by the zero-sample-data
  rule) ? and the research confirms this is the honest pattern, since none of the
  competitors ship fabricated rows.
- **An explore surface separate from a produce surface** (Firefly Boards vs the
  Image Editor), which maps onto Design Studio's project board vs the editor
  workspace.
