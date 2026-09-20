# Privacy Policy — Northstar OS (Alpha)

> **DRAFT — not legal advice.** Prepared 2026-09-19. The operator is
> **T2 Holdings LLC** (Texas, USA). Beta access is by invitation.
> Any clause that would bind the operator to a specific regulatory timeline or
> obligation is marked `[LEGAL REVIEW REQUIRED]` and is not drafted as binding
> language here.

## 1. What we collect

- **Account basics** — the email/username and subscription plan used for
  access (plan id resolves to the catalog in `shared/subscription-plans.json`;
  no payment data is collected today because billing is not live).
- **Workspace content you create** — scanner/project session history, profile
  preferences, notes, and Memory Bank entries you save in your workspace.
- **Operational logs** — request timestamps and feature usage needed to run
  and secure the service. Audit entries (append-only) record which track/tool
  ran; they do not contain credentials.
- **Passwords** — stored only as bcrypt hashes (never plaintext, never
  readable).

## 2. What we DO NOT collect

- We do not place Amazon orders or read seller-account credentials.
- We do not run third-party advertising/tracking on this alpha and do not sell
  your data.

## 3. How data is used & stored

- Local-first: the operator's stack keeps data under its own control
  (Cloudflare-hosted artifacts and provider caches where applicable).
- Results you generate may be cached locally (e.g., scanner snapshots) for
  repeat use; those snapshots are estimates, not personal data files.
- `[LEGAL REVIEW REQUIRED]` — exact retention periods for each data category
  and a deletion schedule are not defined here.

## 4. Sharing & third parties

- Provider adapters are used only with named, operator-approved gates. Data
  minimization applies: the minimum fields needed for a given lookup are sent;
  credentials never appear in logs or exports (see no-leak requirement D12).
- `[LEGAL REVIEW REQUIRED]` — any cross-border transfer or sub-processor
  schedule requires review before we name sub-processors here.

## 5. Your rights

- You may request a copy of, or deletion of, your workspace content/intelligence
  by contacting the operator (the deletion path will be honored within a
  reasonable period; `[LEGAL REVIEW REQUIRED]` for a specific SLA).
- Bear in mind that scanner outputs are estimates; deleting your account does
  not retroactively validate them.

## 6. Security

- bcrypt password hashing; JWT access/refresh tokens; plan entitlements are
  read-time checks; demo/anonymous access is read-only foundation.
- `[LEGAL REVIEW REQUIRED]` — **Data-breach notification timeline** is not
  drafted here and must be set by counsel.

## 7. Children

The Service is intended for commercial operators (18+). `[LEGAL REVIEW REQUIRED]`
any minor-related terms if marketing ever targets individuals.

## 8. Contact & changes

- Privacy/account requests → `[OPERATOR CONTACT EMAIL — to be filled before launch]`.
- We will update this policy as the product and regulations evolve;
  `[LEGAL REVIEW REQUIRED]` for a committed advance-notice period on changes.

---

*Sized to the current alpha feature set. Revisit at every paid-launch boundary.*