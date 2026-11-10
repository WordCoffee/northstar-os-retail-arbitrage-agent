"""Versioned beta documents (Privacy Notice, Terms of Service, Acceptable Use
Policy).

Conservative, accurate language ONLY. These are BETA documents for a
restricted, U.S.-focused, manually approved business beta. They do NOT claim:
legal compliance, guaranteed outcomes, Amazon approval, perfect security,
verified sourcing, sales estimates, fees, Buy Box status, or product
profitability. Unknown remains unknown.
"""
from __future__ import annotations

import hashlib

PRIVACY_NOTICE = "privacy_notice"
TERMS_OF_SERVICE = "terms_of_service"
ACCEPTABLE_USE_POLICY = "acceptable_use_policy"
PRIVATE_BETA_ADDENDUM = "private_beta_addendum"

DOC_TYPES = (PRIVACY_NOTICE, TERMS_OF_SERVICE, ACCEPTABLE_USE_POLICY,
             PRIVATE_BETA_ADDENDUM)

_BETA_NOTE = (
    "BETA DOCUMENT — Northstar OS is a restricted, U.S.-focused, manually "
    "approved business beta. This document is provided for transparency and "
    "is not a statement of legal compliance. It does not guarantee any "
    "outcome, Amazon approval, security property, or financial result, and it "
    "does not promise that sourcing, sales, fees, or Buy Box information is "
    "verified or accurate. Where information is unavailable it is left "
    "unknown; it is never silently assumed."
)

PRIVACY_NOTICE_V1 = f"""{_BETA_NOTE}

# Northstar OS Privacy Notice (Beta v1.0)

Effective: beta launch. Applies to: the restricted U.S. business beta.

## What we collect
We collect only the data needed for beta identity, authentication,
organization access, support, billing metadata, and platform security. The
internal data inventory (docs/northstar-phase1c/16-data-inventory.md) lists
every collected field, its purpose, sensitivity, source, storage location,
access roles, subprocessors, retention, deletion mechanism, and whether it is
optional. Raw IP addresses are not stored; acceptance records note "not_stored".

## How we use it
Collected data is used to authenticate you, provide organizational access,
operate permitted research jobs, attribute audit records, and keep the beta
secure. We do not sell personal data and do not run behavioral advertising.

## How long we keep it
Retention follows the schedule in docs/northstar-phase1c/17-retention-schedule.md.
Backups may retain data longer; we do not promise immediate or complete
deletion where backups or legally necessary financial/audit records remain.
A deletion request may be submitted per the documented process; lawful
hold/regulatory exceptions may apply.

## Your controls
You may request a copy of the data we hold about you, request deletion under
the documented process, and revoke sessions. In this beta there is no public
self-serve account; access is manually approved.

## Contact
Contact the beta operator (the single named accountable role) through the
support channel you were given at onboarding.
"""

TERMS_OF_SERVICE_V1 = f"""{_BETA_NOTE}

# Northstar OS Terms of Service (Beta v1.0)

Effective: beta launch. Applies to: the restricted U.S. business beta.

## Access
Access is granted only by manual operator approval. There is no self-serve
signup. You must be at least 18 years old and using Northstar OS for a
business purpose.

## Use
You may use Northstar OS to operate permitted research jobs using only the
local/fake providers configured in this beta. Live providers are not enabled.

## What we do not promise
Northstar OS does not promise that any sourcing, sales, fee, or Buy Box
information is verified, accurate, or up to date, and does not guarantee any
outcome or profitability. Unknown values are presented as unknown. You are
responsible for verifying any information before relying on it.

## Restrictions
Do not attempt to access another organization's data, to bypass
authorization, to automate purchases or marketplace writes, or to use the
service for unlawful purposes. Payment cards are not collected or processed.

## Changes
Documents are versioned. If we revise this document, you will be asked to
accept the new version before continuing to use the service.
"""

ACCEPTABLE_USE_POLICY_V1 = f"""{_BETA_NOTE}

# Northstar OS Acceptable Use Policy (Beta v1.0)

Effective: beta launch.

## Permitted
Use of the beta for lawful business research with only the configured
local/fake providers, within the scope of your manually approved access.

## Prohibited
- Attempting to access, modify, or delete data outside your organization.
- Bypassing authentication, authorization, preview, or acceptance controls.
- Using the service to commit fraud, to harass, or for unlawful activity.
- Introducing credentials, marketplace/supplier/social secrets, or payment
  data into the beta.
- Automating purchases, listings, or any marketplace/advertising/social write.

## Enforcement
Violations may result in access being disabled and sessions invalidated,
consistent with the incident-response runbook.
"""

PRIVATE_BETA_ADDENDUM_V1 = f"""{_BETA_NOTE}

# Northstar OS Private Beta Addendum (v1.0)

This addendum applies to the restricted private beta and supplements the
Privacy Notice, Terms of Service, and Acceptable Use Policy.

## Invite-only access
This beta is INVITE-ONLY and closed by default. You are granted access only by
a manually approved invite. Self-serve or public signup is not available, and
access may be revoked at any time by the operator.

## Trial / tier limits
Access is provided under an explicit plan tier. Feature limits (for example,
the number of research jobs per month, export and advanced-report access, and
seat limits) are enforced by the system. Your tier is shown in your account.
Cancellation, downgrade, or non-payment revokes gated features — this takes
effect on the next entitlement check, not only at your next login.

## Billing is in TEST MODE
Subscriptions in this beta use a TEST-MODE, redirect-based hosted checkout.
No payment card is collected, stored, or processed, and no real payment is
taken. This test-mode disclosure will be removed only when live payment keys
are explicitly authorized by the operator.

## Unknown data
Sourcing, sales, fee, Buy Box, and profitability information is not verified
and may be unknown. Unknown values are shown as unknown and are never silently
assumed to be zero or correct.
"""

DOCUMENT_VERSIONS = {
    PRIVACY_NOTICE: {"version": "1.0", "title": "Privacy Notice (Beta)", "content": PRIVACY_NOTICE_V1},
    TERMS_OF_SERVICE: {"version": "1.0", "title": "Terms of Service (Beta)", "content": TERMS_OF_SERVICE_V1},
    ACCEPTABLE_USE_POLICY: {"version": "1.0", "title": "Acceptable Use Policy (Beta)", "content": ACCEPTABLE_USE_POLICY_V1},
    PRIVATE_BETA_ADDENDUM: {"version": "1.0", "title": "Private Beta Addendum (Beta)", "content": PRIVATE_BETA_ADDENDUM_V1},
}


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def document_versions() -> dict:
    out = {}
    for doc_type, spec in DOCUMENT_VERSIONS.items():
        out[doc_type] = {
            "doc_type": doc_type, "version": spec["version"],
            "title": spec["title"], "content": spec["content"],
            "content_hash": content_hash(spec["content"]),
        }
    return out