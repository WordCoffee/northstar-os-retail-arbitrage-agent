"""Phase 1 tests — offline secret scanner.

All values here are OBVIOUSLY FAKE. No real credential appears in this file.
"""
from __future__ import annotations

import json

from northstar.security.secret_scan import main, scan_paths, scan_text

FAKE_OPENAI = "sk-FAKEFAKEFAKEFAKE123456"
FAKE_GITHUB = "ghp_" + "F" * 40
FAKE_AWS = "AKIA" + "FAKEFAKEFAKE0000"
FAKE_JWT = "eyJFAKEFAKEFAKE.eyJFAKEFAKEFAKE.signatureFAKE"


class TestScanText:
    def test_token_shapes_are_found(self):
        findings = scan_text("fake.py", f"key = '{FAKE_OPENAI}'\n")
        assert findings
        assert findings[0].rule == "openai-style-key"

    def test_github_token_is_found(self):
        findings = scan_text("fake.py", f"clone {FAKE_GITHUB}\n")
        assert any(f.rule == "github-token" for f in findings)

    def test_clean_text_has_no_findings(self):
        assert scan_text("fake.py", "def add(a, b):\n    return a + b\n") == []

    def test_proof_never_contains_full_value(self):
        findings = scan_text("fake.py", f"x {FAKE_GITHUB} y")
        assert findings
        for f in findings:
            assert FAKE_GITHUB not in f.proof
            assert len(f.proof) < 40

    def test_placeholder_assignments_are_skipped(self):
        text = 'jwt_secret = "test-foundation-jwt-secret-not-real"\n'
        assert scan_text("fake.py", text) == []

    def test_credential_assignment_is_found(self):
        findings = scan_text("fake.py", "password=CorrectHorseBatteryStaple99\n")
        assert any(f.rule == "credential-assignment" for f in findings)


class TestPrecisionSkips:
    """Regressions for the false-positive refinements (cross-line + code refs)."""

    def test_cross_line_pairs_are_not_matched(self):
        assert scan_text("fake.py", "if not password:\n    fetch_next()\n") == []

    def test_env_reference_values_are_skipped(self):
        assert scan_text("fake.py", "api_key = os.environ.get('X') or ''\n") == []
        assert scan_text("fake.js", "token: process.env.SOME_TOKEN,\n") == []

    def test_code_reference_values_are_skipped(self):
        assert scan_text("fake.jsx", "password: e.target.value\n") == []
        assert scan_text("fake.py", "secret = build_secret()\n") == []

    def test_constant_reference_values_are_skipped(self):
        assert scan_text("fake.jsx", "password: LOCAL_DEMO_PASSWORD\n") == []

    def test_field_name_as_value_is_skipped(self):
        assert scan_text("fake.html", 'type="password"\n') == []
        assert scan_text("fake.py", 'password = "password"\n') == []

    def test_unquoted_low_entropy_values_are_skipped(self):
        assert scan_text("fake.py", "token: str = None\n") == []
        assert scan_text("fake.js", "token = await page.evaluate(x)\n") == []

    def test_quoted_literal_still_flagged(self):
        findings = scan_text("fake.py", 'api_key = "Zx9Kq2Lm4Vt7"\n')
        assert any(f.rule == "credential-assignment" for f in findings)

    def test_prose_authorization_is_skipped(self):
        assert (
            scan_text("doc.md", "- A passing data run is NOT purchase authorization: for selling.\n")
            == []
        )

    def test_short_quoted_values_are_skipped(self):
        assert scan_text("fake.py", 'password = "a1"\n') == []

    def test_header_code_values_are_skipped(self):
        assert scan_text("fake.py", "Authorization: Bearer {token}\n") == []
        assert scan_text("fake.js", "Authorization: Bearer ${apiKey}\n") == []

    def test_invalid_bearer_placeholder_is_skipped(self):
        assert scan_text("fake.py", "Authorization: Bearer invalid-bearer-value\n") == []

    def test_lockfile_semver_values_are_skipped(self):
        assert scan_text("package-lock.json", '"js-tokens": "^4.0.0"\n') == []

    def test_status_words_are_skipped(self):
        assert scan_text("fake.py", '"SOME_API_KEY": "configured",\n') == []

    def test_quoted_prose_values_are_skipped(self):
        line = '"ERR_OTP_EXPIRED_TOKEN": "Your code has expired. Please try again."\n'
        assert scan_text("fake.html", line) == []

    def test_fetch_credentials_option_is_skipped(self):
        assert scan_text("fake.js", "fetch(url, { credentials: 'include' })\n") == []

    def test_lowercase_word_values_are_skipped(self):
        assert scan_text("fake.py", '"SOME_API_KEY": "cleared",\n') == []
        assert scan_text("api_docs.py", '"password": "string",\n') == []

    def test_unquoted_index_syntax_is_skipped(self):
        # Regression: `token = auth_header[7:]` (index/slice code) was flagged
        # once; brackets must be treated as code markers when UNQUOTED.
        assert scan_text("fake.py", "token = auth_header[7:]\n") == []
        assert scan_text("fake.py", "secret = rows[0]\n") == []

    def test_bracketed_quoted_value_is_still_flagged(self):
        # A quoted literal that merely CONTAINS brackets is still a value.
        findings = scan_text("fake.py", 'password = "Pa[s]sword1"\n')
        assert any(f.rule == "credential-assignment" for f in findings)

    def test_amazon_dib_url_blobs_are_skipped(self):
        line = f"url=https://www.amazon.com/dp/X?dib={FAKE_JWT}&qid=1\n"
        assert scan_text("fake.md", line) == []

    def test_standalone_jwt_is_still_found(self):
        findings = scan_text("fake.py", f"jwt={FAKE_JWT}\n")
        assert any(f.rule == "jwt" for f in findings)

    def test_placeholder_authorization_example_is_skipped(self):
        assert (
            scan_text("README.md", 'curl -H "Authorization: Bearer <YOUR_TOKEN>"\n')
            == []
        )

    def test_opaque_authorization_value_is_kept(self):
        findings = scan_text(
            "fake.py", "Authorization: Bearer QzR3TgG7wXpL2mNv8sK1aB4dE6fH0jU\n"
        )
        assert any(f.rule == "authorization-header" for f in findings)


