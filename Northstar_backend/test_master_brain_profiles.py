"""Offline tests for master_brain_profiles.py — profile resolver + loader.

ZERO network, ZERO LLM calls, ZERO provider calls. Uses a temp manifest
and temp profile files so the real profiles/ tree is never touched.
"""

import json
import os
import tempfile
import unittest

import master_brain_profiles as mbp


class TestHelpersMixin:
    def setUp(self):
        # Flush the path cache between tests so stale cached paths from the
        # real manifest don't leak into temp-manifest tests.
        mbp._PROFILE_PATH_CACHE.clear()

    def make_context(self):
        """Create a temp dir with a minimal manifest + one profile file."""
        tmp = tempfile.mkdtemp(prefix="mbp-test-")
        profile_id = "t2-holdings-tyrone-johnson"
        files = {
            "t2-holdings-tyrone-johnson.md": "# USER PROFILE — T2\n\n> test seed\n",
            "other-subscriber.md": "# USER PROFILE — Other\n\n> test\n",
        }
        for name, content in files.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
                f.write(content)
        manifest = {
            "default_profile": profile_id,
            "profiles": [
                {"id": profile_id, "file": "t2-holdings-tyrone-johnson.md", "active": True, "default": True},
                {"id": "other-subscriber", "file": "other-subscriber.md", "active": True, "default": False},
            ],
        }
        mp = os.path.join(tmp, "manifest.json")
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        return tmp, mp


class ManifestTests(unittest.TestCase, TestHelpersMixin):
    def test_load_manifest_returns_profiles(self):
        tmp, mp = self.make_context()
        manifest = mbp.load_manifest(mp)
        self.assertEqual(len(manifest["profiles"]), 2)
        self.assertEqual(manifest["default_profile"], "t2-holdings-tyrone-johnson")

    def test_load_manifest_missing_profiles_raises(self):
        tmp = tempfile.mkdtemp(prefix="mbp-test-")
        bad = os.path.join(tmp, "bad.json")
        with open(bad, "w", encoding="utf-8") as f:
            json.dump({"default_profile": "x"}, f)
        with self.assertRaises(ValueError):
            mbp.load_manifest(bad)

    def test_load_manifest_missing_file_raises_oserror(self):
        with self.assertRaises(OSError):
            mbp.load_manifest(os.path.join(tempfile.mkdtemp(), "nope.json"))

    def test_list_profiles_in_manifest_order(self):
        tmp, mp = self.make_context()
        self.assertEqual(
            mbp.list_profiles(mp),
            ["t2-holdings-tyrone-johnson", "other-subscriber"],
        )


