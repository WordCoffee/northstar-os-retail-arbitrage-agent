"""Director queue: jobs, scope manifests, overlap serialisation, worktrees, merges.

The queue is the ranked gap list expressed as claims. Two properties matter and both
are enforced here rather than by convention:

* **No two concurrent jobs may write the same path.** A manifest is a list of
  repo-relative paths (a directory scopes its tree). A claim that overlaps a running
  job is *refused*, not queued behind it silently, so the Director can serialise it
  deliberately.
* **`main` is never moved by the loop.** Merges land on `staging`. A merge to main
  requires `verifier_reproduced=True`, and without it the call refuses by name.

    python tools/director_queue.py --add --unit D3 --title "..." --paths a,b
    python tools/director_queue.py --claim <job> --owner builder-1
    python tools/director_queue.py --list
    python tools/director_queue.py --merge <job> --gates "python -m pytest -q x.py"
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "director"
DB = STATE / "queue.sqlite"
MIRROR = ROOT / "reports" / "ty" / "director_queue.json"
WORKTREES = ROOT / "state" / "worktrees"
STAGING = "staging"
PROTECTED = ("main", "master")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    unit TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    owner TEXT NOT NULL DEFAULT '',
    write_paths TEXT NOT NULL DEFAULT '[]',
    branch TEXT NOT NULL DEFAULT '',
    worktree TEXT NOT NULL DEFAULT '',
    rollback_tag TEXT NOT NULL DEFAULT '',
    acceptance TEXT NOT NULL DEFAULT '[]',
    tokens INTEGER NOT NULL DEFAULT 0,
    score_before REAL,
    score_after REAL,
    evidence TEXT NOT NULL DEFAULT '',
    rank INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    at TEXT NOT NULL,
    job TEXT NOT NULL,
    event TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);
"""

#: Columns added after the first schema shipped. A live store is migrated in place on
#: connect; a fresh one gets them from SCHEMA. `rank` was used by `set_rank()` and by the
#: mirror's ordering for a day while existing only in the hand-migrated live database,
#: so any fresh store (a test, a new machine, a rebuilt one) raised "no such column: rank".
MIGRATIONS = (
    ("rank", "ALTER TABLE jobs ADD COLUMN rank INTEGER NOT NULL DEFAULT 0"),
)

RUNNING = ("claimed", "running", "ready")

#: Units that do not occupy a builder lane (measurement, verification, operator work).
NO_BUILDER_LANES = ("operator", "verifier", "measurement")

