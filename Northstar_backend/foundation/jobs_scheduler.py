"""Persisted scheduler (1C-04 / B15).

Enqueue-only. A scheduler NEVER executes jobs and NEVER calls providers.
It claims due occurrences atomically (INSERT ... ON CONFLICT DO NOTHING on
PostgreSQL; UNIQUE-constraint try/except on SQLite), enqueues one job per
occurrence, advances the next run, and audits every decision.

Rules enforced:
- Organization-scoped schedules; suspended orgs and revoked owners are skipped.
- Provider-backed schedules default disabled.
- Occurrence idempotency prevents duplicate enqueues (two schedulers, one job).
- Misfire policy prevents unbounded catch-up.
- Concurrency policy limits outstanding occurrences per schedule.
- GET requests never tick the scheduler.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from croniter import croniter

from .audit import AuditService
from .jobs_durable import DurableJobService
from .models import utcnow, ScheduleOccurrence
from .repositories import Repositories

DEFAULT_MISFIRE_WINDOW_SECONDS = 600


def _now_iso() -> str:
    return utcnow().isoformat()


class SchedulerError(RuntimeError):
    pass


class JobScheduler:
    def __init__(self, service: DurableJobService, repos: Repositories, *,
                 scheduler_id: str, audit: Optional[AuditService] = None,
                 misfire_window_seconds: int = DEFAULT_MISFIRE_WINDOW_SECONDS) -> None:
        self.service = service
        self.repos = repos
        self.audit = audit or AuditService(repos)
        self.scheduler_id = scheduler_id
        self.misfire_window_seconds = misfire_window_seconds

    # ------------------------------------------------------------------
    # API surface (B15)
    # ------------------------------------------------------------------

    def create_schedule(self, *, organization_id: str, owner_user_id: str,
                        job_template: dict, timezone: str = "UTC",
                        cron_expression: Optional[str] = None,
                        interval_seconds: Optional[int] = None,
                        enabled: bool = False,  # provider-backed default disabled
                        concurrency_policy: Optional[dict] = None,
                        misfire_policy: str = "skip",
                        approval_policy: Optional[dict] = None,
                        budget_policy: Optional[dict] = None,
                        provider_policy: Optional[dict] = None,
                        failure_policy: Optional[dict] = None,
                        first_run_at: Optional[str] = None) -> dict:
        if not cron_expression and not interval_seconds:
            raise SchedulerError("cron_expression or interval_seconds required")
        from .models import JobSchedule
        sched = JobSchedule(
            organization_id=organization_id, owner_user_id=owner_user_id,
            job_template=job_template or {}, timezone=timezone,
            cron_expression=cron_expression, interval_seconds=interval_seconds,
            enabled=bool(enabled),
            next_run_at=first_run_at or self._next_after(sched=None, now=_now_iso(),
                                                         cron=cron_expression,
                                                         interval=interval_seconds),
            concurrency_policy=concurrency_policy or {"max_concurrent": 3},
            misfire_policy=misfire_policy, approval_policy=approval_policy or {},
            budget_policy=budget_policy or {}, provider_policy=provider_policy or {},
            failure_policy=failure_policy or {},
        )
        row = self.repos.job_schedules.add(sched)
        self.audit.record(
            action="schedule.create", actor_user_id=owner_user_id,
            organization_id=organization_id, resource_type="job_schedule",
            resource_id=row["id"],
            after_meta={"job_type": (job_template or {}).get("job_type"),
                        "enabled": bool(enabled)})
        return self._sched_view(self.repos.job_schedules.get(row["id"]))

    def list_schedules(self, organization_id: str, *, include_archived: bool = False) -> list[dict]:
        rows = self.repos.job_schedules.for_org(organization_id,
                                                include_archived=include_archived)
        return [self._sched_view(r) for r in rows]

    def get_schedule(self, organization_id: str, schedule_id: str) -> Optional[dict]:
        row = self.repos.job_schedules.by_org(organization_id, schedule_id)
        return self._sched_view(row) if row else None

    def update_schedule(self, *, organization_id: str, schedule_id: str,
                        actor_user_id: str, **fields) -> dict:
        sched = self.repos.job_schedules.by_org(organization_id, schedule_id)
        if sched is None:
            raise SchedulerError("schedule not found")
        allowed = {"cron_expression", "interval_seconds", "enabled",
                   "next_run_at", "concurrency_policy", "misfire_policy",
                   "approval_policy", "budget_policy", "provider_policy",
                   "failure_policy", "job_template", "timezone"}
        sets = [k for k in fields if k in allowed]
        if not sets:
            raise SchedulerError("no updatable fields provided")
        set_sql = ", ".join(f"{k}=?" for k in sets)
        params = [fields[k] for k in sets] + [_now_iso(), schedule_id]
        self.repos.db.conn.execute(
            f"UPDATE job_schedules SET {set_sql}, updated_at=? WHERE id=?",
            params)
        self.repos.db.conn.commit()
        self.audit.record(
            action="schedule.update", actor_user_id=actor_user_id,
            organization_id=organization_id, resource_type="job_schedule",
            resource_id=schedule_id, after_meta={k: fields[k] for k in sets})
        return self._sched_view(self.repos.job_schedules.get(schedule_id))

    def set_enabled(self, *, organization_id: str, schedule_id: str,
                    enabled: bool, actor_user_id: str) -> dict:
        return self.update_schedule(organization_id=organization_id,
                                    schedule_id=schedule_id,
                                    actor_user_id=actor_user_id,
                                    enabled=bool(enabled))

    def archive(self, *, organization_id: str, schedule_id: str,
                actor_user_id: str) -> dict:
        sched = self.repos.job_schedules.by_org(organization_id, schedule_id)
        if sched is None:
            raise SchedulerError("schedule not found")
        self.repos.db.conn.execute(
            "UPDATE job_schedules SET archived=?, enabled=?, updated_at=? WHERE id=?",
            (True, False, _now_iso(), schedule_id))
        self.repos.db.conn.commit()
        self.audit.record(
            action="schedule.archive", actor_user_id=actor_user_id,
            organization_id=organization_id, resource_type="job_schedule",
            resource_id=schedule_id)
        return self._sched_view(self.repos.job_schedules.get(schedule_id))

    def posture(self, organization_id: str) -> dict:
        schedules = self.repos.job_schedules.for_org(organization_id)
        occurrences = self.repos.schedule_occurrences.list()
        return {
            "organization_id": organization_id,
            "schedule_count": len(schedules),
            "enabled_count": sum(1 for s in schedules if s.get("enabled")),
            "due_now": len(self._due_schedules(organization_id, _now_iso())),
            "occurrence_count": len(occurrences),
            "last_tick": None,
        }

    # ------------------------------------------------------------------
    # Tick (enqueue-only)
    # ------------------------------------------------------------------

    def tick(self, *, now: Optional[str] = None, max_schedules: Optional[int] = None,
             enqueue: bool = True) -> dict:
        """Advance due schedules. Never executes jobs; never calls providers."""
        now = now or _now_iso()
        due = self._due_schedules(None, now)
        if max_schedules is not None:
            due = due[:max_schedules]
        summary = {"scheduler_id": self.scheduler_id, "now": now,
                   "due": len(due), "claimed": 0, "skipped": 0,
                   "enqueued": 0, "failed": 0, "details": []}
        for sched in due:
            decision = self._process_schedule(sched, now, enqueue=enqueue)
            summary["details"].append(decision)
            summary[decision["action"]] += 1
        return summary

    def _due_schedules(self, organization_id: Optional[str], now: str) -> list[dict]:
        rows = self.repos.job_schedules.due(now)
        if organization_id:
            rows = [r for r in rows if r["organization_id"] == organization_id]
        return rows

    def _process_schedule(self, sched: dict, now: str, *, enqueue: bool) -> dict:
        schedule_id = sched["id"]
        scheduled_for = sched.get("next_run_at") or now
        occurrence_key = scheduled_for

        # 1. atomic occurrence claim (dedup across scheduler instances)
        claimed = self._claim_occurrence(schedule_id, occurrence_key, scheduled_for)
        if not claimed:
            return {"schedule_id": schedule_id, "action": "skipped",
                    "reason": "occurrence_already_claimed"}

        # 2. schedule disabled / archived (checked again under the claim)
        if not sched.get("enabled") or sched.get("archived"):
            self._mark_occurrence(claimed["id"], "skipped")
            return {"schedule_id": schedule_id, "action": "skipped",
                    "reason": "schedule_disabled"}

        # 3. misfire window (prevent unbounded catch-up)
        scheduled_dt = _parse_iso(scheduled_for) or utcnow()
        if (utcnow() - scheduled_dt).total_seconds() > self.misfire_window_seconds:
            if sched.get("misfire_policy", "skip") == "skip":
                self._mark_occurrence(claimed["id"], "misfired")
                self.audit.record(
                    action="schedule.misfire", organization_id=sched["organization_id"],
                    resource_type="job_schedule", resource_id=schedule_id,
                    after_meta={"scheduled_for": scheduled_for,
                                "policy": sched.get("misfire_policy")})
                self._advance(sched, scheduled_for)
                return {"schedule_id": schedule_id, "action": "skipped",
                        "reason": "misfire_window"}

        # 4. organization active + owner membership active
        org = self.repos.organizations.get(sched["organization_id"])
        if org is None or not org.get("active", True):
            self._mark_occurrence(claimed["id"], "skipped")
            self.audit.record(action="schedule.skip", organization_id=sched["organization_id"],
                              resource_type="job_schedule", resource_id=schedule_id,
                              after_meta={"reason": "organization_suspended"})
            self._advance(sched, scheduled_for)
            return {"schedule_id": schedule_id, "action": "skipped",
                    "reason": "organization_suspended"}
        memberships = self.repos.memberships.list(
            where={"organization_id": sched["organization_id"],
                   "user_id": sched["owner_user_id"]})
        if not any((m.get("status") or "active") == "active" for m in memberships):
            self._mark_occurrence(claimed["id"], "skipped")
            self.audit.record(action="schedule.skip", organization_id=sched["organization_id"],
                              resource_type="job_schedule", resource_id=schedule_id,
                              after_meta={"reason": "owner_revoked"})
            self._advance(sched, scheduled_for)
            return {"schedule_id": schedule_id, "action": "skipped",
                    "reason": "owner_revoked"}

        # 5. concurrency policy
        max_concurrent = int(_as_dict(sched.get("concurrency_policy")).get(
            "max_concurrent", 3) or 3)
        outstanding = self._outstanding_occurrences(schedule_id)
        if outstanding >= max_concurrent:
            self._mark_occurrence(claimed["id"], "skipped")
            self.audit.record(action="schedule.skip", organization_id=sched["organization_id"],
                              resource_type="job_schedule", resource_id=schedule_id,
                              after_meta={"reason": "concurrency_limit",
                                          "outstanding": outstanding,
                                          "max": max_concurrent})
            self._advance(sched, scheduled_for)
            return {"schedule_id": schedule_id, "action": "skipped",
                    "reason": "concurrency_limit"}

        # 6. enqueue one job (never execute)
        if not enqueue:
            self._mark_occurrence(claimed["id"], "reserved")
            return {"schedule_id": schedule_id, "action": "claimed",
                    "reason": "dry_run_occurrence"}
        try:
            job_template = _as_dict(sched.get("job_template"))
            job_type = job_template.get("job_type") or "immediate_success"
            payload = job_template.get("payload") or {}
            from .context import build_context
            from .enums import Environment, Role
            ctx = build_context(
                user_id=sched["owner_user_id"], organization_id=sched["organization_id"],
                role=Role.ORGANIZATION_OWNER.value,
                environment=Environment.PRODUCTION.value)
            job = self.service.submit(
                ctx, job_type=job_type, payload=payload,
                payload_schema_version=job_template.get("payload_schema_version", "1.0"),
                idempotency_key=f"schedule:{schedule_id}:{occurrence_key}",
                reason=f"scheduled occurrence {occurrence_key}",
                correlation_id=occurrence_key,
                service=job_template.get("service"))
            self._mark_occurrence(claimed["id"], "enqueued",
                                  enqueued_job_id=job["id"])
            self.audit.record(
                action="schedule.enqueue", organization_id=sched["organization_id"],
                resource_type="job_schedule", resource_id=schedule_id,
                job_run_ref=None,
                after_meta={"occurrence": occurrence_key, "job_id": job["id"]})
            self._advance(sched, scheduled_for)
            return {"schedule_id": schedule_id, "action": "enqueued",
                    "job_id": job["id"], "occurrence": occurrence_key}
        except Exception as e:  # noqa: BLE001 - audit + skip, never crash the tick
            self._mark_occurrence(claimed["id"], "failed")
            self.audit.record(
                action="schedule.failure", organization_id=sched["organization_id"],
                resource_type="job_schedule", resource_id=schedule_id,
                result="failure", failure_class=type(e).__name__,
                after_meta={"occurrence": occurrence_key})
            self._advance(sched, scheduled_for)
            return {"schedule_id": schedule_id, "action": "failed",
                    "reason": type(e).__name__}

    def _claim_occurrence(self, schedule_id: str, occurrence_key: str,
                          scheduled_for: str) -> Optional[dict]:
        occ = ScheduleOccurrence(schedule_id=schedule_id, occurrence_key=occurrence_key,
                                 scheduled_for=_parse_iso(scheduled_for),
                                 state="created")
        try:
            self.repos.schedule_occurrences.add(occ)
            return self.repos.schedule_occurrences.by_key(schedule_id, occurrence_key)
        except Exception:  # noqa: BLE001 - duplicate occurrence -> another instance won
            return None

    def _mark_occurrence(self, occurrence_id: str, state: str,
                         enqueued_job_id: Optional[str] = None) -> None:
        if enqueued_job_id:
            self.repos.db.conn.execute(
                "UPDATE schedule_occurrences SET state=?, enqueued_job_request_id=? "
                "WHERE id=?",
                (state, enqueued_job_id, occurrence_id))
        else:
            self.repos.db.conn.execute(
                "UPDATE schedule_occurrences SET state=? WHERE id=?",
                (state, occurrence_id))
        self.repos.db.conn.commit()

    def _outstanding_occurrences(self, schedule_id: str) -> int:
        rows = self.repos.schedule_occurrences.list(
            where={"schedule_id": schedule_id})
        return sum(1 for r in rows if r.get("state") in ("created", "enqueued",
                                                         "reserved"))

    def _advance(self, sched: dict, from_time: str) -> None:
        nxt = self._next_after(sched=sched, now=from_time,
                               cron=sched.get("cron_expression"),
                               interval=sched.get("interval_seconds"))
        self.repos.db.conn.execute(
            "UPDATE job_schedules SET last_run_at=?, next_run_at=?, updated_at=? "
            "WHERE id=?",
            (from_time, nxt, _now_iso(), sched["id"]))
        self.repos.db.conn.commit()

    @staticmethod
    def _next_after(*, sched, now: str, cron: Optional[str],
                    interval: Optional[int]) -> str:
        base = _parse_iso(now) or utcnow()
        if cron:
            try:
                return croniter(cron, base).get_next(datetime).isoformat()
            except Exception:  # noqa: BLE001 - fall back to interval
                pass
        seconds = int(interval or 3600)
        return (base + timedelta(seconds=seconds)).isoformat()

    def next_run_iso(self, *, cron: Optional[str], interval: Optional[int],
                     now: Optional[str] = None) -> str:
        return self._next_after(sched=None, now=now or _now_iso(),
                                cron=cron, interval=interval)

    @staticmethod
    def _sched_view(row: dict) -> dict:
        if row is None:
            return row
        out = dict(row)
        out["enabled"] = bool(row.get("enabled"))
        out["archived"] = bool(row.get("archived"))
        out["concurrency_policy"] = _as_dict(row.get("concurrency_policy"))
        out["job_template"] = _as_dict(row.get("job_template"))
        out["approval_policy"] = _as_dict(row.get("approval_policy"))
        out["budget_policy"] = _as_dict(row.get("budget_policy"))
        out["provider_policy"] = _as_dict(row.get("provider_policy"))
        out["failure_policy"] = _as_dict(row.get("failure_policy"))
        return out


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _as_dict(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}