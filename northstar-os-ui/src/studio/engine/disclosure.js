// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — AI-GENERATED PEOPLE DISCLOSURE
//
// Amazon requires a machine-readable disclosure for media containing
// photorealistic AI-generated people, and New York State requires a CONSPICUOUS
// disclosure in advertisements. They are NOT the same obligation.
//
// WHAT THIS MODULE DOES
//   • Classifies an asset into exactly one of six states. There is NO DEFAULT:
//     an unclassified asset cannot export.
//   • Detects CONFLICT: if the studio generated a person, a seller answer of
//     "no people" is rejected rather than believed.
//   • Records a per-asset ATTESTATION (user, timestamp, asset version,
//     statement) and re-requires it after ANY edit.
//   • Writes the real XMP marker and RE-READS the exported bytes to prove the
//     tag survived the export path.
//
// WHAT THIS MODULE CANNOT DO
//   The studio CANNOT detect AI-generated people from pixels. It knows only
//   what it generated itself and what the seller declares. The UI says so
//   plainly and never implies otherwise.
//
// SOURCES (source ids resolve in specRegistry.SPEC_SOURCES)
//   img-guide     Product image guide G1881          VERIFIED
//   ai-tag-page   GFXHCHYZRGJRBZA5 (tagging procedure) VERIFIED (login-gated)
//   ai-announce   Seller Forums announcement 2026-07-27 VERIFIED
//   ai-ads-page   Ads GP6Y2AE2BUM5XWFX               REPORTED (login-gated)
//   ny-statute    NY GBL 396-b coverage              REPORTED
// ═══════════════════════════════════════════════════════════════════════════

export const DISCLOSURE_KEYWORD = 'contains-synthetic-performer'
export const DISCLOSURE_FIELD = 'dc:subject (XMP)'

// ── 1a. The six classifications. No default. ────────────────────────────────
export const PEOPLE_CLASSES = [
  {
    id: 'no-people',
    label: 'No people in this asset',
    tagRequired: false,
    amazonNote: 'Amazon: you do not need the metadata if the media does not feature any people.',
  },
  {
    id: 'real-only',
    label: 'Real people only',
    tagRequired: false,
    amazonNote: 'Amazon: you do not need the metadata if the media only features real people, EVEN IF they have been altered with AI tools.',
  },
  {
    id: 'real-ai-altered',
    label: 'Real people, altered with AI tools',
    tagRequired: false,
    amazonNote: 'Amazon explicitly exempts real people who were altered with AI-powered tools. Retouching, cleanup and enhancement of a real photo do not trigger the tag.',
  },
  {
    id: 'ai-photoreal',
    label: 'Entirely AI-generated photorealistic people',
    tagRequired: true,
    amazonNote: 'AMAZON REQUIRES THE TAG: a person created entirely by AI who looks like a real human. Also counts: a partially visible synthetic figure, and a synthetic bystander in a background (New York analysis: "a synthetic bystander in a lifestyle scene falls within the definition alongside a synthetic hero model").',
  },
  {
    id: 'non-photoreal',
    label: 'Non-photorealistic or illustrated people',
    tagRequired: false,
    amazonNote: 'Amazon: you do not need the metadata if the media does not feature photorealistic people (illustration, cartoon, abstract).',
  },
  {
    id: 'expressive-work',
    label: 'Character from a film, TV, game or other expressive work',
    tagRequired: false,
    amazonNote: 'Amazon: you do not need the metadata for characters from movies, TV, streaming, documentaries, video games or other expressive works. New York carves out the same class.',
  },
]

export const CLASS_BY_ID = Object.fromEntries(PEOPLE_CLASSES.map(c => [c.id, c]))

// ── 1b + 1g. Classification state for a document ────────────────────────────
/**
 * @returns {{
 *   status: 'decided'|'needs-confirmation'|'conflict',
 *   classification: string|null,
 *   tagRequired: boolean,
 *   conflicts: string[],
 *   note: string,
 * }}
 */