#: Test seam: a callable returning the RAM governor's verdict. ``None`` means the real
#: `tools/ram_governor.py`, imported on demand so a queue-only test never measures RAM.
DEFAULT_GOVERNOR: Optional[Callable[[], Dict[str, Any]]] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(db: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(db or DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> List[str]:
    """Add the columns SCHEMA gained after a store was created. Idempotent."""
    have = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    added: List[str] = []
    for column, statement in MIGRATIONS:
        if column in have:
            continue
        conn.execute(statement)
        added.append(column)
    return added


def _norm(path: str) -> str:
    text = str(path).strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.rstrip("/")


def paths_conflict(left: Iterable[str], right: Iterable[str]) -> List[str]:
    """Every path pair where one side is the other or contains it.

    A declared directory scopes its tree: `northstar-os-ui/src` and
    `northstar-os-ui/src/App.tsx` overlap, and so do two identical files.
    """
    hits: List[str] = []
    a = [_norm(p) for p in left or () if str(p).strip()]
    b = [_norm(p) for p in right or () if str(p).strip()]
    for one in a:
        for other in b:
            if one == other or one.startswith(other + "/") or other.startswith(one + "/"):
                hits.append(one if one == other else f"{one} <-> {other}")
    return sorted(set(hits))


def acceptance_list(value: Any) -> List[str]:
    """Acceptance entries are commands: one non-empty string per check.

    A caller that passed a plain string used to be exploded into one entry per
    character — ``[list(c) for c in "..." ]`` — so a 400-character acceptance
    line became 400 one-character "commands". That is why several jobs in
    ``reports/ty/director_queue.json`` carried an ``acceptance`` array with one
    entry per letter, and why the readable resume mirror became unreadable.
    A string is now split on newlines; a sequence of strings is kept as-is.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    out: List[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(text)
        else:
            joined = " ".join(str(part) for part in item).strip()
            if joined:
                out.append(joined)
    return out


def _repair_acceptance(entries: Sequence[Any]) -> List[str]:
    """Rebuild a row written by the character-exploding bug.

    The signature is unambiguous: more than eight entries, every one of them a
    single character. Joining them restores the original command instead of
    leaving 400 fragments in the store and the mirror.
    """
    items = list(entries or [])
    if len(items) > 8 and all(isinstance(x, str) and len(x) == 1 for x in items):
        return ["".join(items).strip()]
    return acceptance_list(items)


def _event(conn: sqlite3.Connection, job: str, event: str, detail: str = "") -> None:
    conn.execute("INSERT INTO events(at, job, event, detail) VALUES (?,?,?,?)",
                 (_now(), job, event, detail))


def add_job(*, db: Optional[Path] = None, unit: str, title: str,
            write_paths: Sequence[str], acceptance: Sequence[Sequence[str]] = (),
            job_id: str = "", branch: str = "", rollback_tag: str = "") -> Dict[str, Any]:
    conn = _connect(db)
    stem = job_id or f"{unit.lower()}-{int(time.time() * 1000) % 1000000}"
    now = _now()
    try:
        conn.execute(
            "INSERT INTO jobs(id, unit, title, status, write_paths, branch, acceptance,"
            " rollback_tag, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (stem, unit, title, "queued", json.dumps(list(write_paths)),
             branch or f"ty/{stem}", json.dumps(acceptance_list(acceptance)),
             rollback_tag, now, now))
        _event(conn, stem, "added", title)
    except sqlite3.IntegrityError:
        return {"ok": False, "reason": "job_exists", "id": stem}
    finally:
        conn.close()
    mirror(db)
    return {"ok": True, "id": stem}


def _row_to_job(row: sqlite3.Row) -> Dict[str, Any]:
    job = dict(row)
    job["write_paths"] = json.loads(job.get("write_paths") or "[]")
    job["acceptance"] = _repair_acceptance(json.loads(job.get("acceptance") or "[]"))
    return job


def jobs(*, db: Optional[Path] = None, status: str = "") -> List[Dict[str, Any]]:
    conn = _connect(db)
    try:
        if status:
            rows = conn.execute("SELECT * FROM jobs WHERE status=? ORDER BY created_at",
                                (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at").fetchall()
        return [_row_to_job(row) for row in rows]
    finally:
        conn.close()


def job(job_id: str, *, db: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    conn = _connect(db)
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None
    finally:
        conn.close()


def conflicts(job_id: str, *, db: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Running jobs whose manifests overlap this one."""
    target = job(job_id, db=db)
    if not target:
        return []
    out = []
    for other in jobs(db=db):
        if other["id"] == job_id or other["status"] not in RUNNING:
            continue
        hits = paths_conflict(target["write_paths"], other["write_paths"])
        if hits:
            out.append({"id": other["id"], "owner": other["owner"], "hits": hits})
    return out


def unit_needs_builder(unit: str) -> bool:
    """Whether a unit's jobs occupy a builder lane.

    The queue holds builder jobs, so the default is True. A unit opts out in the
    readable mirror (``"needs_builder": false``, or a lane of operator/verifier/
    measurement), which is what keeps a paused governor from blocking bookkeeping.
    """
    try:
        data = json.loads(MIRROR.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    row = (data.get("units") or {}).get(unit) or {}
    if not isinstance(row, dict):
        return True
    if row.get("needs_builder") is False:
        return False
    return str(row.get("lane") or "").lower() not in NO_BUILDER_LANES


def _query_governor(governor: Optional[Callable[[], Dict[str, Any]]], *,
                    who: str) -> Optional[Dict[str, Any]]:
    """Ask the RAM governor. Explicit first, then the injected default, then the real one.

    A governor that cannot answer must not wedge the queue: ``None`` means "no verdict"
    and the claim proceeds. The refusal path is only for a measured pause.
    """
    callable_governor = governor if governor is not None else DEFAULT_GOVERNOR
    if callable_governor is not None:
        try:
            return callable_governor()
        except Exception:  # noqa: BLE001 - a broken stub is not a pause
            return None
    try:
        tools_dir = str(ROOT / "tools")
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        import ram_governor  # noqa: PLC0415 - local tool, loaded on demand

        return ram_governor.status(who=f"claim:{who}", record=True)
    except Exception:  # noqa: BLE001 - the queue stays usable without a probe
        return None


def _note_ram_refusal(job_id: str, owner: str, verdict: Dict[str, Any],
                      db: Optional[Path] = None) -> None:
    """Record the refusal on the job's event trail; the status stays queued."""
    try:
        conn = _connect(db)
        try:
            _event(conn, job_id, "ram_refused",
                   f"{owner}: {verdict.get('free_gb')} GB free, max_builders="
                   f"{verdict.get('max_builders')}")
        finally:
            conn.close()
    except sqlite3.Error:
        pass


def claim(job_id: str, owner: str, *, db: Optional[Path] = None,
          governor: Optional[Callable[[], Dict[str, Any]]] = None,
          needs_builder: Optional[bool] = None) -> Dict[str, Any]:
    """Claim a job atomically, refusing an overlapping scope or a paused RAM gate.

    The RAM question is asked before the write lock is taken: a paused governor means
    there is no point handing back a job nobody can run, and the measurement costs a
    probe, not a lock. ``governor`` is injectable so tests never depend on the machine.
    """
    current = job(job_id, db=db)
    if current and current["status"] == "queued":
        builder_work = (needs_builder if needs_builder is not None
                        else unit_needs_builder(current["unit"]))
        if builder_work:
            verdict = _query_governor(governor, who=owner)
            if verdict and verdict.get("paused"):
                _note_ram_refusal(job_id, owner, verdict, db)
                return {"ok": False, "reason": "ram_paused", "id": job_id,
                        "free_gb": verdict.get("free_gb"),
                        "max_builders": verdict.get("max_builders"),
                        "detail": verdict.get("reason")}

    conn = _connect(db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return {"ok": False, "reason": "no_such_job", "id": job_id}
        current = _row_to_job(row)
        if current["status"] not in ("queued",):
            conn.execute("ROLLBACK")
            return {"ok": False, "reason": f"not_claimable:{current['status']}",
                    "id": job_id}
        mine = current["write_paths"]
        for other in conn.execute("SELECT * FROM jobs WHERE status IN (?,?,?)",
                                  RUNNING).fetchall():
            hits = paths_conflict(mine, json.loads(other["write_paths"] or "[]"))
            if hits:
                conn.execute("ROLLBACK")
                return {"ok": False, "reason": "scope_overlap", "id": job_id,
                        "conflicts": [{"id": other["id"], "hits": hits}]}
        now = _now()
        conn.execute("UPDATE jobs SET status='claimed', owner=?, updated_at=? WHERE id=?",
                     (owner, now, job_id))
        _event(conn, job_id, "claimed", owner)
        conn.execute("COMMIT")
    finally:
        conn.close()
    mirror(db)
    return {"ok": True, "id": job_id, "owner": owner}


def set_status(job_id: str, status: str, *, db: Optional[Path] = None,
               **extra: Any) -> Dict[str, Any]:
    allowed = {"queued", "claimed", "running", "ready", "merged", "rejected",
               "released", "blocked"}
    if status not in allowed:
        return {"ok": False, "reason": f"unknown_status:{status}"}
    conn = _connect(db)
    try:
        fields = {"status": status, "updated_at": _now()}
        for key in ("owner", "branch", "worktree", "rollback_tag", "evidence"):
            if key in extra:
                fields[key] = str(extra[key])
        for key in ("tokens",):
            if key in extra:
                fields[key] = int(extra[key])
        for key in ("score_before", "score_after"):
            if key in extra:
                fields[key] = float(extra[key])
        assignments = ", ".join(f"{key}=?" for key in fields)
        cursor = conn.execute(f"UPDATE jobs SET {assignments} WHERE id=?",
                              (*fields.values(), job_id))
        if cursor.rowcount == 0:
            # A status write that changed nothing must not report success: the caller
            # would record a merge against a job the store never had.
            return {"ok": False, "reason": "no_such_job", "id": job_id}
        _event(conn, job_id, status, str(extra.get("detail") or ""))
    finally:
        conn.close()
    mirror(db)
    return {"ok": True, "id": job_id, "status": status}


def mirror(db: Optional[Path] = None, mirror_path: Optional[Path] = None) -> Dict[str, Any]:
    """Keep the readable JSON in step. It is for resume, not for authority.

    The queue is a *ranked* list, so the mirror is ordered by `rank` first (lower runs
    first), then by creation time. Insertion order alone made "the next job" depend on when
    a row happened to be added, which is not a ranking.

    **Jobs that exist only in the mirror are kept, not deleted.** The mirror is what a
    resume reads, so a job written there by a hand edit (or by a writer that died before
    the store was updated) is real work; dropping it because the store never heard of it
    is silent loss on the resume path. They travel in `mirror_only_jobs` until
    `import_mirror()` adopts them.
    """
    path = Path(mirror_path or MIRROR)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {"units": {}, "jobs": []}
    previous = [row for row in (data.get("jobs") or []) if isinstance(row, dict)]
    rows = jobs(db=db)
    rows.sort(key=lambda row: (int(row.get("rank") or 0), row.get("created_at") or ""))
    known = {row["id"] for row in rows}
    orphans: List[Dict[str, Any]] = []
    for row in previous:
        jid = str(row.get("id") or "")
        if jid and jid not in known and not any(o.get("id") == jid for o in orphans):
            orphans.append(row)
    data["jobs"] = rows + orphans
    data["mirror_only_jobs"] = [str(row.get("id")) for row in orphans]
    data["updated_at"] = _now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True, "jobs": len(rows), "mirror_only": len(orphans),
            "mirror_only_jobs": data["mirror_only_jobs"]}


def import_mirror(*, db: Optional[Path] = None,
                  mirror_path: Optional[Path] = None) -> Dict[str, Any]:
    """Adopt the mirror's jobs into the store: insert the missing, update the changed.

    The failure this repairs was measured on 2026-11-11: the store held 35 jobs while the
    resume mirror held 41, and `mirror()` rewrote the JSON from the store — so four jobs
    (the only record of work in flight) were deleted by the next status write. The mirror
    is read on every resume, so the two must never disagree silently.
    """
    path = Path(mirror_path or MIRROR)
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [row for row in (data.get("jobs") or []) if isinstance(row, dict)]
    conn = _connect(db)
    inserted: List[str] = []
    updated: List[str] = []
    unchanged: List[str] = []
    try:
        for row in rows:
            jid = str(row.get("id") or "").strip()
            if not jid:
                continue
            values = {
                "unit": str(row.get("unit") or "U"),
                "title": str(row.get("title") or jid),
                "status": str(row.get("status") or "queued"),
                "owner": str(row.get("owner") or ""),
                "write_paths": json.dumps(list(row.get("write_paths") or [])),
                "branch": str(row.get("branch") or f"ty/{jid}"),
                "worktree": str(row.get("worktree") or ""),
                "rollback_tag": str(row.get("rollback_tag") or ""),
                "acceptance": json.dumps(_repair_acceptance(row.get("acceptance") or [])),
                "tokens": int(row.get("tokens") or 0),
                "score_before": row.get("score_before"),
                "score_after": row.get("score_after"),
                "evidence": (json.dumps(row.get("evidence"), ensure_ascii=False)
                             if isinstance(row.get("evidence"), (list, dict))
                             else str(row.get("evidence") or "")),
                "rank": int(row.get("rank") or 0),
            }
            existing = conn.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO jobs(id, unit, title, status, owner, write_paths, branch,"
                    " worktree, rollback_tag, acceptance, tokens, score_before, score_after,"
                    " evidence, rank, created_at, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (jid, values["unit"], values["title"], values["status"], values["owner"],
                     values["write_paths"], values["branch"], values["worktree"],
                     values["rollback_tag"], values["acceptance"], values["tokens"],
                     values["score_before"], values["score_after"], values["evidence"],
                     values["rank"], str(row.get("created_at") or _now()), _now()))
                _event(conn, jid, "imported", "from mirror")
                inserted.append(jid)
                continue
            merged = {**dict(existing), **values}
            changed = any(str(dict(existing).get(key)) != str(value)
                          for key, value in values.items())
            if not changed:
                unchanged.append(jid)
                continue
            conn.execute(
                "UPDATE jobs SET unit=?, title=?, status=?, owner=?, write_paths=?, branch=?,"
                " worktree=?, rollback_tag=?, acceptance=?, tokens=?, score_before=?,"
                " score_after=?, evidence=?, rank=?, updated_at=? WHERE id=?",
                (merged["unit"], merged["title"], merged["status"], merged["owner"],
                 merged["write_paths"], merged["branch"], merged["worktree"],
                 merged["rollback_tag"], merged["acceptance"], merged["tokens"],
                 merged["score_before"], merged["score_after"], merged["evidence"],
                 merged["rank"], _now(), jid))
            _event(conn, jid, "imported", "mirror status/fields updated")
            updated.append(jid)
        conn.commit()
    finally:
        conn.close()
    written = mirror(db=db, mirror_path=path)
    return {"ok": True, "inserted": inserted, "updated": updated,
            "unchanged": len(unchanged), "mirror_only": written["mirror_only"]}


def set_rank(job_id: str, rank: int, *, db: Optional[Path] = None) -> Dict[str, Any]:
    """Put a job at a position in the ranked list. Lower runs first."""
    conn = _connect(db)
    try:
        conn.execute("UPDATE jobs SET rank=?, updated_at=? WHERE id=?",
                     (int(rank), _now(), job_id))
        _event(conn, job_id, "ranked", str(rank))
    finally:
        conn.close()
    mirror(db)
    return {"ok": True, "id": job_id, "rank": int(rank)}


# ------------------------------------------------------------------- worktrees
def _git(*args: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *[str(a) for a in args]],
                          cwd=str(cwd or ROOT), capture_output=True, text=True)


def worktree_add(name: str, base: str = "HEAD") -> Dict[str, Any]:
    """One worktree per builder. Builders never touch the main working tree."""
    path = WORKTREES / name
    if path.exists():
        return {"ok": False, "reason": "worktree_exists", "path": str(path)}
    path.parent.mkdir(parents=True, exist_ok=True)
    out = _git("worktree", "add", "-b", f"ty/{name}", str(path), base)
    if out.returncode != 0:
        return {"ok": False, "reason": "git_failed",
                "detail": (out.stderr or out.stdout).strip()[:400]}
    return {"ok": True, "name": name, "path": str(path), "branch": f"ty/{name}"}


def worktree_remove(name: str, force: bool = False) -> Dict[str, Any]:
    path = WORKTREES / name
    args = ["worktree", "remove", str(path)]
    if force:
        args.append("--force")
    out = _git(*args)
    return {"ok": out.returncode == 0,
            "detail": (out.stderr or out.stdout).strip()[:400]}


def worktrees() -> List[Dict[str, str]]:
    out = _git("worktree", "list", "--porcelain")
    rows: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for line in (out.stdout or "").splitlines():
        if not line.strip():
            if current:
                rows.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value.strip()
    if current:
        rows.append(current)
    return rows


# ---------------------------------------------------------------------- merges
def ensure_staging() -> Dict[str, Any]:
    out = _git("rev-parse", "--verify", STAGING)
    if out.returncode == 0:
        return {"ok": True, "branch": STAGING}
    out = _git("branch", STAGING)
    return {"ok": out.returncode == 0, "branch": STAGING,
            "detail": (out.stderr or "").strip()[:300]}


def _gates(commands: Sequence[Sequence[str]], cwd: Optional[Path] = None) -> Dict[str, Any]:
    results = []
    ok = True
    for cmd in commands or ():
        argv = [str(part) for part in cmd]
        if not argv:
            continue
        started = time.time()
        try:
            proc = subprocess.run(argv, cwd=str(cwd or ROOT), capture_output=True,
                                  text=True, timeout=1800)
            passed = proc.returncode == 0
            detail = ((proc.stdout or "") + (proc.stderr or ""))[-600:]
            code = proc.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            passed, detail, code = False, str(exc), 127
        ok = ok and passed
        results.append({"cmd": " ".join(argv), "exit": code, "ok": passed,
                        "seconds": round(time.time() - started, 1), "detail": detail})
        if not ok:
            break
    return {"ok": ok, "checks": results}


def merge(job_id: str, *, db: Optional[Path] = None, into: str = STAGING,
          gates: Sequence[Sequence[str]] = (), verifier_reproduced: bool = False,
          ran_gates: Callable[[Sequence[Sequence[str]]], Dict[str, Any]] = _gates
          ) -> Dict[str, Any]:
    """Merge a ready job, but never move main without the verifier.

    The gates run **after** the merge and a failure resets the branch to the exact
    commit it had before, so a red merge cannot linger.
    """
    if into in PROTECTED and not verifier_reproduced:
        return {"ok": False, "reason": "protected_branch",
                "detail": f"{into} moves only when the independent verifier reproduces "
                          "the scorecard result; pass verifier_reproduced=True then"}
    target = job(job_id, db=db)
    if not target:
        return {"ok": False, "reason": "no_such_job"}
    if target["status"] not in ("ready", "claimed", "running"):
        return {"ok": False, "reason": f"not_mergeable:{target['status']}"}
    branch = target.get("branch") or f"ty/{job_id}"
    before = _git("rev-parse", into).stdout.strip()
    checkout = _git("checkout", into)
    if checkout.returncode != 0:
        return {"ok": False, "reason": "checkout_failed",
                "detail": (checkout.stderr or "").strip()[:300]}
    merged = _git("merge", "--no-ff", "-m",
                  f"merge {job_id}: {target['title'][:80]}", branch)
    if merged.returncode != 0:
        _git("merge", "--abort")
        return {"ok": False, "reason": "merge_conflict",
                "detail": (merged.stderr or merged.stdout).strip()[:500]}
    result = ran_gates(list(gates) or target.get("acceptance") or [])
    if not result.get("ok"):
        if before:
            _git("reset", "--hard", before)
        set_status(job_id, "rejected", db=db,
                   evidence=json.dumps(result.get("checks"), ensure_ascii=False)[:2000],
                   detail="gates_failed_after_merge")
        return {"ok": False, "reason": "gates_failed", "checks": result.get("checks"),
                "reverted_to": before}
    set_status(job_id, "merged", db=db,
               evidence=json.dumps(result.get("checks"), ensure_ascii=False)[:2000],
               detail=f"merged into {into}")
    return {"ok": True, "id": job_id, "into": into,
            "commit": _git("rev-parse", "HEAD").stdout.strip(),
            "checks": result.get("checks")}


def release(job_id: str, *, db: Optional[Path] = None,
            owner: str = "") -> Dict[str, Any]:
    return set_status(job_id, "released", db=db, owner=owner)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Director queue")
    parser.add_argument("--add", action="store_true")
    parser.add_argument("--unit", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--paths", default="")
    parser.add_argument("--id", default="")
    parser.add_argument("--claim")
    parser.add_argument("--owner", default="")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--merge")
    parser.add_argument("--gates", default="")
    parser.add_argument("--into", default=STAGING)
    parser.add_argument("--import-mirror", action="store_true",
                        help="adopt jobs that exist only in reports/ty/director_queue.json")
    parser.add_argument("--mirror", action="store_true",
                        help="rewrite the readable mirror from the store")
    parser.add_argument("--set-status", nargs=2, metavar=("JOB", "STATUS"),
                        help="record a job's status in the store and mirror")
    parser.add_argument("--rank", nargs=2, metavar=("JOB", "RANK"), type=str,
                        help="put a job at a position in the ranked list")
    parser.add_argument("--evidence", default="", help="with --set-status")
    args = parser.parse_args(argv)

    if args.rank:
        job_id, rank = args.rank
        print(json.dumps(set_rank(job_id, int(rank)), indent=2))
        return 0
    if args.import_mirror:
        print(json.dumps(import_mirror(), indent=2))
        return 0
    if args.mirror:
        print(json.dumps(mirror(), indent=2))
        return 0
    if args.set_status:
        job_id, status = args.set_status
        print(json.dumps(set_status(job_id, status, evidence=args.evidence), indent=2))
        return 0
    if args.add:
        print(json.dumps(add_job(unit=args.unit, title=args.title,
                                 write_paths=[p for p in args.paths.split(",") if p],
                                 job_id=args.id), indent=2))
        return 0
    if args.claim:
        print(json.dumps(claim(args.claim, args.owner or "director"), indent=2))
        return 0
    if args.merge:
        gates = [[part for part in args.gates.split()]] if args.gates else []
        print(json.dumps(merge(args.merge, into=args.into, gates=gates), indent=2))
        return 0
    print(json.dumps({"jobs": jobs(),
                      "worktrees": worktrees()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
