"""Tests for chromeconnect_guard.py — Playwright import guard with e2e/localhost exception."""

import sys
import os
import tempfile
import textwrap
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_test_file(test_file: Path, project_root: Path):
    """Run a test file in a subprocess with proper PYTHONPATH."""
    import subprocess
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([
        sys.executable, str(test_file)
    ], capture_output=True, text=True, timeout=30, env=env)


def test_guard_refuses_playwright_outside_instruction():
    """Direct import of playwright is refused outside controller instruction."""
    import tools.chromeconnect_guard as guard
    guard.enforce("test")
    try:
        import playwright.async_api  # noqa: F401
        assert False, "Should have raised DirectPlaywrightUseRefused"
    except guard.DirectPlaywrightUseRefused:
        pass  # expected


def test_guard_allows_playwright_inside_instruction():
    """Import is allowed inside a controller_instruction context."""
    import tools.chromeconnect_guard as guard
    guard.enforce("test")
    with guard.controller_instruction("test_ins"):
        # Should not raise
        import playwright.async_api  # noqa: F401


def test_guard_refuses_external_host_even_in_e2e_dir(tmp_path):
    """An e2e test targeting a non-localhost host is refused."""
    test_dir = tmp_path / "tests" / "e2e"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "test_external.py"
    test_file.write_text(textwrap.dedent("""
    import tools.chromeconnect_guard as guard
    guard.enforce("test")
    BASE_URL = "https://example.com"
    import playwright.async_api
    """))
    
    result = run_test_file(test_file, PROJECT_ROOT)
    
    assert result.returncode != 0, f"Expected failure, got returncode 0. stderr: {result.stderr}"
    assert "DirectPlaywrightUseRefused" in result.stderr


def test_guard_allows_localhost_in_e2e_dir(tmp_path):
    """An e2e test targeting only localhost is allowed."""
    test_dir = tmp_path / "tests" / "e2e"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "test_localhost.py"
    test_file.write_text(textwrap.dedent("""
    import tools.chromeconnect_guard as guard
    guard.enforce("test")
    BASE_URL = "http://localhost:8101"
    import playwright.async_api
    print("OK")
    """))
    
    result = run_test_file(test_file, PROJECT_ROOT)
    
    assert result.returncode == 0, f"stdout: {result.stdout}, stderr: {result.stderr}"
    assert "OK" in result.stdout


def test_guard_refuses_outside_e2e_dir(tmp_path):
    """A test outside tests/e2e/ is refused even with localhost URL."""
    test_dir = tmp_path / "tests" / "unit"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "test_something.py"
    test_file.write_text(textwrap.dedent("""
    import tools.chromeconnect_guard as guard
    guard.enforce("test")
    BASE_URL = "http://localhost:8101"
    import playwright.async_api
    """))
    
    result = run_test_file(test_file, PROJECT_ROOT)
    
    assert result.returncode != 0, f"Expected failure, got returncode 0. stderr: {result.stderr}"
    assert "DirectPlaywrightUseRefused" in result.stderr


def test_guard_refuses_amazon_host_even_in_e2e_dir(tmp_path):
    """An e2e test targeting Amazon is refused."""
    test_dir = tmp_path / "tests" / "e2e"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "test_amazon.py"
    test_file.write_text(textwrap.dedent("""
    import tools.chromeconnect_guard as guard
    guard.enforce("test")
    BASE_URL = "https://www.amazon.com/dp/B08N5WRWNW"
    import playwright.async_api
    """))
    
    result = run_test_file(test_file, PROJECT_ROOT)
    
    assert result.returncode != 0, f"Expected failure, got returncode 0. stderr: {result.stderr}"
    assert "DirectPlaywrightUseRefused" in result.stderr


def test_guard_refuses_cloud_url_even_in_e2e_dir(tmp_path):
    """An e2e test targeting a cloud URL is refused."""
    test_dir = tmp_path / "tests" / "e2e"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "test_cloud.py"
    test_file.write_text(textwrap.dedent("""
    import tools.chromeconnect_guard as guard
    guard.enforce("test")
    BASE_URL = "https://api.openai.com/v1/models"
    import playwright.async_api
    """))
    
    result = run_test_file(test_file, PROJECT_ROOT)
    
    assert result.returncode != 0, f"Expected failure, got returncode 0. stderr: {result.stderr}"
    assert "DirectPlaywrightUseRefused" in result.stderr


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])