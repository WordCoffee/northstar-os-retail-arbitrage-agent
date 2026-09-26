"""Subscriber-facing file sets (1C-06 master slice / Phase D).

Versioned, conservative, accurate documents: onboarding/setup guide, FAQ, and
support/contact page. These are informational only — they make no claims of
compliance, guaranteed outcomes, Amazon approval, or verified data.
"""
from __future__ import annotations

ONBOARDING_GUIDE = "onboarding_guide"
FAQ = "faq"
SUPPORT_CONTACT = "support_contact"

FILE_SETS = {
    ONBOARDING_GUIDE: {
        "version": "1.0",
        "title": "Northstar OS — Private Beta Onboarding & Setup Guide",
        "content": (
            "# Onboarding & Setup Guide (Private Beta)\n\n"
            "## 1. Getting access\n"
            "Access is invite-only and manually approved. You will receive an "
            "invite link with an invite code. There is no self-serve signup.\n\n"
            "## 2. First sign-in\n"
            "Sign in, then review and accept the current beta documents "
            "(Privacy Notice, Terms of Service, Acceptable Use Policy, and the "
            "Private Beta Addendum). You must be 18 or older and using the "
            "product for a business purpose. Until you accept, product "
            "features remain locked.\n\n"
            "## 3. Your plan and limits\n"
            "Your plan tier determines feature limits (for example monthly "
            "research-job allowance, exports, advanced reports, and seat "
            "limits). These limits are enforced by the system.\n\n"
            "## 4. Billing is in test mode\n"
            "Subscriptions use a test-mode hosted checkout. No payment card is "
            "collected or processed, and no real payment is taken.\n\n"
            "## 5. Data posture\n"
            "Sourcing, sales, fee, Buy Box, and profitability information is "
            "not verified and may be unknown. Unknown is shown as unknown.\n\n"
            "## 6. Support\n"
            "Contact the beta operator through the support channel you were "
            "given at onboarding."),
    },
    FAQ: {
        "version": "1.0",
        "title": "Northstar OS — Private Beta FAQ",
        "content": (
            "# Frequently Asked Questions (Private Beta)\n\n"
            "**Is this public?** No. Access is invite-only and manually "
            "approved.\n\n"
            "**Is billing live?** No. Billing is in test mode; no card is "
            "collected or processed.\n\n"
            "**Are sourcing/sales/fee/Buy Box values verified?** No. They may "
            "be unknown and are shown as unknown. Do not rely on them without "
            "independent verification.\n\n"
            "**What happens if I exceed my plan limits?** The action is "
            "blocked with a clear message; your tier's limits apply on the "
            "next check.\n\n"
            "**Can my access be revoked?** Yes. The operator may revoke "
            "invites or suspend accounts, which blocks access immediately.\n\n"
            "**How do I delete my data?** Follow the documented deletion "
            "request process; note that backups and legally necessary "
            "financial/audit records may remain.\n\n"
            "**What does this beta guarantee?** Nothing beyond what the "
            "documents state. No outcome, approval, or profitability is "
            "guaranteed."),
    },
    SUPPORT_CONTACT: {
        "version": "1.0",
        "title": "Northstar OS — Support & Contact (Private Beta)",
        "content": (
            "# Support & Contact (Private Beta)\n\n"
            "This private beta is operated by a single operator. Support is "
            "provided through the channel you were given at onboarding.\n\n"
            "- Report incidents or suspected abuse immediately to the "
            "operator; the incident-response runbook is followed.\n"
            "- Deletion requests, data questions, and billing questions are "
            "handled by the operator.\n"
            "- Do not share invite codes or credentials.\n\n"
            "Response expectations: the operator reviews requests on a "
            "best-effort basis. No guaranteed response time is offered in "
            "this beta."),
    },
}


def file_sets() -> dict:
    return FILE_SETS