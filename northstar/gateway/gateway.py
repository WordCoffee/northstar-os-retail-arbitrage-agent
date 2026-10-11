"""The gateway facade (Phase 3) — the ONLY tool surface for agents.

Every call runs: policy check → isolated fetch → sanitize → snapshot → audit.
Tools: ``fetch_page`` (title + bounded content), ``markdown_dump`` (full
sanitized markdown), ``extract`` (paragraphs containing a query).

Every decision (allow AND deny) goes to the policy kernel's hash-chained
audit log. Content leaves only inside the untrusted-data envelope.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from northstar.policy.kernel import PolicyKernel

from .driver import DockerLightpandaDriver, FetchResult
from .sanitize import sanitize_markdown, wrap_untrusted

GATEWAY_VERSION = "lightpanda-gateway-1.0.0"
PARSER_VERSION = "lightpanda-1.0.0"


@dataclass(frozen=True)
class GatewayResult:
    ok: bool
    tool: str
    reason: str = ""
    detail: str = ""
    title: str = ""
    envelope: str = ""
    snapshot: Optional[dict] = None
    truncated: bool = False


class LightpandaGateway:
    def __init__(
        self,
        *,
        kernel: PolicyKernel,
        driver: Optional[DockerLightpandaDriver] = None,
        max_chars: int = 20_000,
        fetch_page_chars: int = 4_000,
        clock=time.time,
    ) -> None:
        self.kernel = kernel
        self.driver = driver or DockerLightpandaDriver()
        self.max_chars = max_chars
        self.fetch_page_chars = fetch_page_chars
        self.clock = clock

    # -- internals -----------------------------------------------------------
    def _snapshot_record(self, url: str, cleaned: str) -> dict:
        return {
            "snapshot_id": f"snap-{uuid.uuid4().hex[:12]}",
            "source": "lightpanda-connect",
            "url": url,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "freshness_status": "OBSERVED",
            "data_class": "live_verified",
            "parser_version": PARSER_VERSION,
            "gateway_version": GATEWAY_VERSION,
            "content_hash": hashlib.sha256(cleaned.encode("utf-8")).hexdigest(),
            "limitations": ["sanitized-markdown", "no-js-execution-proof"],
        }

    def _slot(self, registry: dict, snapshot: dict) -> dict:
        """Phase 4 store adapter point; keeps records in memory for now."""
        registry[snapshot["snapshot_id"]] = snapshot
        return snapshot

    def _run(self, task_id: str, tool: str, url: str) -> tuple[Optional[str], Optional[dict], Optional[GatewayResult]]:
        decision = self.kernel.authorize_fetch(task_id=task_id, url=url)
        if not decision.allowed:
            return None, None, GatewayResult(
                False, tool, reason=decision.reason, detail=decision.detail
            )

        fetched: FetchResult = self.driver.fetch(url)
        if not fetched.ok:
            self.kernel.audit.append(
                actor=task_id,
                action=f"gateway.{tool}",
                decision="error",
                reason="fetch_failed",
                detail=f"{url} :: exit={fetched.exit_code} {fetched.stderr_tail}",
            )
            return None, None, GatewayResult(
                False, tool, reason="fetch_failed", detail=fetched.stderr_tail
            )

        size_decision = self.kernel.check_response_size(
            task_id=task_id, size=len(fetched.markdown)
        )
        if not size_decision.allowed:
            return None, None, GatewayResult(
                False, tool, reason=size_decision.reason, detail=size_decision.detail
            )

        sanitized = sanitize_markdown(fetched.markdown, max_chars=self.max_chars)
        snapshot = self._snapshot_record(url, sanitized.cleaned)
        self.kernel.audit.append(
            actor=task_id,
            action=f"gateway.{tool}",
            decision="allow",
            reason="ok",
            detail=(
                f"{url} snapshot={snapshot['snapshot_id']} "
                f"hash={snapshot['content_hash'][:16]} truncated={sanitized.truncated}"
            ),
        )
        return sanitized.cleaned, snapshot, None

    @staticmethod
    def _title(cleaned: str) -> str:
        for line in cleaned.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("# ").strip()
            if stripped:
                return stripped[:120]
        return ""

    # -- the three tools -----------------------------------------------------
    def markdown_dump(self, *, task_id: str, url: str) -> GatewayResult:
        cleaned, snapshot, denial = self._run(task_id, "markdown_dump", url)
        if denial:
            return denial
        assert cleaned is not None and snapshot is not None
        envelope = wrap_untrusted(
            cleaned,
            source_url=url,
            snapshot_id=snapshot["snapshot_id"],
            captured_at=snapshot["observed_at"],
        )
        return GatewayResult(True, "markdown_dump", envelope=envelope, snapshot=snapshot)

    def fetch_page(self, *, task_id: str, url: str) -> GatewayResult:
        cleaned, snapshot, denial = self._run(task_id, "fetch_page", url)
        if denial:
            return denial
        assert cleaned is not None and snapshot is not None
        bounded = cleaned[: self.fetch_page_chars]
        truncated = len(cleaned) > self.fetch_page_chars
        envelope = wrap_untrusted(
            bounded,
            source_url=url,
            snapshot_id=snapshot["snapshot_id"],
            captured_at=snapshot["observed_at"],
        )
        return GatewayResult(
            True,
            "fetch_page",
            title=self._title(cleaned),
            envelope=envelope,
            snapshot=snapshot,
            truncated=truncated,
        )

    def extract(
        self, *, task_id: str, url: str, text: str, limit: int = 10
    ) -> GatewayResult:
        cleaned, snapshot, denial = self._run(task_id, "extract", url)
        if denial:
            return denial
        assert cleaned is not None and snapshot is not None
        needle = text.lower()
        matches = [
            para.strip()
            for para in cleaned.split("\n\n")
            if needle in para.lower()
        ][: max(1, limit)]
        payload = "\n\n".join(matches) if matches else f"(no matches for query: {text})"
        envelope = wrap_untrusted(
            payload,
            source_url=url,
            snapshot_id=snapshot["snapshot_id"],
            captured_at=snapshot["observed_at"],
        )
        return GatewayResult(
            True,
            "extract",
            envelope=envelope,
            snapshot=snapshot,
            detail=f"matches={len(matches)}",
        )