export function classifyDisclosure(doc) {
  const meta = doc?.meta || {}
  const answer = meta.peopleClass || null
  const studioGenerated = !!meta.studioGeneratedPerson
  const conflicts = []

  if (!answer) {
    return {
      status: 'needs-confirmation',
      classification: null,
      tagRequired: false,
      conflicts,
      note: 'Not answered. The studio cannot detect AI people from pixels, so export stays blocked until the seller classifies this asset.',
    }
  }
  if (!CLASS_BY_ID[answer]) {
    return {
      status: 'conflict',
      classification: answer,
      tagRequired: false,
      conflicts: [`Unknown classification "${answer}".`],
      note: 'An unrecognised classification cannot be trusted; export is blocked.',
    }
  }

  // 1b. CONFLICT: the studio generated a person, so "no people" is not credible.
  if (studioGenerated && (answer === 'no-people' || answer === 'expressive-work')) {
    conflicts.push(
      `The studio generated a person for this asset, so "${CLASS_BY_ID[answer].label}" cannot be correct.`
    )
  }
  // A tag-required class with the marker disabled is also a conflict.
  const cls = CLASS_BY_ID[answer]
  if (cls.tagRequired && meta.syntheticPerformerTag === false) {
    conflicts.push('This classification requires the XMP marker, but the marker is switched off.')
  }

  if (conflicts.length) {
    return {
      status: 'conflict',
      classification: answer,
      tagRequired: cls.tagRequired,
      conflicts,
      note: 'A seller answer contradicts what the studio knows about this asset. Export is blocked until the answer is corrected.',
    }
  }

  return {
    status: 'decided',
    classification: answer,
    tagRequired: cls.tagRequired,
    conflicts,
    note: cls.tagRequired
      ? `The XMP keyword "${DISCLOSURE_KEYWORD}" will be written to ${DISCLOSURE_FIELD}, then re-read from the exported file to prove it survived.`
      : cls.amazonNote,
  }
}

// ── 1c. Attestation ────────────────────────────────────────────────────────
// The statement a seller affirms, quoted so there is no ambiguity about what
// was agreed to.
export const ATTESTATION_STATEMENTS = {
  'ai-photoreal': 'I created or commissioned the synthetic person in this asset, it is not a real person, and I am disclosing it as Amazon requires.',
  'no-people': 'This asset contains no people.',
  'real-only': 'Every person in this asset is a real person.',
  'real-ai-altered': 'Every person in this asset is real. AI tools were used only to alter or enhance the photograph.',
  'non-photoreal': 'Any people in this asset are clearly non-photorealistic (illustrated, cartoon or abstract).',
  'expressive-work': 'Any people in this asset are characters from an expressive work (film, TV, game), not synthetic performers.',
}

/** A stable fingerprint of everything an attestation is about. */
export function assetVersion(doc, assetBytes) {
  const parts = [
    doc?.formatId || '',
    doc?.w ?? '', doc?.h ?? '',
    doc?.meta?.peopleClass || '',
    doc?.meta?.studioGeneratedPerson ? 'gen' : '',
    doc?.meta?.lastEditAt || '',
    assetBytes ? String(assetBytes) : '',
  ]
  return parts.join('|')
}

/**
 * Is a stored attestation still valid for THIS version of the asset?
 * Any edit changes `lastEditAt` (or the bytes) and invalidates it.
 */
export function attestationValid(attestation, doc, assetBytes) {
  if (!attestation) return false
  if (!attestation.user || !attestation.timestamp || !attestation.statement) return false
  return attestation.assetVersion === assetVersion(doc, assetBytes)
}

export function makeAttestation(doc, { user, assetBytes } = {}) {
  const cls = doc?.meta?.peopleClass
  if (!cls) return null
  return {
    user: user || 'unknown',
    timestamp: new Date().toISOString(),
    assetVersion: assetVersion(doc, assetBytes),
    statement: ATTESTATION_STATEMENTS[cls] || 'I confirm the classification recorded for this asset.',
    classification: cls,
  }
}

// ── 1d. The XMP marker: build, embed, read back ────────────────────────────

const XMP_NS = 'http://ns.adobe.com/xap/1.0/\u0000'
const PNG_SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]

/** XML-escape a value for the XMP packet. */
function xesc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

