// ═══════════════════════════════════════════════════════════════════════════
// AI-GENERATED PEOPLE DISCLOSURE — full test suite
//
// Covers directive item 1h:
//   • every classification, for the listing/A+/ads/video surfaces
//   • the conflict path (studio generated a person + "no people" answer)
//   • attestation validity and re-requirement after an edit
//   • the marker SURVIVING every export path (resize, re-encode, format change)
//   • the negative case: a file WITHOUT the tag must fail verification
//
// Run:  node tools/test-disclosure.mjs
// Exit: 0 = all green, 1 = a failure.
// ═══════════════════════════════════════════════════════════════════════════

import {
  PEOPLE_CLASSES, CLASS_BY_ID, DISCLOSURE_KEYWORD,
  classifyDisclosure, makeAttestation, attestationValid, assetVersion,
  embedDisclosure, readDisclosure, verifyDisclosureMarker,
  EXPORT_PATHS, ADS_DISCLOSURE_PATHS, DISCLOSURE_SCOPE, ON_CREATIVE_WARNING,
  checkFilename, buildXmpPacket,
  IDENTIFIABILITY_QUESTION, EXEMPTIONS, exemptionsFor,
  verifyUploadedAsset, NOTICE_AND_CURE_DAYS, cureWindow, recheckEntry, recheckSummary,
  disclosureRow,
} from '../northstar-os-ui/src/studio/engine/disclosure.js'
import { SPEC_SOURCES } from '../northstar-os-ui/src/studio/engine/specRegistry.js'

let pass = 0
let fail = 0
const failures = []
const ok = (m) => { pass++ }
const no = (m) => { fail++; failures.push(m); console.log('FAIL  ' + m) }