class TestScanPaths:
    def test_finds_secret_in_file(self, tmp_path):
        target = tmp_path / "creds.txt"
        target.write_text(f"aws {FAKE_AWS}\n", encoding="utf-8")
        findings = scan_paths([tmp_path])
        assert len(findings) == 1
        assert findings[0].rule == "aws-access-key-id"
        assert "creds.txt" in findings[0].path

    def test_skip_dirs_are_respected(self, tmp_path):
        skip = tmp_path / "node_modules"
        skip.mkdir()
        (skip / "leak.txt").write_text(FAKE_OPENAI, encoding="utf-8")
        (tmp_path / "ok.txt").write_text("nothing here", encoding="utf-8")
        assert scan_paths([tmp_path]) == []

    def test_dotenv_files_are_never_scanned_in_walks(self, tmp_path):
        # Owner directive: the scanner must never READ local .env material.
        (tmp_path / ".env").write_text(FAKE_AWS, encoding="utf-8")
        (tmp_path / ".env.local").write_text(FAKE_OPENAI, encoding="utf-8")
        (tmp_path / "prod.env").write_text(FAKE_AWS, encoding="utf-8")
        (tmp_path / "ok.txt").write_text("nothing here", encoding="utf-8")
        assert scan_paths([tmp_path]) == []

    def test_env_example_is_skipped(self, tmp_path):
        (tmp_path / ".env.example").write_text(
            "BRIGHTDATA_API_KEY=your_brightdata_api_key_here\n", encoding="utf-8"
        )
        assert scan_paths([tmp_path]) == []

    def test_binary_files_are_skipped(self, tmp_path):
        (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02" + FAKE_OPENAI.encode())
        assert scan_paths([tmp_path]) == []


class TestCli:
    def test_exit_codes_and_redacted_output(self, tmp_path, capsys):
        (tmp_path / "clean.txt").write_text("nothing to see", encoding="utf-8")
        assert main(["--root", str(tmp_path), "--no-allowlist"]) == 0

        (tmp_path / "bad.txt").write_text(FAKE_AWS, encoding="utf-8")
        assert main(["--root", str(tmp_path), "--no-allowlist"]) == 1
        out = capsys.readouterr().out
        assert FAKE_AWS not in out  # proofs are truncated
        assert "aws-access-key-id" in out


class TestBaseline:
    """Known-active findings stay visible and never fail; NEW findings do."""

    def test_known_active_does_not_fail_and_stays_visible(self, tmp_path, capsys):
        (tmp_path / "leak.txt").write_text(FAKE_AWS, encoding="utf-8")
        findings = scan_paths([tmp_path])
        assert len(findings) == 1
        base = tmp_path / "base.json"
        base.write_text(
            json.dumps(
                {
                    "version": 1,
                    "entries": [
                        {
                            "rule": "aws-access-key-id",
                            "fingerprint": findings[0].fingerprint,
                            "reason": "pending rotation",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        assert main(["--root", str(tmp_path), "--no-allowlist", "--baseline", str(base)]) == 0
        out = capsys.readouterr().out
        assert "KNOWN-ACTIVE" in out
        assert "pending rotation" in out
        assert "0 new finding(s)" in out

    def test_new_finding_beyond_baseline_fails(self, tmp_path, capsys):
        (tmp_path / "leak.txt").write_text(FAKE_AWS, encoding="utf-8")
        base = tmp_path / "base.json"
        base.write_text(json.dumps({"entries": []}), encoding="utf-8")
        assert main(["--root", str(tmp_path), "--no-allowlist", "--baseline", str(base)]) == 1
        out = capsys.readouterr().out
        assert "FINDING" in out

    def test_stale_baseline_entry_is_reported_not_fatal(self, tmp_path, capsys):
        (tmp_path / "clean.txt").write_text("nothing to see", encoding="utf-8")
        base = tmp_path / "base.json"
        base.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "rule": "aws-access-key-id",
                            "fingerprint": "a" * 64,
                            "reason": "already fixed",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        assert main(["--root", str(tmp_path), "--no-allowlist", "--baseline", str(base)]) == 0
        err = capsys.readouterr().err
        assert "STALE-BASELINE" in err


class TestMultiPrefixAndCompoundRules:
    def test_all_github_prefixes_are_found(self):
        # Multi-prefix regression: the 2026-09 leak audit missed `ghp_` (its
        # pattern matched `ghp-`); cover every classic prefix plus fine-grained
        # PATs so the miss cannot recur.
        for prefix in ("ghp", "gho", "ghu", "ghs", "ghr"):
            fake = prefix + "_" + "F" * 40
            findings = scan_text("fake.py", f"x {fake}\n")
            assert any(f.rule == "github-token" for f in findings), prefix
        pat = "github_pat_" + "F" * 40
        assert any(
            f.rule == "github-token" for f in scan_text("fake.py", f"x {pat}\n")
        )

    def test_sk_underscore_style_key_is_found(self):
        fake = "sk_" + "F" * 40
        findings = scan_text("fake.py", f"x {fake} y\n")
        assert any(f.rule == "openai-style-key" for f in findings)

    def test_compound_env_assignment_is_found(self):
        findings = scan_text("fake.env", "SCAVIO_API_KEY=K7q2Wm9Zb4Tt6Yp1\n")
        assert any(f.rule == "credential-assignment" for f in findings)

    def test_guid_value_under_key_name_is_found(self):
        findings = scan_text(
            "fake.env", "SOME_API_KEY=a1b2c3d4-b5c6-d7e8-f9a0-bc1d2e3f4a5b\n"
        )
        assert any(f.rule == "credential-assignment" for f in findings)


class TestAllowlist:
    def test_fingerprint_exact_allowlisting(self, tmp_path, capsys):
        (tmp_path / "leak.txt").write_text(FAKE_AWS, encoding="utf-8")
        findings = scan_paths([tmp_path])
        assert len(findings) == 1
        allow = tmp_path / "allow.json"
        allow.write_text(
            json.dumps(
                {
                    "version": 1,
                    "entries": [
                        {
                            "rule": "aws-access-key-id",
                            "fingerprint": findings[0].fingerprint,
                            "reason": "unit test ok",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        assert main(["--root", str(tmp_path), "--allowlist", str(allow)]) == 0
        out = capsys.readouterr().out
        assert "ALLOWED" in out
        assert "unit test ok" in out

    def test_fingerprint_mismatch_still_fails(self, tmp_path, capsys):
        (tmp_path / "leak.txt").write_text(FAKE_AWS, encoding="utf-8")
        allow = tmp_path / "allow.json"
        allow.write_text(
            json.dumps(
                {
                    "version": 1,
                    "entries": [
                        {
                            "rule": "aws-access-key-id",
                            "fingerprint": "0" * 64,
                            "reason": "nope",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        assert main(["--root", str(tmp_path), "--allowlist", str(allow)]) == 1

    def test_malformed_allowlist_is_ignored(self, tmp_path, capsys):
        (tmp_path / "leak.txt").write_text(FAKE_AWS, encoding="utf-8")
        allow = tmp_path / "allow.json"
        allow.write_text("{not json", encoding="utf-8")
        assert main(["--root", str(tmp_path), "--allowlist", str(allow)]) == 1
        err = capsys.readouterr().err
        assert "allowlist" in err.lower()
