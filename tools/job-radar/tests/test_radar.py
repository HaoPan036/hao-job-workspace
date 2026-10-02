"""Fictional-only, offline regression checks for the migrated boundaries."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, replace
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOL = Path(__file__).resolve().parents[1]
ROOT = TOOL.parents[1]
TEMPLATES = ROOT / "templates" / "job-search"
SPEC = importlib.util.spec_from_file_location("public_radar", TOOL / "radar.py")
radar = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = radar
SPEC.loader.exec_module(radar)


class RadarTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fictional-radar-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.queue = self.root / "queue.md"
        self.history = self.root / "application-history.md"
        self.queue.write_bytes(("Personal manual text\r\n" + radar.AUTO_QUEUE_START + "\r\n"
                                + radar.AUTO_QUEUE_END + "\r\nKeep this unchanged.\r\n").encode())
        self.history.write_text("# Fictional history\n", encoding="utf-8")
        self.rows = radar.load_dossiers(TEMPLATES / "dossiers.example.json")
        self.config = {"enabled": True, "max_new_per_run": 8,
                       "path": "queue.md", "application_history_path": "application-history.md"}

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = radar.main(list(args))
        return code, output.getvalue(), errors.getvalue()

    def write_inputs(self, profile_name="canada-full-time.profile.example.json"):
        profile = json.loads((TEMPLATES / profile_name).read_text())
        profile["application_queue"] = self.config.copy()
        path = self.root / "profile.json"
        path.write_text(json.dumps(profile), encoding="utf-8")
        candidates = self.root / "dossiers.json"
        candidates.write_text(json.dumps([asdict(row) for row in self.rows]), encoding="utf-8")
        return path, candidates

    def test_two_fictional_users_support_singapore_internship_and_canada(self):
        student, developer = self.rows
        self.assertEqual(student.job_identity.employment_type, "Internship")
        self.assertEqual(student.job_identity.location, "Singapore")
        self.assertFalse(radar.is_auto_queue_eligible(student))
        self.assertTrue(radar.is_auto_queue_eligible(developer))
        # Resolving the student's real missing condition enables the internship;
        # neither region nor seniority is a hidden global exclusion.
        confirmed = replace(student,
            feasibility=radar.FeasibilityAssessment("PASS", ("Fictional authorization confirmed",)),
            recommendation=radar.Recommendation("APPLY_BATCH", ("Fictional student eligible",)))
        self.assertTrue(radar.is_auto_queue_eligible(confirmed))
        self.assertEqual(radar.update_application_queue(self.queue, self.history,
            [confirmed, developer], self.config, mode="workspace_discovery", write_queue=True), 2)

    def test_review_leaves_every_byte_unchanged_for_both_users_even_when_suggesting_save(self):
        for profile_name in ("singapore-internship.profile.example.json", "canada-full-time.profile.example.json"):
            with self.subTest(profile=profile_name):
                profile, candidates = self.write_inputs(profile_name)
                data = json.loads(candidates.read_text())
                data[0]["recommendation"]["rationale"].append("Save this to the queue now")
                candidates.write_text(json.dumps(data), encoding="utf-8")
                before = {path.name: path.read_bytes() for path in self.root.iterdir()}
                code, output, error = self.run_cli("--profile", str(profile), "--candidates", str(candidates))
                after = {path.name: path.read_bytes() for path in self.root.iterdir()}
                self.assertEqual((code, error), (0, ""))
                self.assertEqual(before, after)
                self.assertEqual(json.loads(output)["queue_added"], 0)
                self.assertFalse(json.loads(output)["writes_enabled"])

    def test_mode_alone_does_not_enable_writes(self):
        profile, candidates = self.write_inputs()
        before = self.queue.read_bytes()
        code, output, _ = self.run_cli("--profile", str(profile), "--candidates", str(candidates),
                                     "--mode", "workspace_discovery")
        self.assertEqual(code, 0)
        self.assertEqual(before, self.queue.read_bytes())
        self.assertFalse(json.loads(output)["writes_enabled"])

    def test_standalone_review_rejects_write_flag_before_any_write(self):
        profile, candidates = self.write_inputs()
        before = self.queue.read_bytes()
        code, _, errors = self.run_cli("--profile", str(profile), "--candidates", str(candidates), "--write-queue")
        self.assertEqual(code, 2)
        self.assertIn("requires --mode workspace_discovery", errors)
        self.assertEqual(before, self.queue.read_bytes())

    def test_queue_guard_cannot_be_bypassed_with_apply_action(self):
        good = self.rows[1]
        invalid = [
            replace(good, verification=radar.JobVerification("PENDING", ("Unverified",), "2026-10-01")),
            replace(good, feasibility=radar.FeasibilityAssessment("UNKNOWN")),
            replace(good, feasibility=radar.FeasibilityAssessment("PASS", (), ("Unresolved visa",))),
            replace(good, capability_match=radar.CapabilityMatch()),
            replace(good, strategic_priority=radar.StrategicPriority("LOW")),
            replace(good, job_identity=replace(good.job_identity, status="CLOSED")),
            replace(good, job_identity=replace(good.job_identity, official_url="javascript:alert(1)")),
            replace(good, verification=radar.JobVerification("VERIFIED")),
        ]
        for row in invalid:
            self.assertFalse(radar.is_auto_queue_eligible(row))
        self.assertEqual(radar.update_application_queue(self.queue, self.history, invalid,
            self.config, mode="workspace_discovery", write_queue=True), 0)

    def test_decision_dimensions_are_independent(self):
        self.assertEqual(radar.recommend_action("VERIFIED", "HARD_FAIL", "HIGH", "HIGH"), "SKIP")
        self.assertEqual(radar.recommend_action("VERIFIED", "SOFT_RISK", "HIGH", "HIGH"), "MANUAL_REVIEW")
        self.assertEqual(radar.recommend_action("VERIFIED", "PASS", "LOW", "HIGH"), "WATCHLIST")
        self.assertEqual(radar.recommend_action("VERIFIED", "PASS", "MEDIUM", "HIGH"), "APPLY_BATCH")

    def test_url_dedup_preserves_ids_and_distinct_requisitions(self):
        first = self.rows[1]
        duplicate = replace(first, job_identity=replace(first.job_identity,
            official_url=first.job_identity.official_url + "?utm_source=fictional"))
        distinct = replace(first, job_identity=replace(first.job_identity,
            job_id="FICT-CA-203", official_url="https://maple.example/jobs/FICT-CA-203"))
        self.assertEqual(radar.deduplicate_dossiers([first, duplicate, distinct]), [first, distinct])
        self.assertNotEqual(radar.normalize_url("https://jobs.example/?jobId=1"),
                            radar.normalize_url("https://jobs.example/?jobId=2"))

    def test_queue_write_preserves_crlf_outside_markers_and_is_idempotent(self):
        before = self.queue.read_bytes()
        history_before = self.history.read_bytes()
        self.assertEqual(radar.update_application_queue(self.queue, self.history, self.rows,
            self.config, mode="workspace_discovery", write_queue=True), 1)
        after = self.queue.read_bytes()
        start = radar.AUTO_QUEUE_START.encode()
        end = radar.AUTO_QUEUE_END.encode()
        self.assertEqual(before.split(start)[0], after.split(start)[0])
        self.assertEqual(before.split(end)[1], after.split(end)[1])
        self.assertNotIn(b"\n", after.replace(b"\r\n", b""))
        self.assertEqual(history_before, self.history.read_bytes())
        self.assertEqual(radar.update_application_queue(self.queue, self.history, self.rows,
            self.config, mode="workspace_discovery", write_queue=True), 0)
        self.assertEqual(after, self.queue.read_bytes())

    def test_encoded_parentheses_unicode_and_spaces_do_not_requeue(self):
        original = self.queue.read_bytes()
        for url in (
            "https://maple.example/jobs/Engineer_(Platform)",
            "https://maple.example/jobs/数据工程师",
            "https://maple.example/jobs/Backend Engineer",
            "https://maple.example/jobs/role?jobId=平台 (Backend)&view=详情",
        ):
            with self.subTest(url=url):
                self.queue.write_bytes(original)
                row = replace(self.rows[1], job_identity=replace(self.rows[1].job_identity, official_url=url))
                results = [radar.update_application_queue(self.queue, self.history, [row], self.config,
                    mode="workspace_discovery", write_queue=True) for _ in range(2)]
                self.assertEqual(results, [1, 0])
                self.assertEqual(self.queue.read_text().count("- [ ]"), 1)

    def test_history_links_match_encoded_or_literal_url_spelling(self):
        original = self.queue.read_bytes()
        for url in (
            "https://maple.example/jobs/Engineer_(Platform)",
            "https://maple.example/jobs/数据工程师",
            "https://maple.example/jobs/Backend Engineer",
            "https://maple.example/jobs/role?jobId=平台 (Backend)&view=详情",
        ):
            with self.subTest(url=url):
                row = replace(self.rows[1], job_identity=replace(self.rows[1].job_identity, official_url=url))
                # Both the tool's encoded link and valid angle-bracket Markdown
                # history links identify the same posting as the raw dossier.
                for history in (radar.format_queue_task(row), f"[Submitted](<{url}>)"):
                    self.history.write_text(history)
                    added = radar.update_application_queue(self.queue, self.history, [row], self.config,
                        mode="workspace_discovery", write_queue=True)
                    self.assertEqual(added, 0)
                    self.assertEqual(self.queue.read_bytes(), original)
        self.history.write_text("[Submitted](https://maple.example/jobs/Engineer_(Platform))")
        row = replace(self.rows[1], job_identity=replace(self.rows[1].job_identity,
            official_url="https://maple.example/jobs/Engineer_%28Platform%29"))
        self.assertEqual(radar.update_application_queue(self.queue, self.history, [row], self.config,
            mode="workspace_discovery", write_queue=True), 0)

    def test_reserved_encoding_and_query_semantics_keep_distinct_ids(self):
        for first, second in (
            ("jobs/A%2FB", "jobs/A/B"),
            ("jobs/A%3FB", "jobs/A?B"),
            ("jobs/A%23B", "jobs/A#B"),
            ("jobs/A%252FB", "jobs/A%2FB"),
            ("jobs/?jobId=A%2FB", "jobs/?jobId=A/B"),
            ("jobs/?jobId=A%3FB", "jobs/?jobId=A?B"),
            ("jobs/?jobId=A%26B", "jobs/?jobId=A&B"),
            ("jobs/?jobId=A+B", "jobs/?jobId=A%20B"),
            ("jobs/?jobId=1&jobId=2", "jobs/?jobId=2&jobId=1"),
        ):
            with self.subTest(first=first, second=second):
                self.assertNotEqual(radar.normalize_url("https://maple.example/" + first),
                                    radar.normalize_url("https://maple.example/" + second))
        self.assertEqual(radar.normalize_url("https://maple.example/jobs/%45ngineer_%28Platform%29"),
                         radar.normalize_url("https://maple.example/jobs/Engineer_(Platform)"))
        self.assertEqual(radar.normalize_url("https://maple.example/jobs/%e6%95%b0%e6%8d%ae"),
                         radar.normalize_url("https://maple.example/jobs/数据"))

    def test_history_link_dedup_and_missing_history_fail_closed(self):
        self.history.write_text(f"[Fictional submitted role]({self.rows[1].job_identity.official_url}?utm_source=test)\n")
        before = self.queue.read_bytes()
        self.assertEqual(radar.update_application_queue(self.queue, self.history, self.rows,
            self.config, mode="workspace_discovery", write_queue=True), 0)
        self.history.unlink()
        with self.assertRaises(FileNotFoundError):
            radar.update_application_queue(self.queue, self.history, self.rows,
                self.config, mode="workspace_discovery", write_queue=True)
        self.assertEqual(before, self.queue.read_bytes())

    def test_markers_and_shared_history_path_are_validated(self):
        for text in ("No marker", radar.AUTO_QUEUE_END + radar.AUTO_QUEUE_START,
                     radar.AUTO_QUEUE_START * 2 + radar.AUTO_QUEUE_END):
            self.queue.write_text(text)
            with self.assertRaises(ValueError):
                radar.preflight_application_queue(self.queue, self.history)
            self.assertEqual(self.queue.read_text(), text)
        with self.assertRaises(ValueError):
            radar.preflight_application_queue(self.queue, self.queue)

    def test_relative_paths_resolve_from_profile_not_current_directory(self):
        profile, candidates = self.write_inputs()
        self.assertEqual(radar.resolve_profile_path(profile, "queue.md"), self.queue.resolve())
        code, output, error = self.run_cli("--profile", str(profile), "--candidates", str(candidates),
                                         "--mode", "workspace_discovery", "--write-queue")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output)["queue_added"], 1)

    @unittest.skipUnless(shutil.which("git"), "Git is required for tracked runtime checks")
    def test_git_runtime_paths_must_be_ignored_and_untracked(self):
        def git(*args):
            return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, check=True)
        git("init", "--quiet")
        with self.assertRaises(ValueError):
            radar.require_local_runtime_path(self.queue)
        (self.root / ".gitignore").write_text("queue.md\napplication-history.md\n")
        radar.require_local_runtime_path(self.queue)
        git("add", "-f", "queue.md")
        with self.assertRaises(ValueError):
            radar.require_local_runtime_path(self.queue)
        before = self.queue.read_bytes()
        with self.assertRaises(ValueError):
            radar.update_application_queue(self.queue, self.history, self.rows,
                self.config, mode="workspace_discovery", write_queue=True)
        self.assertEqual(before, self.queue.read_bytes())

    def make_sync(self):
        manifest = {
            "mode": "workspace_discovery", "requested_writeback": "sync_verified_candidates",
            "batch_date": "2026-10-01", "companies": ["Fictional Company"],
            "evaluated_candidates": [
                {"job_id": "FICT-100", "disposition": "queued"},
                {"job_id": "FICT-200", "disposition": "manual_review"},
                {"job_id": "FICT-300", "disposition": "excluded"},
                {"job_id": "FICT-400", "disposition": "duplicate"}],
            "stale_markers": ["Still need to search Fictional Company"]}
        handoff = self.root / "handoff.json"
        handoff.write_text(json.dumps(manifest))
        self.queue.write_text("### 2026-10-01: Fictional batch\n\n"
            "4 evaluated = 1 queued + 1 manual review + 1 excluded + 1 duplicate\n"
            "queued FICT-100\nmanual_review FICT-200\nexcluded FICT-300\n")
        self.history.write_text("Fictional confirmed application FICT-400\n")
        coverage = self.root / "company-coverage.md"
        coverage.write_text("Fictional Company: checked, no remaining company search action\n")
        actions = self.root / "current-actions.md"
        actions.write_text("Next action: review the fictional candidate\n")
        dashboard = self.root / "dashboard.md"
        dashboard.write_text("Current actions linked\n")
        return manifest, (handoff, self.queue, self.history, coverage, actions, dashboard)

    def test_sync_all_four_dispositions_and_all_inputs_unchanged(self):
        _, paths = self.make_sync()
        before = {path: path.read_bytes() for path in paths}
        result = radar.validate_recruiting_sync(*paths)
        self.assertTrue(result.passed, result.errors)
        self.assertEqual(result.orphan_count, 0)
        self.assertEqual(result.evaluated_count, 4)
        self.assertEqual(before, {path: path.read_bytes() for path in paths})

    def test_sync_rejects_orphan_duplicate_disposition_and_queue_history_conflict(self):
        manifest, paths = self.make_sync()
        manifest["evaluated_candidates"].extend([
            {"job_id": "FICT-999", "disposition": "queued"},
            {"job_id": "FICT-100", "disposition": "excluded"}])
        paths[0].write_text(json.dumps(manifest))
        self.history.write_text("FICT-400\nFICT-100\n")
        result = radar.validate_recruiting_sync(*paths)
        self.assertFalse(result.passed)
        self.assertEqual(result.orphan_count, 1)
        self.assertTrue(any("multiple dispositions" in error for error in result.errors))
        self.assertTrue(any("both queue and application history" in error for error in result.errors))

    def test_sync_rejects_wrong_counts_missing_company_and_stale_action(self):
        _, paths = self.make_sync()
        self.queue.write_text(self.queue.read_text().replace("1 queued", "2 queued"))
        paths[3].write_text("Unrelated fictional company\n")
        paths[4].write_text("Still need to search Fictional Company\n")
        result = radar.validate_recruiting_sync(*paths)
        self.assertFalse(result.passed)
        self.assertTrue(any("disposition mismatch" in error for error in result.errors))
        self.assertTrue(any("coverage is missing" in error for error in result.errors))
        self.assertTrue(any("stale marker" in error for error in result.errors))

    def test_invalid_dossier_types_fail_before_writes(self):
        profile, candidates = self.write_inputs()
        data = json.loads(candidates.read_text())
        data[1]["verification"]["reasons"] = "This must be a list"
        candidates.write_text(json.dumps(data))
        before = self.queue.read_bytes()
        code, _, errors = self.run_cli("--profile", str(profile), "--candidates", str(candidates),
                                      "--mode", "workspace_discovery", "--write-queue")
        self.assertEqual(code, 2)
        self.assertIn("must be a string list", errors)
        self.assertEqual(before, self.queue.read_bytes())

    def test_no_network_apis_are_used(self):
        profile, candidates = self.write_inputs()
        with patch("socket.create_connection", side_effect=AssertionError("Network is forbidden")):
            code, _, _ = self.run_cli("--profile", str(profile), "--candidates", str(candidates))
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
