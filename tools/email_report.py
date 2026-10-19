r"""Send a report by SMTP — credentials come from the environment, never printed.

The agent cannot send mail: this machine has no mail channel and no SMTP
credentials are configured (and reading a credential to send mail is exactly what
the operating constitution forbids). Run this yourself; your password never
leaves your shell and is never written to disk by this script.

Usage (PowerShell):
  $env:SMTP_HOST = "smtp.gmail.com"
  $env:SMTP_PORT = "587"
  $env:SMTP_USER = "you@gmail.com"
  $env:SMTP_PASS = "<app password>"          # Gmail requires an app password
  python tools/email_report.py --to mediablitz07@gmail.com \
      --file reports/Creative_Pipeline_v2_Improvements_20261019.pdf

Then clear it:
  Remove-Item Env:\SMTP_PASS

Gmail note: an account password will NOT work. Create an App Password
(Google Account -> Security -> 2-Step Verification -> App passwords).
"""

from __future__ import annotations

import argparse
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

DEFAULT_SUBJECT = "Northstar OS — Creative Pipeline v2 (19 Oct 2026)"
DEFAULT_BODY = """\
Attached: the Creative Pipeline v2 improvement report.

It covers, with evidence for each claim:
  - the research wave (47,323 GitHub repos, 9,513 Hugging Face assets,
    829 videos, 57,355 sources indexed locally)
  - surface realism in the mockup compositor (before vs after, with images)
  - the Qwen edit lane and the OCR gate that blocks copy drift
  - BiRefNet cutouts framed to Amazon MAIN rules
  - the ICC prepress chain and the gamut mapper
  - the doypack dieline and the pouch calibration tool
  - one retail-readiness verdict across all of it

Every number in it was measured on this machine.
"""


def send(*, host: str, port: int, user: str, password: str, to: str,
         subject: str, body: str, attachment: Path,
         use_tls: bool = True) -> None:
    if not attachment.is_file():
        raise SystemExit(f"attachment not found: {attachment}")
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(attachment.read_bytes(), maintype="application",
                       subtype="pdf", filename=attachment.name)

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=45) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=45) as s:
            s.ehlo()
            if use_tls:
                s.starttls(context=context)
                s.ehlo()
            s.login(user, password)
            s.send_message(msg)
    # Deliberately no credential material in any output.
    print(f"sent {attachment.name} ({attachment.stat().st_size/1024:.0f} KB) to {to}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Email a report via SMTP")
    ap.add_argument("--to", default="mediablitz07@gmail.com")
    ap.add_argument("--file", required=True)
    ap.add_argument("--subject", default=DEFAULT_SUBJECT)
    ap.add_argument("--body", default=DEFAULT_BODY)
    ap.add_argument("--no-tls", action="store_true")
    args = ap.parse_args()

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    missing = [n for n, v in (("SMTP_USER", user), ("SMTP_PASS", password)) if not v]
    if missing:
        print("Missing environment variable(s): " + ", ".join(missing))
        print("Set SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS, then re-run. "
              "See the docstring for the Gmail app-password note.")
        return 2

    try:
        send(host=host, port=port, user=user, password=password, to=args.to,
             subject=args.subject, body=args.body, attachment=Path(args.file),
             use_tls=not args.no_tls)
    except Exception as exc:  # noqa: BLE001
        print(f"send failed: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