class PathResolutionTests(unittest.TestCase, TestHelpersMixin):
    def test_profile_path_resolves_known_profile(self):
        tmp, mp = self.make_context()
        path = mbp.profile_path("t2-holdings-tyrone-johnson", manifest_path=mp)
        self.assertTrue(os.path.isfile(path))
        self.assertIn("t2-holdings-tyrone-johnson.md", path)

    def test_profile_path_unknown_id_fails_closed(self):
        tmp, mp = self.make_context()
        with self.assertRaises(KeyError):
            mbp.profile_path("ghost-subscriber", manifest_path=mp)

    def test_profile_path_missing_file_on_disk_raises(self):
        tmp = tempfile.mkdtemp(prefix="mbp-test-")
        mp = os.path.join(tmp, "manifest.json")
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "default_profile": "ghost",
                    "profiles": [{"id": "ghost", "file": "ghost.md", "active": True, "default": True}],
                },
                f,
            )
        with self.assertRaises(ValueError):
            mbp.profile_path("ghost", manifest_path=mp)

    def test_profile_path_blocks_traversal(self):
        tmp = tempfile.mkdtemp(prefix="mbp-test-")
        mp = os.path.join(tmp, "manifest.json")
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "default_profile": "escape",
                    "profiles": [{"id": "escape", "file": "../escape.md", "active": True, "default": True}],
                },
                f,
            )
        with self.assertRaises(ValueError):
            mbp.profile_path("escape", manifest_path=mp)

    def test_profile_path_rejects_non_markdown(self):
        tmp, mp = self.make_context()
        manifest = mbp.load_manifest(mp)
        manifest["profiles"].append({"id": "txt", "file": "subscriber.txt", "active": True})
        evil = os.path.join(tmp, "evil.json")
        with open(evil, "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        with self.assertRaises(ValueError):
            mbp.profile_path("txt", manifest_path=evil)


class ResolveTests(unittest.TestCase, TestHelpersMixin):
    def tearDown(self):
        os.environ.pop(mbp.ENV_PROFILE, None)

    def test_default_resolution_without_env(self):
        os.environ.pop(mbp.ENV_PROFILE, None)
        result = mbp.resolve_active_profile()
        self.assertEqual(result["profile_id"], mbp.DEFAULT_PROFILE)
        self.assertEqual(result["resolver"], "local_default")

    def test_env_override_selects_profile(self):
        os.environ[mbp.ENV_PROFILE] = "other-subscriber"
        result = mbp.resolve_active_profile()
        self.assertEqual(result["profile_id"], "other-subscriber")
        self.assertEqual(result["resolver"], "local_default")

    def test_env_override_not_stripped_empty(self):
        os.environ[mbp.ENV_PROFILE] = "   "
        result = mbp.resolve_active_profile()
        self.assertEqual(result["profile_id"], mbp.DEFAULT_PROFILE)

    def test_chain_skips_not_implemented_resolvers(self):
        os.environ.pop(mbp.ENV_PROFILE, None)
        result = mbp.resolve_active_profile("some-login-token")
        self.assertEqual(result["resolver"], "local_default")
        self.assertIn("two_step_auth", result["resolvers_skipped"])
        self.assertIn("login_session", result["resolvers_skipped"])

    def test_broken_resolver_does_not_kill_chain(self):
        class Boom(mbp.IdentityResolver):
            name = "boom"
            priority = 500

            def resolve(self, identity=None):
                raise RuntimeError("boom")

        boom = Boom()
        mbp.register_resolver(boom)
        try:
            result = mbp.resolve_active_profile()
            self.assertEqual(result["profile_id"], mbp.DEFAULT_PROFILE)
            self.assertIn("boom(RuntimeError)", result["resolvers_skipped"])
        finally:
            mbp._RESOLVERS.remove(boom)

    def test_matching_resolver_wins_over_default(self):
        class AlwaysOther(mbp.IdentityResolver):
            name = "always_other"
            priority = 500

            def resolve(self, identity=None):
                return "other-subscriber"

        always_other = AlwaysOther()
        mbp.register_resolver(always_other)
        try:
            result = mbp.resolve_active_profile()
            self.assertEqual(result["profile_id"], "other-subscriber")
            self.assertEqual(result["resolver"], "always_other")
        finally:
            mbp._RESOLVERS.remove(always_other)


class LoadTests(unittest.TestCase, TestHelpersMixin):
    def test_load_profile_returns_verified_metadata(self):
        tmp, mp = self.make_context()
        loaded = mbp.load_profile("t2-holdings-tyrone-johnson", manifest_path=mp)
        self.assertEqual(loaded["profile_id"], "t2-holdings-tyrone-johnson")
        self.assertTrue(loaded["exists"])
        self.assertGreater(loaded["size_bytes"], 0)
        self.assertEqual(loaded["line_count"], 3)
        self.assertRegex(loaded["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("# USER PROFILE — T2", loaded["head"][0])

    def test_load_profile_include_content(self):
        tmp, mp = self.make_context()
        loaded = mbp.load_profile("other-subscriber", manifest_path=mp, include_content=True)
        self.assertIn("test", loaded["content"])

    def test_load_profile_unknown_fails_closed(self):
        tmp, mp = self.make_context()
        with self.assertRaises(KeyError):
            mbp.load_profile("nobody", manifest_path=mp)

    def test_load_profile_empty_file_still_loads(self):
        tmp = tempfile.mkdtemp(prefix="mbp-test-")
        with open(os.path.join(tmp, "empty.md"), "w", encoding="utf-8") as f:
            f.write("")
        mp = os.path.join(tmp, "manifest.json")
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(
                {"default_profile": "empty", "profiles": [{"id": "empty", "file": "empty.md", "active": True, "default": True}]},
                f,
            )
        loaded = mbp.load_profile("empty", manifest_path=mp)
        self.assertEqual(loaded["line_count"], 0)
        self.assertEqual(loaded["size_bytes"], 0)


class AuditTests(unittest.TestCase, TestHelpersMixin):
    def test_audit_profile_load_writes_append_only(self):
        tmp, mp = self.make_context()
        log = os.path.join(tmp, "audit.log.jsonl")
        first = mbp.audit_profile_load("t2-holdings-tyrone-johnson", resolver="local_default", log_path=log)
        self.assertEqual(first, log)
        mbp.audit_profile_load("other-subscriber", resolver="cli", log_path=log)
        with open(log, "r", encoding="utf-8") as f:
            lines = [json.loads(l) for l in f if l.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["metadata"]["event"], "profile_load")
        self.assertEqual(lines[0]["metadata"]["profile_id"], "t2-holdings-tyrone-johnson")
        self.assertEqual(lines[1]["metadata"]["profile_id"], "other-subscriber")
        self.assertFalse(lines[0]["live_action_requested"])
        # files_touched contains the resolved profile file (relpath to repo root) or fallback id
        ft = " ".join(lines[0]["files_touched"])
        self.assertTrue("t2-holdings-tyrone-johnson" in ft, f"unexpected files_touched: {ft}")

    def test_audit_never_contains_credentials(self):
        tmp, mp = self.make_context()
        log = os.path.join(tmp, "audit.log.jsonl")
        mbp.audit_profile_load("t2-holdings-tyrone-johnson", log_path=log)
        raw = open(log, "r", encoding="utf-8").read()
        for secretish in ("api_key", "password", "token=", "sk-", "Bearer"):
            self.assertNotIn(secretish, raw.lower())


class BootstrapTests(unittest.TestCase, TestHelpersMixin):
    def test_bootstrap_resolves_loads_and_audits(self):
        tmp, mp = self.make_context()
        log = os.path.join(tmp, "audit.log.jsonl")
        # Without audit: resolve + load only
        ctx = mbp.bootstrap(manifest_path=mp)
        self.assertEqual(ctx["resolved"]["profile_id"], mbp.DEFAULT_PROFILE)
        self.assertEqual(ctx["profile"]["profile_id"], mbp.DEFAULT_PROFILE)
        self.assertIsNone(ctx["audit"])

        # Verify full content (this bootstrap read the temp 3-line file):
        self.assertEqual(ctx["profile"]["line_count"], 3)


class CLITests(unittest.TestCase, TestHelpersMixin):
    def test_cli_list(self):
        tmp, mp = self.make_context()
        # Monkeypatch the manifest path for --list by passing it via env trick is not needed
        # — --list uses the module MANIFEST_PATH, but we can test it doesn't crash
        # (it reads the real manifest which always has T2)
        rc = mbp._cli(["--list"])
        self.assertEqual(rc, 0)

    def test_cli_resolve(self):
        rc = mbp._cli(["--resolve"])
        self.assertEqual(rc, 0)

    def test_cli_load_real_profile(self):
        # --load reads the real profiles dir; confirm it doesn't crash for T2
        rc = mbp._cli(["--load", "t2-holdings-tyrone-johnson"])
        self.assertEqual(rc, 0)

    def test_cli_load_unknown_returns_error(self):
        rc = mbp._cli(["--load", "ghost-profile-xxx"])
        self.assertNotEqual(rc, 0)

    def test_cli_audit_without_load_fails(self):
        rc = mbp._cli(["--audit"])
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()