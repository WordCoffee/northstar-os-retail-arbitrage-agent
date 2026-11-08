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

RUNNING = ("claimed", "running", "ready")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(db: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(db or DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


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
             branch or f"ty/{stem}", json.dumps([list(c) for c in acceptance]),
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
    job["acceptance"] = json.loads(job.get("acceptance") or "[]")
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


def claim(job_id: str, owner: str, *, db: Optional[Path] = None) -> Dict[str, Any]:
    """Claim a job atomically, refusing an overlapping scope.

    BEGIN IMMEDIATE takes the write lock before the overlap question is asked, so two
    directors cannot both see "no conflict" and both claim.
    """
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
        conn.execute(f"UPDATE jobs SET {assignments} WHERE id=?",
                     (*fields.values(), job_id))
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
    """
    path = Path(mirror_path or MIRROR)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {"units": {}, "jobs": []}
    rows = jobs(db=db)
    rows.sort(key=lambda row: (int(row.get("rank") or 0), row.get("created_at") or ""))
    data["jobs"] = rows
    data["updated_at"] = _now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True, "jobs": len(data["jobs"])}


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
    args = parser.parse_args(argv)

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
