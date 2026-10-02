import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("setup_workspace", Path(__file__).resolve().parents[1] / "setup.py")
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git("init", "-q")
        (self.root / ".gitignore").write_text("**/private/\n", encoding="utf-8")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def test_empty_workspace_is_structurally_valid_without_success_or_authority(self):
        result = setup.initialize(self.root)
        self.assertEqual(len(setup.FILES), len(result["created"]))
        report = setup.check(self.root)
        self.assertTrue(report["ok"])
        self.assertEqual(0, report["history_rows"])
        self.assertIn("not verified", report["scope"])
        self.assertEqual(b"", self.git("ls-files", "--", "private/").stdout)
        preferences = json.loads((self.root / "private/application-profile/preferences.json").read_text())
        self.assertIn("NEEDS_CONFIRMATION", json.dumps(preferences))
        sources = json.loads((self.root / "private/job-search/sources.json").read_text())
        self.assertFalse(any(source.get("enabled", True) for source in sources["sources"]))

    def test_second_run_preserves_user_bytes(self):
        setup.initialize(self.root)
        path = self.root / "private/material-index.md"
        expected = b"User-selected material\r\nKeep this exactly.\r\n"
        path.write_bytes(expected)
        result = setup.initialize(self.root)
        self.assertEqual([], result["created"])
        self.assertEqual(len(setup.FILES), len(result["kept"]))
        self.assertEqual(expected, path.read_bytes())

    def test_dry_run_creates_nothing(self):
        result = setup.initialize(self.root, dry_run=True)
        self.assertEqual(len(setup.FILES), len(result["would_create"]))
        self.assertFalse((self.root / "private").exists())

    def test_fresh_cli_dry_run_does_not_create_import_caches(self):
        for relative in ("tools/workspace/setup.py", "tools/recruiting-sync/sync.py",
                         "tools/application-profile/read.py", "tools/job-radar/radar.py",
                         "tools/job-radar/collect.py"):
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(setup.PACKAGE / relative, destination)
        shutil.copytree(setup.PACKAGE / "templates", self.root / "templates")
        before = {str(path.relative_to(self.root)) for path in self.root.rglob("*")}
        environment = {key: value for key, value in os.environ.items()
                       if key != "PYTHONDONTWRITEBYTECODE"}
        result = subprocess.run([sys.executable, str(self.root / "tools/workspace/setup.py"),
                                 "init", "--dry-run"], capture_output=True, text=True, env=environment)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("INIT_PREVIEW", result.stdout)
        self.assertEqual(before, {str(path.relative_to(self.root)) for path in self.root.rglob("*")})

    def test_unignored_destination_rejected_before_writes(self):
        (self.root / ".gitignore").write_text("", encoding="utf-8")
        with self.assertRaises(setup.sync.SyncError):
            setup.initialize(self.root)
        self.assertFalse((self.root / "private").exists())

    def test_tracked_destination_rejected_before_writes(self):
        path = self.root / "private/job-search/dashboard.md"
        path.parent.mkdir(parents=True)
        path.write_text("Tracked fixture\n", encoding="utf-8")
        self.git("add", "-f", "--", str(path.relative_to(self.root)))
        with self.assertRaises(setup.sync.SyncError):
            setup.initialize(self.root)
        self.assertFalse((self.root / "private/material-index.md").exists())
        self.assertEqual("Tracked fixture\n", path.read_text())

    def test_symlink_destination_and_broken_parent_rejected(self):
        (self.root / "private").symlink_to(self.root / "absent", target_is_directory=True)
        with self.assertRaises(setup.sync.SyncError):
            setup.initialize(self.root)
        self.assertFalse((self.root / "absent").exists())

    def test_file_blocking_later_directory_causes_no_partial_init(self):
        (self.root / "private").mkdir()
        (self.root / "private/job-search").write_text("Keep this file\n", encoding="utf-8")
        with self.assertRaises(setup.sync.SyncError):
            setup.initialize(self.root)
        self.assertFalse((self.root / "private/material-index.md").exists())

    def test_check_lists_missing_without_writes(self):
        report = setup.check(self.root)
        self.assertFalse(report["ok"])
        self.assertEqual(len(setup.FILES), len(report["missing"]))
        self.assertFalse((self.root / "private").exists())

    def test_search_queue_mismatch_detected_without_modifying_records(self):
        setup.initialize(self.root)
        path = self.root / "private/job-search/profile.json"
        data = json.loads(path.read_text())
        data["application_queue"]["path"] = "../recruiting/different-queue.md"
        path.write_text(json.dumps(data), encoding="utf-8")
        before = {p: p.read_bytes() for p in (self.root / "private").rglob("*") if p.is_file()}
        result = setup.check(self.root)
        self.assertFalse(result["ok"])
        self.assertIn("search: path does not match recruiting configuration", result["issues"])
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_module_privacy_checked_without_printing_values(self):
        setup.initialize(self.root)
        module = "private/application-profile/facts.json"
        self.git("add", "-f", "--", module)
        with self.assertRaisesRegex(setup.sync.SyncError, "ignored and untracked"):
            setup.check(self.root)

    def test_symlink_route_is_not_normalized_away(self):
        setup.initialize(self.root)
        directory = self.root / "private/job-search"
        (directory / "redirect").symlink_to(self.root / "private/recruiting", target_is_directory=True)
        path = directory / "profile.json"
        data = json.loads(path.read_text())
        data["application_queue"]["path"] = "redirect/queue.md"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(setup.sync.SyncError, "symlink"):
            setup.check(self.root)

    def test_configured_history_is_preserved_without_recreating_default(self):
        setup.initialize(self.root)
        old = self.root / "private/recruiting/history.md"
        old.rename(old.with_name("applications.md"))
        config_path = self.root / "private/recruiting/config.json"
        config = json.loads(config_path.read_text())
        config["paths"]["history"] = "private/recruiting/applications.md"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        profile_path = self.root / "private/job-search/profile.json"
        profile = json.loads(profile_path.read_text())
        profile["application_queue"]["application_history_path"] = "../recruiting/applications.md"
        profile["current_actions"] = "../job-search/current-actions.md"
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        self.assertTrue(setup.check(self.root)["ok"])
        self.assertEqual([], setup.initialize(self.root)["created"])
        self.assertFalse(old.exists())

    def test_invalid_sources_fail_before_claiming_check_pass(self):
        setup.initialize(self.root)
        path = self.root / "private/job-search/sources.json"
        path.write_text(json.dumps({"sources": [123]}), encoding="utf-8")
        with self.assertRaises(ValueError):
            setup.check(self.root)


if __name__ == "__main__":
    unittest.main()