/** Build a minimal XMP packet carrying dc:subject keywords. */
export function buildXmpPacket(keywords) {
  const list = (Array.isArray(keywords) ? keywords : [keywords]).filter(Boolean)
  const items = list.map(k => `        <rdf:li>${xesc(k)}</rdf:li>`).join('\n')
  return `<?xpacket begin="\uFEFF" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Northstar OS">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/">
   <dc:subject>
    <rdf:Bag>
${items}
    </rdf:Bag>
   </dc:subject>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>`
}

// ── CRC32 (needed for a valid PNG chunk) ───────────────────────────────────
const CRC_TABLE = (() => {
  const t = new Uint32Array(256)
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    t[n] = c >>> 0
  }
  return t
})()

function crc32(bytes) {
  let c = 0xffffffff
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function u32(n) {
  return new Uint8Array([(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255])
}

function concat(parts) {
  const len = parts.reduce((s, p) => s + p.length, 0)
  const out = new Uint8Array(len)
  let off = 0
  for (const p of parts) { out.set(p, off); off += p.length }
  return out
}

const enc = (s) => new TextEncoder().encode(s)
const dec = (b) => new TextDecoder('utf-8', { fatal: false }).decode(b)

/**
 * Embed the XMP packet into PNG bytes as an iTXt chunk, inserted immediately
 * after IHDR so it is never inside the image data.
 */
export function embedXmpInPng(bytes, keywords) {
  const sig = bytes.slice(0, 8)
  for (let i = 0; i < 8; i++) if (sig[i] !== PNG_SIG[i]) throw new Error('not a PNG')
  const xmp = buildXmpPacket(keywords)
  // iTXt: keyword \0 compFlag(1) compMethod(1) langTag \0 translatedKw \0 text
  const data = concat([
    enc('XML:com.adobe.xmp'), new Uint8Array([0]),
    new Uint8Array([0, 0]),
    new Uint8Array([0]), new Uint8Array([0]),
    enc(xmp),
  ])
  const type = enc('iTXt')
  const chunk = concat([u32(data.length), type, data, u32(crc32(concat([type, data])))])
  // Insert after IHDR (signature 8 + length 4 + type 4 + data 13 + crc 4 = 33)
  const ihdrEnd = 8 + 4 + 4 + 13 + 4
  return concat([bytes.slice(0, ihdrEnd), chunk, bytes.slice(ihdrEnd)])
}

/** Read the XMP packet back out of PNG bytes. */
export function readXmpFromPng(bytes) {
  let off = 8
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  while (off + 8 <= bytes.length) {
    const len = view.getUint32(off)
    const type = dec(bytes.slice(off + 4, off + 8))
    const dataStart = off + 8
    if (type === 'iTXt') {
      const data = bytes.slice(dataStart, dataStart + len)
      const nul = data.indexOf(0)
      const kw = dec(data.slice(0, nul))
      if (kw === 'XML:com.adobe.xmp') {
        // skip compFlag, compMethod, langTag\0, translatedKeyword\0
        let p = nul + 1 + 1 + 1
        while (p < data.length && data[p] !== 0) p++
        p++
        while (p < data.length && data[p] !== 0) p++
        p++
        return dec(data.slice(p))
      }
    }
    if (type === 'IEND') break
    off = dataStart + len + 4
  }
  return null
}

/** Embed the XMP packet into JPEG bytes as an APP1 segment after SOI. */
export function embedXmpInJpeg(bytes, keywords) {
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8) throw new Error('not a JPEG')
  const xmp = buildXmpPacket(keywords)
  const payload = concat([enc(XMP_NS), enc(xmp)])
  const segLen = payload.length + 2
  const seg = concat([new Uint8Array([0xff, 0xe1]), new Uint8Array([(segLen >> 8) & 255, segLen & 255]), payload])
  return concat([bytes.slice(0, 2), seg, bytes.slice(2)])
}

/** Read the XMP packet back out of JPEG bytes. */
export function readXmpFromJpeg(bytes) {
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8) return null
  let off = 2
  while (off + 4 <= bytes.length) {
    if (bytes[off] !== 0xff) { off++; continue }
    const marker = bytes[off + 1]
    if (marker === 0xda) break // start of scan
    const len = (bytes[off + 2] << 8) | bytes[off + 3]
    if (marker === 0xe1) {
      const start = off + 4
      const ns = dec(bytes.slice(start, start + XMP_NS.length))
      if (ns === XMP_NS) return dec(bytes.slice(start + XMP_NS.length, off + 2 + len))
    }
    off += 2 + len
  }
  return null
}

