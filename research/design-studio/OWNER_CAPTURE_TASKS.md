# Owner Capture Tasks

Two Amazon pages behind a Seller Central / Amazon Ads sign-in are cited by the
Design Studio's AI-people disclosure register. They are currently labelled
**REPORTED**, because a sign-in-gated page cannot be verified by anything but a
signed-in human.

**This is the only thing standing between the current labels and VERIFIED.**

## Rules for this task

- **Do not reproduce the page in full.** Paste ONE OR TWO SENTENCES you observed
  — the exact keyword string and field name, and the operative wording. Long
  verbatim reproduction of Amazon documentation is not something this project
  stores.
- Record the date you looked. A page read on a date is a page that was true on
  that date.
- If the page does not say what the register claims, say so. A correction is
  more valuable than a confirmation.

## Task 1 — the tagging procedure page

| Field | Value |
|---|---|
| Source id | `ai-tag-page` |
| Page | How to tag media that contains an AI-generated person |
| URL | https://sellercentral.amazon.com/help/hub/reference/external/GFXHCHYZRGJRBZA5 |
| Now labelled | REPORTED |
| Upgrade to | VERIFIED |

**Confirm, in your own words:**

1. The keyword is exactly `contains-synthetic-performer`.
2. The field is exactly `dc:subject` (also called Keywords on macOS Preview and
   Tags on Windows file Properties).
3. Whether **video** is named alongside images.
4. Whether **older uploads** are addressed, and whether there is a deadline.
5. Whether the page names the tool paths (Windows / macOS / exiftool).

**What the register currently claims, so you can correct it:**
- Keyword exact, `dc:subject` field, IPTC-compatible editor, applied before upload.
- Applies to images and video, in listings and A+ content, worldwide.
- Exemptions: real people (even AI-altered), expressive-work characters, no
  people, non-photorealistic people.

## Task 2 — the Ads page

| Field | Value |
|---|---|
| Source id | `ai-ads-page` |
| Page | AI-generated people in ads: New York State disclosure requirement |
| URL | https://advertising.amazon.com/help/GP6Y2AE2BUM5XWFX |
| Now labelled | REPORTED |
| Upgrade to | VERIFIED |

**Confirm, in your own words:**

1. The **three paths** and who acts on each:
   - Amazon made the creative and it stays in Amazon's workflow → Amazon
     displays the disclosure automatically.
   - Externally made (or Amazon-made then downloaded, edited and re-uploaded) →
     the **advertiser** declares **"Contains synthetic performers"** at upload.
   - Third-party-served formats where Amazon cannot control presentation → the
     **advertiser** places the disclosure in the creative.
2. The **effective date** and the **jurisdiction wording** (New York State
   shoppers or viewers).
3. Whether the page states anything about **conspicuousness**.

## How to record it

Open `research/design-studio/SOURCES.csv`, fill in the `pulled_at`,
`observed_quote` and `notes` columns for the rows already present, then change
`upgrade_to` to `VERIFIED`.

After the capture, the register is updated in one place:
`northstar-os-ui/src/studio/engine/specRegistry.js` → `SPEC_SOURCES`. Change
`confidence: 'REPORTED'` to `'VERIFIED'` for those two ids and add the capture
date. The disclosure scope table (`DISCLOSURE_SCOPE` in
`studio/engine/disclosure.js`) then upgrades the surfaces that depend on them:
Premium A+, Brand Story, Store images and videos, shoppable or product video,
and ad creative.

## Why it matters

Seven surfaces currently read REPORTED, and the Ads jurisdiction scope is
date-sensitive. Until a human reads those two pages, the studio cannot claim
them as verified, and it will not.

## Also worth capturing while you are signed in

These would let three more rules move from a restatement to a primary source:

| Source id | Page | URL |
|---|---|---|
| `premium-elig` | Update to Premium A+ Content eligibility requirements (forum) | https://sellercentral.amazon.com/seller-forums/discussions/t/301e6741-8ef5-485f-8829-a14c55647f9c |
| `stores-content` | Content tiles on Stores (re-read; the overlay percentages live here) | https://advertising.amazon.com/help/GBX4ZFVHAKXKA5WM |
| `ads-overview` | Ad specifications overview (carries the 4 Mbps OLV minimum) | https://advertising.amazon.com/help/GAULLQNSRGXQKDFW |
