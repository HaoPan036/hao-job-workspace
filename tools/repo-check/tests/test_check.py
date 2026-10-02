import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("package_check", PACKAGE / "tools/repo-check/check.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class PackageChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="career-check-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("-c", "init.templateDir=", "init", "--quiet")
        self.put(".gitignore", (PACKAGE / ".gitignore").read_text())
        self.put("README.md", "# Fictional package\n")
        self.git("add", ".gitignore", "README.md")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def put(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def findings(self, staged=False):
        check = checker.Checker(self.root, staged)
        check.run()
        return {finding[3] for finding in check.findings if finding[0] == "error"}

    def test_clean_package_and_nested_ignores(self):
        self.assertEqual(self.findings(), set())
        paths = ["private/README.md", "a/private/b.txt", ".obsidian/workspace.json",
                 "a/.obsidian/plugins/tool/data.json", ".obsidian/snippets/unreviewed.css"]
        for path in paths:
            with self.subTest(path=path):
                self.git("check-ignore", "--no-index", path)
        result = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--no-index",
                                 ".obsidian/snippets/hao-job-workspace.css"], capture_output=True)
        self.assertEqual(result.returncode, 1)

    def test_links_in_arbitrary_public_folder_are_checked(self):
        self.put("guides/new.md", "[Missing](absent.md)\n")
        self.assertIn("local-link-missing", self.findings())

    def test_markdown_suffix_variants_are_checked(self):
        for name in ["guide.MD", "guide.markdown"]:
            with self.subTest(name=name):
                self.put(name, "[Missing](absent.md)\n")
                check = checker.Checker(self.root)
                check.run()
                self.assertTrue(any(f[1] == name and f[3] == "local-link-missing" for f in check.findings))

    def test_placeholder_does_not_hide_later_credential_on_same_line(self):
        content = json.dumps({"pass" + "word": "PLACEHOLDER", "api" + "_key": "synthetic" + "credentialvalue"})
        self.put("settings.json", content)
        self.assertIn("credential-assignment", self.findings())

    def test_links_cannot_depend_on_parent_repository(self):
        self.put("README.md", "[Private parent](../outside.md)\n")
        self.assertIn("link-outside-package", self.findings())

    def test_force_added_private_file_is_rejected_without_read(self):
        self.put("nested/private/real.txt", "contents must not be read\n")
        self.git("add", "-f", "nested/private/real.txt")
        check = checker.Checker(self.root, True)
        self.assertIsNone(check.read("nested/private/real.txt"))
        self.assertIn("private-path-in-package", self.findings(True))

    def test_tokens_are_checked_in_tracked_unchanged_files(self):
        self.put("notes.md", "sk-" + "x" * 30 + "\n")
        self.git("add", "notes.md")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "fixture")
        self.assertIn("secret-token", self.findings(True))

    def test_staged_view_does_not_scan_unstaged_replacement(self):
        self.put("README.md", "sk-" + "y" * 30 + "\n")
        self.assertNotIn("secret-token", self.findings(True))
        self.assertIn("secret-token", self.findings(False))

    def test_example_does_not_exempt_credentials(self):
        self.put("examples/sample.md", "sk-" + "z" * 30 + "\n")
        self.assertIn("secret-token", self.findings())

    def test_missing_nested_ignore_is_detected(self):
        self.put(".gitignore", "/private/\n")
        self.assertIn("privacy-ignore-missing:nested/private/probe.txt", self.findings())


if __name__ == "__main__":
    unittest.main()