/** Embed by mime type. Throws on an unsupported container. */
export function embedDisclosure(bytes, mime, keywords = [DISCLOSURE_KEYWORD]) {
  const m = String(mime || '').toLowerCase()
  if (m === 'image/png') return embedXmpInPng(bytes, keywords)
  if (m === 'image/jpeg' || m === 'image/jpg') return embedXmpInJpeg(bytes, keywords)
  throw new Error(`unsupported container for the XMP marker: ${mime}`)
}

/** Read back by mime type. */
export function readDisclosure(bytes, mime) {
  const m = String(mime || '').toLowerCase()
  if (m === 'image/png') return readXmpFromPng(bytes)
  if (m === 'image/jpeg' || m === 'image/jpg') return readXmpFromJpeg(bytes)
  return null
}

/**
 * 1d. Prove the marker SURVIVED an export. Reads the real bytes back and
 * checks the exact keyword. Returns a verdict the pre-flight can use.
 */
export function verifyDisclosureMarker(bytes, mime, keyword = DISCLOSURE_KEYWORD) {
  if (!bytes || !bytes.length) {
    return { ok: false, reason: 'no-exported-bytes', detail: 'The exported file was not provided, so the marker cannot be proven.' }
  }
  let packet = null
  try {
    packet = readDisclosure(bytes, mime)
  } catch (e) {
    return { ok: false, reason: 'read-failed', detail: `Could not read the exported file: ${e.message}` }
  }
  if (!packet) {
    return { ok: false, reason: 'no-xmp', detail: 'No XMP packet found in the exported file. A metadata-stripping export step would do exactly this.' }
  }
  const found = packet.includes(`<rdf:li>${keyword}</rdf:li>`)
  if (!found) {
    return { ok: false, reason: 'keyword-missing', detail: `The XMP packet survived but does not carry the exact keyword "${keyword}". Amazon documents the string as exact.`, packet }
  }
  return { ok: true, reason: 'marker-present', detail: `Verified: "${keyword}" is present in ${DISCLOSURE_FIELD} of the exported file.`, packet }
}

// ── 1d. The export paths that must each be tested ──────────────────────────
// A pipeline step that resizes, re-encodes or changes format can flatten XMP.
// Every one of these is a path the marker has to survive.
export const EXPORT_PATHS = [
  { id: 'png-native', label: 'PNG, no resize', mime: 'image/png', transform: 'none' },
  { id: 'png-resize', label: 'PNG, resized', mime: 'image/png', transform: 'resize' },
  { id: 'jpeg-native', label: 'JPEG, no resize', mime: 'image/jpeg', transform: 'none' },
  { id: 'jpeg-resize', label: 'JPEG, resized', mime: 'image/jpeg', transform: 'resize' },
  { id: 'jpeg-reencode', label: 'JPEG, re-encoded', mime: 'image/jpeg', transform: 'reencode' },
  { id: 'png-to-jpeg', label: 'PNG → JPEG format change', mime: 'image/jpeg', transform: 'format-change' },
  { id: 'jpeg-to-png', label: 'JPEG → PNG format change', mime: 'image/png', transform: 'format-change' },
]

// ── 1f. Ads: the upload checklist + on-creative disclosure ─────────────────
export const ADS_DISCLOSURE_PATHS = [
  {
    id: 'ads-native',
    condition: 'Amazon Ads generative tools created the creative and it stays in the Amazon ad workflow',
    whoActs: 'Amazon',
    step: 'Amazon identifies qualifying synthetic performers and displays the disclosure automatically.',
  },
  {
    id: 'ads-external',
    condition: 'The creative was generated OUTSIDE Amazon, or generated with Amazon tools then downloaded, edited and re-uploaded',
    whoActs: 'Advertiser',
    step: 'Select "Contains synthetic performers" during asset upload.',
  },
  {
    id: 'ads-third-party',
    condition: 'Third-party-served formats where Amazon cannot control the presentation',
    whoActs: 'Advertiser',
    step: 'Put the disclosure directly into the creative.',
  },
]

