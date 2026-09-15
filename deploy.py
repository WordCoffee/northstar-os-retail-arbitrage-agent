#!/usr/bin/env python3
"""Deployment script for Northstar OS.

Handles:
- Environment validation
- Database migrations
- Health checks
- Service startup

Usage:
    python deploy.py check     # Validate environment
    python deploy.py migrate   # Run database migrations
    python deploy.py start     # Start the server
    python deploy.py status    # Check all services
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "Northstar_backend"))


def check_environment():
    """Validate environment configuration."""
    print("🔍 Checking environment...")

    issues = []

    # Check .env file
    env_file = Path("Northstar_backend/.env")
    if env_file.exists():
        print("  ✅ .env file found")
    else:
        print("  ⚠️  No .env file (using defaults)")
        issues.append("No .env file — using default configuration")

    # Check required directories
    dirs = ["Northstar_backend/data", "Northstar_backend/static", "logs"]
    for d in dirs:
        path = Path(d)
        if path.exists():
            print(f"  ✅ {d}/ exists")
        else:
            path.mkdir(parents=True, exist_ok=True)
            print(f"  📁 Created {d}/")

    # Check Ollama
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            print(f"  ✅ Ollama running ({len(models)} models)")
            if any("qwen3" in n for n in model_names):
                print("  ✅ qwen3 model available")
            else:
                print("  ⚠️  qwen3 model not found — pull with: ollama pull qwen3:14b")
        else:
            print("  ❌ Ollama not responding")
            issues.append("Ollama not running — start with: ollama serve")
    except Exception:
        print("  ❌ Ollama not reachable")
        issues.append("Ollama not running — start with: ollama serve")

    # Check Python version
    if sys.version_info >= (3, 10):
        print(f"  ✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        print(f"  ❌ Python {sys.version_info.major}.{sys.version_info.minor} (need 3.10+)")
        issues.append(f"Python {sys.version_info.major}.{sys.version_info.minor} is below minimum 3.10")

    # Check dependencies
    try:
        import fastapi
        import uvicorn
        import httpx
        print(f"  ✅ FastAPI {fastapi.__version__}")
    except ImportError as e:
        print(f"  ❌ Missing dependency: {e}")
        issues.append(f"Missing dependency: {e}")

    # Check ports
    import socket
    for port in [8000, 5432, 6379, 11434]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", port))
        sock.close()
        if result == 0:
            print(f"  ✅ Port {port} in use")
        else:
            print(f"  ⚠️  Port {port} free")

    print()
    if issues:
        print("⚠️  Issues found:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("✅ All checks passed!")

    return len(issues) == 0


def run_migrations():
    """Run database migrations."""
    print("🔄 Running database migrations...")
    try:
        from data_layer import get_database
        db = get_database()
        print(f"  ✅ Database initialized: {db.db_type}")
        print(f"  ✅ Tables: {len(db.tables)} created")
    except Exception as e:
        print(f"  ❌ Migration failed: {e}")
        return False
    return True


def check_services():
    """Check status of all services."""
    print("🏥 Checking services...")

    services = [
        ("Ollama", "http://localhost:11434/api/tags"),
        ("Northstar API", "http://localhost:8000/health"),
        ("PostgreSQL", None),
        ("Redis", None),
    ]

    import socket
    for name, url in services:
        if url:
            try:
                import httpx
                resp = httpx.get(url, timeout=5)
                if resp.status_code == 200:
                    print(f"  ✅ {name}: running")
                else:
                    print(f"  ⚠️  {name}: HTTP {resp.status_code}")
            except Exception:
                print(f"  ❌ {name}: not reachable")
        else:
            port = 5432 if "PostgreSQL" in name else 6379
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            if result == 0:
                print(f"  ✅ {name}: running")
            else:
                print(f"  ⚠️  {name}: not running (port {port} free)")


def start_server():
    """Start the Northstar API server."""
    print("🚀 Starting Northstar OS API server...")
    os.chdir(str(Path(__file__).parent / "Northstar_backend"))
    os.system("python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload")


def main():
    if len(sys.argv) < 2:
        print("Usage: python deploy.py [check|migrate|start|status]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "check":
        check_environment()
    elif command == "migrate":
        run_migrations()
    elif command == "start":
        start_server()
    elif command == "status":
        check_services()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python deploy.py [check|migrate|start|status]")
        sys.exit(1)


if __name__ == "__main__":
    main()
