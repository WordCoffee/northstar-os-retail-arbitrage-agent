"""Foundation application state (dependency container)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..db import FoundationDB
from ..repositories import Repositories
from ..identity import IdentityResolver
from ..providers import ProviderRegistry, FixtureAdapter
from ..jobs import JobOrchestrator
from ..jobs_durable import DurableJobService
from ..jobs_scheduler import JobScheduler
from ..keywords.importer import KeywordImporter
from ..billing.entitlements import EntitlementService
from ..billing.service import BillingService
from ..billing.signup import InviteService
from ..operations.lifecycle import OrgLifecycleService
from ..operations.admin import AdminOpsService
from ..operations.support import SupportService
from ..operations.dashboard import TesterDashboard
from ..operations.plan import PlanUsageService
from ..usage import UsageLedger
from ..audit import AuditService
from ..approvals import ApprovalService
from ..models import Marketplace, PricingPolicy, ProviderDefinition


@dataclass
class FoundationState:
    db: FoundationDB
    repos: Repositories
    identity: IdentityResolver
    providers: ProviderRegistry
    jobs: JobOrchestrator
    jobs_durable: DurableJobService
    scheduler: JobScheduler
    keywords: KeywordImporter
    billing: BillingService
    entitlements: EntitlementService
    invites: InviteService
    lifecycle: OrgLifecycleService
    admin_ops: AdminOpsService
    support: SupportService
    dashboard: TesterDashboard
    plan_usage: PlanUsageService
    usage: UsageLedger
    audit: AuditService
    approvals: ApprovalService

    @classmethod
    def build(cls, db_path: Optional[str] = None, *, seed: bool = True) -> "FoundationState":
        # An explicit db_path always means SQLite (authoritative over env).
        # Otherwise DB_URL/FOUNDATION_DB_URL selects PostgreSQL; else SQLite temp.
        import os as _os
        _url = _os.environ.get("DB_URL") or _os.environ.get("FOUNDATION_DB_URL")
        if db_path is not None:
            db = FoundationDB(db_path)
        elif _url:
            from ..db_postgres import PostgresFoundationDB
            db = PostgresFoundationDB(_url)
            # P2-T4: fail closed in hosted environments if migrations are behind.
            from ..migrations_check import assert_migrations_current
            _migrations_dir = str(Path(__file__).resolve().parents[2] / "migrations_foundation")
            assert_migrations_current(
                db, environment=_os.environ.get("ENVIRONMENT"),
                migrations_dir=_migrations_dir)
        else:
            db = FoundationDB(db_path)
        repos = Repositories(db)
        audit = AuditService(repos)
        approvals = ApprovalService(repos, audit)
        durable = DurableJobService(repos, audit=audit, approvals=approvals)
        importer = KeywordImporter(repos, audit=audit)
        durable.register_service("keyword_importer", importer)
        entitlements = EntitlementService(repos)
        durable.register_service("entitlements", entitlements)
        lifecycle = OrgLifecycleService(repos, audit=audit)
        admin_ops = AdminOpsService(repos, lifecycle_svc=lifecycle, audit=audit)
        support = SupportService(repos, audit=audit)
        state = cls(
            db=db,
            repos=repos,
            identity=IdentityResolver(repos),
            providers=ProviderRegistry(repos),
            jobs=JobOrchestrator(repos),
            jobs_durable=durable,
            scheduler=JobScheduler(durable, repos, scheduler_id="state-scheduler"),
            keywords=importer,
            billing=BillingService(repos, entitlements=entitlements, audit=audit),
            entitlements=entitlements,
            invites=InviteService(repos, audit=audit),
            lifecycle=lifecycle,
            admin_ops=admin_ops,
            support=support,
            dashboard=TesterDashboard(repos, admin=admin_ops, support=support,
                                      audit=audit),
            plan_usage=PlanUsageService(entitlements, lifecycle),
            usage=UsageLedger(repos),
            audit=audit,
            approvals=approvals,
        )
        if seed:
            state.seed()
        return state

    def seed(self) -> None:
        """Seed reference data only (marketplace, pricing policy, fixture providers).
        No operational/customer data is fabricated."""
        if self.repos.marketplaces.by_code("amazon.com") is None:
            self.repos.marketplaces.add(Marketplace())  # amazon.com / US / USD (owner decision 1)
        if self.repos.pricing.latest() is None:
            self.repos.pricing.add(PricingPolicy())
        # Register providers (fixture adapters bound), both DISABLED by default.
        for key, name, cat in (("ollama", "Ollama (local)", "ai"),
                                ("fixture_price", "Fixture Price (dev)", "discovery")):
            if self.repos.providers.by_key(key) is None:
                self.providers.register_definition(ProviderDefinition(
                    provider_key=key, name=name, category=cat,
                    credential_ref_names=[], enabled=False,
                    sandbox_supported=True,
                ))
        self.providers.bind_adapter(FixtureAdapter(
            "fixture_price", {"sample_price": {"amount": 12.34, "currency": "USD"}}))
        self.providers.bind_adapter(FixtureAdapter("ollama", {}))
        # Close any read transaction opened by the idempotent by_key/latest
        # checks so the connection never holds an idle-in-transaction snapshot
        # (which would block DDL/vacuum on PostgreSQL).
        self.db.conn.commit()

    def close(self) -> None:
        self.db.close()