export const ON_CREATIVE_WARNING =
  'A conspicuous on-creative disclosure is visible to every shopper and cannot be a metadata tag. ' +
  'New York requires the disclosure to be conspicuous; the XMP keyword is invisible and does not satisfy it. ' +
  'Place the disclosure where a person watching the ad can read it, and expect it to be seen.'

// ── 1e. Scope, labelled honestly ───────────────────────────────────────────
export const DISCLOSURE_SCOPE = [
  { surface: 'Listing images', status: 'VERIFIED', source: 'img-guide', note: 'The Product image guide itself carries the tagging clause.' },
  { surface: 'Listing videos', status: 'VERIFIED', source: 'ai-announce', note: 'The announcement names image OR VIDEO files.' },
  { surface: 'A+ Content (basic)', status: 'VERIFIED', source: 'ai-announce', note: 'The announcement names A+ content explicitly.' },
  { surface: 'Premium A+', status: 'REPORTED', source: 'ai-tag-page', note: 'The moderator scope covers A+ Content; the Premium A+ page itself is login-gated and not recorded.' },
  { surface: 'Brand Story', status: 'REPORTED', source: 'ai-tag-page', note: 'Named by a moderator reply as buyer-facing media; the page is login-gated.' },
  { surface: 'Store images and videos', status: 'REPORTED', source: 'ai-tag-page', note: 'Named by a moderator reply; the Store help pages were not captured.' },
  { surface: 'Shoppable / product video', status: 'REPORTED', source: 'ai-tag-page', note: 'The announcement links a shoppable video guide; that guide is not recorded here.' },
  { surface: 'Advertising video / ad creative', status: 'REPORTED', source: 'ai-ads-page', note: 'Ads page GP6Y2AE2BUM5XWFX is sign-in gated, so the three-path behaviour is REPORTED. Jurisdiction scope is DATE-SENSITIVE.' },
]

// ── 1g. The pre-flight row factory ─────────────────────────────────────────
export function disclosureRow(doc) {
  const c = classifyDisclosure(doc)
  return {
    id: 'ai-generated-people-disclosure',
    label: 'AI-generated people disclosure',
    level: c.status === 'decided' ? 'pass' : (c.status === 'conflict' ? 'block' : 'incomplete'),
    status: c.status === 'decided' ? 'checked' : (c.status === 'conflict' ? 'checked' : 'needs-review'),
    need: 'human',
    classification: c.classification,
    tagRequired: c.tagRequired,
    detail: c.conflicts.length
      ? c.conflicts.join(' ')
      : `${c.note} The studio cannot detect AI-generated people from pixels; this state rests on the seller's answer and on what the studio generated.`,
    source: c.tagRequired ? 'img-guide / ai-announce' : 'img-guide',
    accessed: '2026-10-10',
    dateSensitive: true,
  }
}

// ── Filename pattern (directive item 3) ────────────────────────────────────
// Amazon documents ID.VARIANT.ext for listing image filenames.
export const FILENAME_PATTERN = /^[A-Za-z0-9]{6,14}\.[A-Za-z0-9_-]{1,32}\.(jpg|jpeg|png|tif|tiff|gif)$/i

export function checkFilename(name) {
  const n = String(name || '').trim()
  if (!n) return { ok: false, detail: 'No filename recorded. Amazon documents the pattern ID.VARIANT.ext (for example B01ABCDEFG.main.jpg).' }
  if (!FILENAME_PATTERN.test(n)) {
    return { ok: false, detail: `"${n}" does not match the documented pattern ID.VARIANT.ext — an identifier, a dot, a variant, a dot, and an accepted extension.` }
  }
  return { ok: true, detail: `"${n}" matches ID.VARIANT.ext.` }
}