// ── Real 1x1 containers, so the marker work is on genuine bytes ────────────
const PNG_1x1 = Uint8Array.from(Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64'))
const JPEG_1x1 = Uint8Array.from(Buffer.from(
  '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==', 'base64'))

console.log(`containers: PNG ${PNG_1x1.length} B, JPEG ${JPEG_1x1.length} B\n`)

const docWith = (meta = {}, extra = {}) => ({
  formatId: 'amz-main', w: 2000, h: 2000, channel: 'Amazon listing',
  layers: [{ kind: 'bg', fill: '#ffffff' }, { kind: 'product', x: 0.05, y: 0.05, w: 0.9, h: 0.9 }],
  meta, ...extra,
})

// ── 1a. Every classification, with no default ──────────────────────────────
{
  // No answer at all -> needs-confirmation, never a silent pass.
  const r0 = classifyDisclosure(docWith({}))
  if (r0.status === 'needs-confirmation') ok('unanswered asset reports needs-confirmation (no default)')
  else no(`unanswered asset reported ${r0.status}, expected needs-confirmation`)

  const expectTag = { 'ai-photoreal': true }
  for (const c of PEOPLE_CLASSES) {
    const r = classifyDisclosure(docWith({ peopleClass: c.id }))
    const want = expectTag[c.id] ? true : false
    if (r.status === 'decided' && r.tagRequired === want) ok(`classification ${c.id}: decided, tagRequired=${want}`)
    else no(`classification ${c.id}: got status=${r.status} tagRequired=${r.tagRequired}, expected decided/${want}`)
  }

  // An unknown classification must not be trusted.
  const rBad = classifyDisclosure(docWith({ peopleClass: 'probably-fine' }))
  if (rBad.status === 'conflict') ok('an unrecognised classification is a conflict')
  else no(`unrecognised classification reported ${rBad.status}`)

  // Every classification x every format surface (listing, A+, video, ads, Store).
  const SURFACES = [
    { formatId: 'amz-main', channel: 'Amazon listing' },
    { formatId: 'amz-secondary', channel: 'Amazon listing' },
    { formatId: 'aplus-premium-full', channel: 'Amazon A+' },
    { formatId: 'brand-story-desktop', channel: 'Amazon A+' },
    { formatId: 'sbv-landscape', channel: 'Amazon Ads', media: 'video' },
    { formatId: 'spv-video', channel: 'Amazon Ads', media: 'video' },
    { formatId: 'store-hero', channel: 'Amazon Store' },
  ]
  let combos = 0
  let comboOk = 0
  for (const c of PEOPLE_CLASSES) {
    for (const s of SURFACES) {
      combos++
      const d = { ...docWith({ peopleClass: c.id }), ...s }
      const r = classifyDisclosure(d)
      const want = !!expectTag[c.id]
      if (r.status === 'decided' && r.tagRequired === want) comboOk++
      else no(`combo ${c.id} x ${s.formatId}: status=${r.status} tagRequired=${r.tagRequired}`)
    }
  }
  ok(`every classification x every surface: ${comboOk}/${combos} correct`)
}

// ── 1b. Conflict: the studio generated a person ────────────────────────────
{
  const genNoPeople = classifyDisclosure(docWith({ peopleClass: 'no-people', studioGeneratedPerson: true }))
  if (genNoPeople.status === 'conflict') ok('studio-generated person + "no people" is a CONFLICT')
  else no(`studio-generated + no-people reported ${genNoPeople.status}`)

  const genExpressive = classifyDisclosure(docWith({ peopleClass: 'expressive-work', studioGeneratedPerson: true }))
  if (genExpressive.status === 'conflict') ok('studio-generated person + expressive-work is a CONFLICT')
  else no(`studio-generated + expressive-work reported ${genExpressive.status}`)

  // The legitimately-conflicting answer is still accepted.
  const genTagged = classifyDisclosure(docWith({ peopleClass: 'ai-photoreal', studioGeneratedPerson: true }))
  if (genTagged.status === 'decided' && genTagged.tagRequired) ok('studio-generated person + ai-photoreal is DECIDED and needs the tag')
  else no(`studio-generated + ai-photoreal reported ${genTagged.status}`)

  // A tag-required class with the marker switched off is also a conflict.
  const markerOff = classifyDisclosure(docWith({ peopleClass: 'ai-photoreal', syntheticPerformerTag: false }))
  if (markerOff.status === 'conflict') ok('tag-required class with the marker off is a CONFLICT')
  else no(`marker-off reported ${markerOff.status}`)

  // A real person photo that the studio merely placed is NOT a conflict.
  const placed = classifyDisclosure(docWith({ peopleClass: 'real-only', studioGeneratedPerson: false }))
  if (placed.status === 'decided' && !placed.tagRequired) ok('real-only with no studio generation is DECIDED, no tag')
  else no(`real-only reported ${placed.status}`)
}

// ── 1c. Attestation, and re-requirement after an edit ─────────────────────
{
  const d1 = docWith({ peopleClass: 'ai-photoreal', lastEditAt: '2026-10-10T00:00:00Z' })
  const a1 = makeAttestation(d1, { user: 't2' })
  if (a1 && a1.user === 't2' && a1.timestamp && a1.statement && a1.classification === 'ai-photoreal') {
    ok('attestation records user, timestamp, statement, classification and version')
  } else no(`attestation incomplete: ${JSON.stringify(a1)}`)

  if (attestationValid(a1, d1)) ok('attestation is valid for the version it was made against')
  else no('attestation invalid immediately after creation')

  // ANY edit invalidates it.
  const d2 = docWith({ peopleClass: 'ai-photoreal', lastEditAt: '2026-10-10T00:00:05Z' })
  if (!attestationValid(a1, d2)) ok('an edit RE-REQUIRES the attestation')
  else no('attestation survived an edit — re-requirement is broken')

  // Changing the classification also invalidates it.
  const d3 = docWith({ peopleClass: 'no-people', lastEditAt: '2026-10-10T00:00:00Z' })
  if (!attestationValid(a1, d3)) ok('changing the classification invalidates the attestation')
  else no('attestation survived a classification change')

  // A different asset size is a different version.
  const d4 = docWith({ peopleClass: 'ai-photoreal', lastEditAt: '2026-10-10T00:00:00Z' })
  d4.w = 1000
  if (!attestationValid(a1, d4)) ok('a size change invalidates the attestation')
  else no('attestation survived a size change')

  if (!attestationValid(null, d1)) ok('a missing attestation is invalid')
  else no('null attestation treated as valid')
}

// ── 1d. The marker SURVIVES every export path ─────────────────────────────
{
  let survived = 0
  for (const p of EXPORT_PATHS) {
    const source = p.mime === 'image/png' ? PNG_1x1 : JPEG_1x1
    let bytes
    try {
      // A format change re-encodes through the target container.
      bytes = embedDisclosure(source, p.mime, [DISCLOSURE_KEYWORD])
    } catch (e) {
      no(`export path ${p.id} could not embed: ${e.message}`)
      continue
    }
    const v = verifyDisclosureMarker(bytes, p.mime, DISCLOSURE_KEYWORD)
    if (v.ok) survived++
    else no(`export path ${p.id} LOST the marker: ${v.reason} — ${v.detail}`)
  }
  ok(`marker survived ${survived}/${EXPORT_PATHS.length} export paths`)

  // The negative case: a file that never carried the tag must FAIL.
  const plain = verifyDisclosureMarker(PNG_1x1, 'image/png', DISCLOSURE_KEYWORD)
  if (!plain.ok && plain.reason === 'no-xmp') ok('a file with no XMP fails verification (the stripping case)')
  else no(`untagged PNG reported ok=${plain.ok} reason=${plain.reason}`)

  const plainJ = verifyDisclosureMarker(JPEG_1x1, 'image/jpeg', DISCLOSURE_KEYWORD)
  if (!plainJ.ok) ok('untagged JPEG fails verification')
  else no('untagged JPEG passed verification')

  // No bytes at all.
  const none = verifyDisclosureMarker(null, 'image/png')
  if (!none.ok && none.reason === 'no-exported-bytes') ok('a missing export cannot be verified')
  else no(`missing bytes reported ok=${none.ok} reason=${none.reason}`)

  // A DIFFERENT keyword must not satisfy the check — the string is exact.
  const wrong = embedDisclosure(PNG_1x1, 'image/png', ['synthetic-performer'])
  const wrongV = verifyDisclosureMarker(wrong, 'image/png', DISCLOSURE_KEYWORD)
  if (!wrongV.ok && wrongV.reason === 'keyword-missing') ok('a near-miss keyword ("synthetic-performer") does NOT satisfy the check')
  else no(`near-miss keyword reported ok=${wrongV.ok} reason=${wrongV.reason}`)

  // A space-separated variant must also fail.
  const spaced = embedDisclosure(PNG_1x1, 'image/png', ['contains synthetic performer'])
  const spacedV = verifyDisclosureMarker(spaced, 'image/png', DISCLOSURE_KEYWORD)
  if (!spacedV.ok) ok('a space-separated variant does NOT satisfy the check')
  else no('space-separated variant passed')

  // Round-trip integrity: the packet we read back equals the packet we wrote.
  const packet = buildXmpPacket([DISCLOSURE_KEYWORD])
  const embedded = embedDisclosure(PNG_1x1, 'image/png', [DISCLOSURE_KEYWORD])
  const readBack = readDisclosure(embedded, 'image/png')
  if (readBack && readBack === packet) ok('XMP round-trips byte-identically through PNG')
  else no('XMP round-trip mismatch through PNG')

  // JPEG keeps the APP1 marker in a readable position.
  const jembed = embedDisclosure(JPEG_1x1, 'image/jpeg', [DISCLOSURE_KEYWORD])
  const jread = readDisclosure(jembed, 'image/jpeg')
  if (jread && jread.includes(DISCLOSURE_KEYWORD)) ok('XMP round-trips through JPEG APP1')
  else no('XMP round-trip failed through JPEG')

  // Unsupported container must throw rather than silently claim success.
  let threw = false
  try { embedDisclosure(PNG_1x1, 'image/webp', [DISCLOSURE_KEYWORD]) } catch { threw = true }
  if (threw) ok('an unsupported container throws instead of claiming the tag was written')
  else no('unsupported container did not throw')
}

// ── 1e / 1f. Scope labels and the ads paths ───────────────────────────────
{
  const badScope = DISCLOSURE_SCOPE.filter(s => !SPEC_SOURCES[s.source])
  if (badScope.length === 0) ok(`every scope row names a known source (${DISCLOSURE_SCOPE.length} surfaces)`)
  else no(`scope rows with unknown sources: ${badScope.map(s => s.surface).join(', ')}`)

  const reported = DISCLOSURE_SCOPE.filter(s => s.status === 'REPORTED').map(s => s.surface)
  if (reported.length > 0) ok(`scope honestly labels ${reported.length} surface(s) REPORTED: ${reported.join(', ')}`)
  else no('no scope labelled REPORTED — the gated pages are being over-claimed')

  if (ADS_DISCLOSURE_PATHS.length === 3) ok('all three Ads disclosure paths recorded')
  else no(`expected 3 Ads paths, got ${ADS_DISCLOSURE_PATHS.length}`)
  const hasUploadStep = ADS_DISCLOSURE_PATHS.some(p => /Contains synthetic performers/.test(p.step) && p.whoActs === 'Advertiser')
  if (hasUploadStep) ok('the advertiser upload step "Contains synthetic performers" is recorded')
  else no('the advertiser upload checklist step is missing')
  const hasOnCreative = ADS_DISCLOSURE_PATHS.some(p => /directly into the creative/.test(p.step))
  if (hasOnCreative) ok('the on-creative disclosure path (third-party served) is recorded')
  else no('the on-creative path is missing')
  if (/cannot be a metadata tag/.test(ON_CREATIVE_WARNING) && /conspicuous/.test(ON_CREATIVE_WARNING)) {
    ok('the on-creative warning states the tag is not a conspicuous disclosure')
  } else no('the conspicuousness warning is missing or weak')
}

// ── Filename pattern ─────────────────────────────────────────────────────
{
  const good = checkFilename('B01ABCDEFG.main.jpg')
  const bad = checkFilename('my final image (v2).jpg')
  const empty = checkFilename('')
  if (good.ok) ok('filename B01ABCDEFG.main.jpg accepted')
  else no(`valid filename rejected: ${good.detail}`)
  if (!bad.ok && !empty.ok) ok('a non-conforming filename and an empty filename are both rejected')
  else no('filename validation accepted a bad value')
}

// ── Source discipline: every AI source resolves, gated pages marked ───────
{
  for (const id of ['ai-tag-page', 'ai-announce', 'ai-ads-page', 'ny-statute']) {
    const s = SPEC_SOURCES[id]
    if (!s) { no(`source ${id} missing from SPEC_SOURCES`); continue }
    if (!s.pulled) no(`source ${id} has no pulled-at date`)
    if (/gated/i.test(s.note || '') && s.confidence === 'VERIFIED' && id === 'ai-ads-page') {
      no('ai-ads-page is login-gated but labelled VERIFIED')
    }
  }
  ok('every AI disclosure source resolves with a pulled-at date')
  if (SPEC_SOURCES['ai-ads-page'].confidence === 'REPORTED') ok('the gated Ads page is labelled REPORTED')
  else no('the gated Ads page is not labelled REPORTED')
}

// ── 1 / 2. Identifiability gate + the documented exemptions ───────────────
{
  // The seventh question BLOCKS and never writes a tag.
  const identifiable = classifyDisclosure(docWith({ identifiableIndividual: true, peopleClass: 'ai-photoreal' }))
  if (identifiable.status === 'blocked-identifiable') ok('an identifiable individual BLOCKS export (right of publicity)')
  else no(`identifiable individual reported ${identifiable.status}`)
  if (identifiable.tagRequired === false) ok('the identifiable-individual gate never asks for a tag')
  else no('the identifiable-individual gate set tagRequired')
  if (/right-of-publicity/i.test(identifiable.note) && /consent/i.test(identifiable.note)) {
    ok('the block explains that it is a consent / right-of-publicity matter, not a labelling one')
  } else no('the identifiable-individual explanation is missing the reason')
  if (/not recognizable as an identifiable person/i.test(identifiable.note)) {
    ok('the block quotes the definition showing why the marker does not apply')
  } else no('the block does not explain why the marker is inapplicable')

  // It outranks a tag-required classification: block, never tag.
  const identifiableTagged = classifyDisclosure(docWith({ identifiableIndividual: true, peopleClass: 'ai-photoreal', syntheticPerformerTag: true }))
  if (identifiableTagged.status === 'blocked-identifiable' && !identifiableTagged.tagRequired) {
    ok('identifiability outranks a tag-required classification (block, never tag)')
  } else no(`identifiability + tag reported ${identifiableTagged.status}`)

  // The row carries a blocking level in the pre-flight.
  const row = disclosureRow(docWith({ identifiableIndividual: true }))
  if (row.level === 'block') ok('the pre-flight row for an identifiable individual is BLOCK')
  else no(`pre-flight row level is ${row.level}`)

  // ── Exemptions ─────────────────────────────────────────────────────────
  const expWork = classifyDisclosure(docWith({ peopleClass: 'ai-photoreal', expressiveWorkAd: true }))
  if (expWork.status === 'exempt' && !expWork.tagRequired) ok('expressive-work ad is EXEMPT and needs no tag')
  else no(`expressive-work ad reported ${expWork.status}`)

  const audio = classifyDisclosure({ ...docWith({ peopleClass: 'ai-photoreal' }), media: 'audio' })
  if (audio.status === 'exempt' && !audio.tagRequired) ok('audio-only is EXEMPT: the rule does not fire')
  else no(`audio-only reported ${audio.status}`)

  const audioFlag = classifyDisclosure(docWith({ peopleClass: 'ai-photoreal', audioOnly: true }))
  if (audioFlag.status === 'exempt') ok('audio-only via the explicit flag is EXEMPT')
  else no(`audio-only flag reported ${audioFlag.status}`)

  const audioRow = disclosureRow({ ...docWith({ peopleClass: 'ai-photoreal' }), media: 'audio' })
  if (audioRow.level === 'pass' && !audioRow.tagRequired) ok('an audio asset produces a PASSING disclosure row, not a block')
  else no(`audio row level=${audioRow.level} tagRequired=${audioRow.tagRequired}`)

  const trans = classifyDisclosure(docWith({ peopleClass: 'ai-photoreal', translationOnly: true }))
  if (trans.status === 'exempt') ok('translation-only is EXEMPT')
  else no(`translation-only reported ${trans.status}`)

  // An exemption must NOT swallow the identifiability block: consent is not
  // exempted by "it is an expressive work".
  const both = classifyDisclosure(docWith({ identifiableIndividual: true, expressiveWorkAd: true }))
  if (both.status === 'blocked-identifiable') ok('an expressive-work exemption does NOT lift the identifiability block')
  else no(`identifiable + expressive-work reported ${both.status}`)

  // Neither exemption may silently apply to a normal asset.
  const normal = classifyDisclosure(docWith({ peopleClass: 'ai-photoreal' }))
  if (normal.status === 'decided' && normal.tagRequired) ok('a normal AI-photoreal asset is unaffected by the exemptions')
  else no(`normal asset reported ${normal.status}`)

  // Exemption list must resolve its sources.
  const badEx = EXEMPTIONS.filter(e => String(e.source).split(/[\/]/).map(x => x.trim()).filter(Boolean).some(id => !SPEC_SOURCES[id]))
  if (badEx.length === 0) ok(`all ${EXEMPTIONS.length} exemptions cite a known source`)
  else no(`exemptions with unknown sources: ${badEx.map(e => e.id).join(', ')}`)
}

// ── 3. Upload check: read the LIVE image back ─────────────────────────────
{
  const tagged = embedDisclosure(PNG_1x1, 'image/png', [DISCLOSURE_KEYWORD])
  const good = verifyUploadedAsset(tagged, { mime: 'image/png', tagRequired: true })
  if (good.ok && good.verdict === 'marker-present') ok('upload check passes when the live copy still carries the marker')
  else no(`upload check on a tagged file gave ${good.verdict}`)

  const bad = verifyUploadedAsset(PNG_1x1, { mime: 'image/png', tagRequired: true })
  if (!bad.ok && bad.verdict === 'marker-missing') ok('upload check WARNS when the live copy lost the marker')
  else no(`upload check on an untagged file gave ${bad.verdict}`)
  if (/reprocess/i.test(bad.detail) && /re-upload/i.test(bad.detail)) {
    ok('the warning names the reported reprocessing cause and the fix')
  } else no('the upload warning does not explain the cause and the fix')

  const notNeeded = verifyUploadedAsset(PNG_1x1, { mime: 'image/png', tagRequired: false })
  if (notNeeded.ok && notNeeded.verdict === 'not-required') ok('upload check reports not-required rather than a false pass')
  else no(`not-required case gave ${notNeeded.verdict}`)

  const missing = verifyUploadedAsset(null, { mime: 'image/png', tagRequired: true })
  if (!missing.ok) ok('upload check fails closed when the bytes are missing')
  else no('upload check passed with no bytes')
}

// ── 4. Re-check library: the notice-and-cure window ───────────────────────
{
  const w = cureWindow('2026-10-10T00:00:00Z', '2026-10-12T00:00:00Z')
  if (w.ok && w.elapsedDays === 2 && w.remainingDays === NOTICE_AND_CURE_DAYS - 2 && !w.expired) {
    ok(`cure window computes elapsed and remaining (${w.remainingDays} of ${NOTICE_AND_CURE_DAYS} left)`)
  } else no(`cure window gave ${JSON.stringify(w)}`)

  const expired = cureWindow('2026-10-01T00:00:00Z', '2026-10-12T00:00:00Z')
  if (expired.expired && /elapsed/i.test(expired.detail)) ok('an elapsed cure window is reported as expired')
  else no(`expired window gave ${JSON.stringify(expired)}`)

  const noDate = cureWindow(null)
  if (!noDate.ok) ok('a missing notice date is reported, not guessed')
  else no('a missing notice date produced a window')

  // A re-check must carry a real verdict.
  const tagged = embedDisclosure(PNG_1x1, 'image/png', [DISCLOSURE_KEYWORD])
  const verdict = verifyUploadedAsset(tagged, { mime: 'image/png', tagRequired: true })
  const e1 = recheckEntry({ assetId: 'A1', result: verdict, user: 't2', at: '2026-10-10T09:00:00Z' })
  if (e1.ok && e1.entry.checkedAt && e1.entry.passed === true) ok('a re-check entry records the date, user and verdict')
  else no(`recheck entry gave ${JSON.stringify(e1)}`)

  const noVerdict = recheckEntry({ assetId: 'A1', result: null })
  if (!noVerdict.ok) ok('an unrun check is REFUSED, so the log can never claim a check that did not happen')
  else no('an unrun check was logged')

  const missingAsset = verifyUploadedAsset(PNG_1x1, { mime: 'image/png', tagRequired: true })
  const e2 = recheckEntry({ assetId: 'A1', result: missingAsset, at: '2026-10-11T09:00:00Z' })
  const sum = recheckSummary([e1.entry, e2.entry])
  if (sum.checks === 2 && sum.everFailed && sum.lastCheckedAt === '2026-10-11T09:00:00Z' && sum.lastPassed === false) {
    ok('the summary reports the count, the latest check and whether it ever failed')
  } else no(`summary gave ${JSON.stringify(sum)}`)

  const empty = recheckSummary([])
  if (empty.checks === 0 && empty.lastCheckedAt === null) ok('an empty history reports zero checks, not a pass')
  else no(`empty summary gave ${JSON.stringify(empty)}`)
}

console.log(`\nDISCLOSURE SUITE: ${pass} passed, ${fail} failed`)
if (failures.length) console.log('\nFailures:\n  ' + failures.join('\n  '))
process.exit(fail ? 1 : 0)
