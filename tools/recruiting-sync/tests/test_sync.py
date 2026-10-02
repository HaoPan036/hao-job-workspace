"""Only temporary repositories, fictional users, and reserved example domains."""

import copy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "sync.py"
TEMPLATES = SCRIPT.parents[2] / "templates" / "recruiting"
SPEC = importlib.util.spec_from_file_location("recruiting_sync", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("private/\n")
        (self.root / "private/recruiting").mkdir(parents=True)
        for source, destination in (("config.example.json", "config.json"), ("history.md", "history.md"), ("queue.md", "queue.md")):
            (self.root / "private/recruiting" / destination).write_bytes((TEMPLATES / source).read_bytes())
        self.config_path = sync.DEFAULT_CONFIG
        self.config_data = json.loads((self.root / self.config_path).read_text())
        self.config = sync.load_config(self.root)
        self.history, self.queue = self.config.files
        self.event = json.loads((TEMPLATES / "event-singapore-internship.example.json").read_text())
        self.input = "private/recruiting/event.json"
        self.serial = 0
        self.write_queue(self.task())

    def save_config(self):
        (self.root / self.config_path).write_text(json.dumps(self.config_data) + "\n")
        self.config = sync.load_config(self.root, self.config_path)
        self.history, self.queue = self.config.files

    def task(self, company="Fictional Aurora Labs", role="Software Engineering Intern", job_id="DEMO-SG-001"):
        return f"- [ ] #p1 **{company}｜{role}** · [Official job](https://careers.example.com/jobs/{job_id})\n  - Verified fictional task detail.\n"

    def row(self, company="Fictional Aurora Labs", role="Software Engineering Intern", job_id="DEMO-SG-001", nature="Singapore / Internship", note=None, submitted="Not recorded"):
        return f"| 2026-10-01 | {submitted} | {company} | {role} | {nature} | Submitted | [Official job](https://careers.example.com/jobs/{job_id}) | {note or ('Job ID ' + job_id + '; Fictional row.')} |\n"

    def write_queue(self, tasks="", tail=""):
        (self.root / self.queue).write_text("# Queue\n\n" + self.config.markdown["queue_heading"] + "\n\n" + tasks + "\n" + tail + "\n## Excluded\n\nKeep excluded DEMO-SG-001 reference.\n")

    def write_history(self, rows="", counts=None, targets=None):
        counts = dict.fromkeys(self.config.categories, 0) | (counts or {})
        targets = dict.fromkeys(self.config.categories, "—") | (targets or {})
        lines = ["---", "updated: 2026-10-01", "---", "", "# Applications", "", self.config.markdown["counts_heading"], "", "| " + " | ".join(self.config.markdown["count_headers"]) + " |", "|---|---:|---:|---:|"]
        for category in self.config.categories:
            target = targets[category]
            remaining = int(target) - counts[category] if str(target).isdigit() else "—"
            lines.append(f"| {category} | {counts[category]} | {target} | {remaining} |")
        for total, members in ((self.config.totals[0], self.config.full_time_categories), (self.config.totals[1], self.config.categories)):
            count = sum(counts[key] for key in members)
            target = sum(int(targets[key]) for key in members) if all(str(targets[key]).isdigit() for key in members) else "—"
            remaining = target - count if isinstance(target, int) else "—"
            lines.append(f"| {total} | {count} | {target} | {remaining} |")
        lines += ["", self.config.markdown["history_heading"], "", "| " + " | ".join(self.config.markdown["history_headers"]) + " |", "|---|---|---|---|---|---|---|---|"]
        (self.root / self.history).write_text("\n".join(lines) + "\n" + rows + "\n## Notes\n\nPreserve this explanation.\n")

    def plan(self, mode="strict"):
        self.serial += 1
        (self.root / self.input).write_text(json.dumps(self.event))
        out = f"private/recruiting/plan-{self.serial}"
        result = sync.create_plan(self.root, self.input, out, mode, self.config_path)
        return result, self.root / out / "plan.json"

    def check(self, path, verify=False):
        return sync.check_plan(self.root, path, verify, self.config_path)

    def audit(self):
        return sync.audit(self.root, self.config_path)

    def snapshot(self):
        return {name: (self.root / name).read_bytes() for name in self.config.files}

    def apply(self, plan_path, only=None):
        """Interpret generated apply_patch hunks against fictional fixtures."""
        patch = (plan_path.parent / "changes.patch").read_text().splitlines(keepends=True)
        self.assertEqual(patch[0], "*** Begin Patch\n")
        self.assertEqual(patch[-1], "*** End Patch\n")
        index = 1
        while index < len(patch) - 1:
            self.assertTrue(patch[index].startswith("*** Update File: "))
            name = patch[index].removeprefix("*** Update File: ").strip()
            self.assertIn(name, self.config.files)
            index += 1
            contents = (self.root / name).read_text().splitlines(keepends=True)
            while index < len(patch) and patch[index] == "@@\n":
                index += 1
                old, new = [], []
                while index < len(patch) and not patch[index].startswith(("@@", "***")):
                    line = patch[index]
                    self.assertIn(line[0], " +-")
                    if line[0] in " -":
                        old.append(line[1:])
                    if line[0] in " +":
                        new.append(line[1:])
                    index += 1
                places = [i for i in range(len(contents) - len(old) + 1) if contents[i:i + len(old)] == old]
                self.assertEqual(len(places), 1, "Patch context must identify one exact fixture location")
                position = places[0]
                contents[position:position + len(old)] = new
            if only is None or only == name:
                (self.root / name).write_text("".join(contents))

    def test_singapore_internship_plan_is_read_only_then_verified(self):
        self.write_history()
        before = self.snapshot()
        result, path = self.plan()
        self.assertEqual(before, self.snapshot())
        self.assertIn({"path": self.history, "line": 2}, result["review_locations"])
        self.assertEqual(result["counts"], {"Singapore / Full time": 0, "Singapore / Internship": 1, "Canada / Full time": 0, "Canada / Internship": 0})
        self.check(path)
        self.apply(path)
        self.check(path, True)
        self.assertEqual(self.audit()["issues"], [])
        history = (self.root / self.history).read_text()
        self.assertIn("| 2026-10-01 | Not recorded | Fictional Aurora Labs", history)
        self.assertIn("| All full time | 0 |", history)
        self.assertIn("| All submitted | 1 |", history)
        self.assertIn("Keep excluded", (self.root / self.queue).read_text())

    def test_second_fictional_user_canada_full_time_with_custom_headers_paths(self):
        self.event = json.loads((TEMPLATES / "event-canada-full-time.example.json").read_text())
        self.config_data["regions"] = {"canada": self.config_data["regions"]["canada"]}
        self.config_data["paths"] = {"history": "private/recruiting/user-b-history.md", "queue": "private/recruiting/user-b-queue.md"}
        self.config_data["markdown"].update(history_heading="## 已投递", queue_heading="## 待投递", counts_heading="## 统计", history_headers=["确认日期", "实际投递日期", "公司", "岗位", "地区 / 性质", "当前状态", "岗位链接", "备注"], count_headers=["类型", "已投", "目标", "剩余"], employment_labels={"full_time": "全职", "internship": "实习"}, total_labels={"full_time": "全职合计", "all": "全部已投"}, unknown_date="未记录")
        self.save_config()
        self.write_history()
        self.write_queue(self.task("Fictional Boreal Systems", "Software Engineer", "DEMO-CA-002"))
        result, path = self.plan()
        self.apply(path)
        self.check(path, True)
        self.assertEqual(result["counts"], {"Canada / 全职": 1, "Canada / 实习": 0})
        self.assertIn("| Toronto / 全职 |", (self.root / self.history).read_text())
        self.assertIn("| 未记录 |", (self.root / self.history).read_text())
        self.assertEqual(self.audit()["history_rows"], 1)

    def test_repeated_event_does_not_duplicate_or_require_material_archive(self):
        self.event["sync"]["material_record_id"] = "fictional-not-archived"
        _, path = self.plan()
        self.apply(path)
        self.check(path, True)
        before = self.snapshot()
        result, repeated = self.plan()
        self.apply(repeated)
        self.check(repeated, True)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.audit()["history_rows"], 1)
        self.assertEqual(result["counts"]["Singapore / Internship"], 1)
        self.assertFalse((self.root / "private/application-records").exists())

    def test_radar_generated_task_uses_same_queue_and_preserves_markers(self):
        self.radar_sync_roundtrip()

    def test_radar_escaped_identity_roundtrip_does_not_leave_pending_or_recount(self):
        cases = (
            ("Fictional [Maple] Systems", "[Backend] Engineer", False),
            ("Fictional [Maple] Systems | Tools", r"Backend \ API *Engineer* <Team>", False),
            ("Fictional Systems " + "\\", "Backend Engineer", True),
        )
        for company, role, ascii_separator in cases:
            with self.subTest(company=company, role=role, ascii_separator=ascii_separator):
                self.write_history()
                self.radar_sync_roundtrip(company, role, ascii_separator)

    def test_radar_url_only_unicode_roundtrip_keeps_reserved_distinctions(self):
        self.radar_sync_roundtrip(official_url="https://maple.example/jobs/工程師(Cloud)?team=研發&view=a%2Fb#職缺")
        for left, right in (
            ("https://example.com/a%2Fb", "https://example.com/a/b"),
            ("https://example.com/?q=a%26b", "https://example.com/?q=a&b"),
            ("https://example.com/?q=a%2Bb", "https://example.com/?q=a+b"),
            ("https://example.com/?q=a+b", "https://example.com/?q=a%20b"),
        ):
            self.assertNotEqual(sync.canonical_url(left), sync.canonical_url(right))

    def radar_sync_roundtrip(self, company=None, role=None, ascii_separator=False, official_url=None):
        radar_script = SCRIPT.parent.parent / "job-radar" / "radar.py"
        spec = importlib.util.spec_from_file_location("job_radar_sync_contract", radar_script)
        radar = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = radar
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(radar)
        row = radar.load_dossiers(TEMPLATES.parent / "job-search" / "dossiers.example.json")[1]
        if company is not None:
            row = replace(row, job_identity=replace(row.job_identity, company=company, title=role))
        if official_url is not None:
            row = replace(row, job_identity=replace(row.job_identity, job_id="", official_url=official_url))
        queue_path, history_path = self.root / self.queue, self.root / self.history
        queue_path.write_bytes((TEMPLATES / "queue.md").read_bytes())
        history_before = history_path.read_bytes()
        added = radar.update_application_queue(queue_path, history_path, [row], {"enabled": True}, mode="workspace_discovery", write_queue=True)
        self.assertEqual(added, 1)
        self.assertEqual(history_before, history_path.read_bytes())
        self.assertIn(radar.format_queue_task(row), queue_path.read_text())
        if ascii_separator:
            queue_path.write_text(queue_path.read_text().replace("｜", "|", 1))
        identity = row.job_identity
        entries = sync.queue_entries(queue_path.read_text(), self.config)
        self.assertEqual(entries[0]["company"], identity.company)
        self.assertEqual(entries[0]["role"], identity.title)
        self.event = json.loads((TEMPLATES / "event-canada-full-time.example.json").read_text())
        self.event["application_execution"]["target"].update(company=identity.company, role=identity.title, job_id=identity.job_id or None, official_url=identity.official_url)
        self.event["sync"]["location"] = identity.location
        result, path = self.plan()
        self.check(path)
        self.apply(path)
        self.check(path, True)
        pending = queue_path.read_text()
        self.assertEqual(pending.count(radar.AUTO_QUEUE_START), 1)
        self.assertEqual(pending.count(radar.AUTO_QUEUE_END), 1)
        self.assertLess(pending.index(radar.AUTO_QUEUE_START), pending.index(radar.AUTO_QUEUE_END))
        for heading in ("## Manual review", "## Excluded", "## Duplicate pointers", "## Discovery batches"):
            self.assertIn(heading, pending)
        self.assertNotIn(identity.official_url, pending)
        self.assertNotIn("  - Fit:", pending)
        self.assertEqual(result["counts"]["Canada / Full time"], 1)
        self.assertEqual(radar.update_application_queue(queue_path, history_path, [row], {"enabled": True}, mode="workspace_discovery", write_queue=True), 0)
        _, repeated = self.plan()
        self.check(repeated, True)
        self.assertEqual(self.audit()["history_rows"], 1)

    def test_partial_sync_failure_recovers_only_remaining_queue(self):
        _, path = self.plan()
        self.apply(path, only=self.history)
        with self.assertRaisesRegex(sync.SyncError, "post-apply mismatch"):
            self.check(path, True)
        result, recovery = self.plan()
        self.assertEqual(result["files"][0]["before_sha256"], result["files"][0]["after_sha256"])
        self.apply(recovery)
        self.check(recovery, True)
        self.assertEqual(self.audit()["history_rows"], 1)
        self.assertEqual(result["counts"]["Singapore / Internship"], 1)

    def test_history_row_without_count_update_recovers_strict_mode(self):
        _, path = self.plan()
        history = (self.root / self.history).read_text()
        header = "|---|---|---|---|---|---|---|---|\n"
        (self.root / self.history).write_text(history.replace(header, header + self.row()))
        result, recovery = self.plan()
        self.apply(recovery)
        self.check(recovery, True)
        self.assertEqual(self.audit()["history_rows"], 1)
        self.assertEqual(result["counts"]["Singapore / Internship"], 1)

    def test_uncertain_or_missing_result_never_counts_as_success(self):
        original = copy.deepcopy(self.event)
        for outcome in ("in_progress", "unknown", "submitted", "failure", None):
            with self.subTest(outcome=outcome):
                self.event = copy.deepcopy(original)
                self.event["application_execution"]["outcome"] = outcome
                before = self.snapshot()
                with self.assertRaisesRegex(sync.SyncError, "success not proven"):
                    self.plan()
                self.assertEqual(before, self.snapshot())
        self.event = original
        self.event["application_execution"]["submission_evidence"] = []
        with self.assertRaisesRegex(sync.SyncError, "success reference required"):
            self.plan()

    def test_concurrent_notes_invalidate_check_and_post_apply_verify(self):
        _, path = self.plan()
        with (self.root / self.queue).open("a") as handle:
            handle.write("Concurrent edit.\n")
        before = self.snapshot()
        with self.assertRaisesRegex(sync.SyncError, "stale plan"):
            self.check(path)
        self.assertEqual(before, self.snapshot())
        _, fresh = self.plan()
        self.apply(fresh)
        with (self.root / self.history).open("a") as handle:
            handle.write("Another concurrent edit.\n")
        with self.assertRaisesRegex(sync.SyncError, "post-apply mismatch"):
            self.check(fresh, True)
        self.assertIn("Concurrent edit.", (self.root / self.queue).read_text())

    def test_config_edit_invalidates_existing_plan(self):
        _, path = self.plan()
        self.config_data["regions"]["canada"]["aliases"].append("Ottawa")
        self.save_config()
        with self.assertRaisesRegex(sync.SyncError, "config: stale plan"):
            self.check(path)

    def test_config_defaults_and_explicit_cli_config(self):
        self.config_data.pop("paths")
        self.config_data.pop("markdown")
        self.save_config()
        self.assertEqual(self.config.files, ("private/recruiting/history.md", "private/recruiting/queue.md"))
        result = subprocess.run([sys.executable, str(SCRIPT), "audit", "--root", str(self.root), "--config", self.config_path], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AUDIT_PASS history_rows=0", result.stdout)

    def test_tracked_or_unignored_config_and_notes_are_rejected(self):
        (self.root / "config.json").write_text(json.dumps(self.config_data))
        with self.assertRaisesRegex(sync.SyncError, "ignored"):
            sync.audit(self.root, "config.json")
        for path in (self.config_path, self.history, self.queue):
            with self.subTest(path=path):
                subprocess.run(["git", "-C", str(self.root), "add", "-f", path], check=True)
                with self.assertRaisesRegex(sync.SyncError, "ignored"):
                    self.audit()
                subprocess.run(["git", "-C", str(self.root), "rm", "--cached", "--quiet", path], check=True)

    def test_event_and_plan_artifacts_must_be_ignored_untracked(self):
        (self.root / "event.json").write_text(json.dumps(self.event))
        with self.assertRaisesRegex(sync.SyncError, "ignored"):
            sync.create_plan(self.root, "event.json", "private/plan")
        with self.assertRaisesRegex(sync.SyncError, "ignored"):
            (self.root / self.input).write_text(json.dumps(self.event))
            sync.create_plan(self.root, self.input, "public-plan")
        _, path = self.plan()
        subprocess.run(["git", "-C", str(self.root), "add", "-f", str(path)], check=True)
        with self.assertRaisesRegex(sync.SyncError, "ignored"):
            self.check(path)

    def test_changed_ignore_policy_is_rechecked(self):
        _, path = self.plan()
        (self.root / ".gitignore").write_text("private/\n!private/\nprivate/recruiting/config.json\nprivate/recruiting/event.json\nprivate/recruiting/plan-1/\n")
        with self.assertRaisesRegex(sync.SyncError, "ignored"):
            self.check(path)

    def test_config_path_traversal_absolute_and_symlink_rejected(self):
        original = copy.deepcopy(self.config_data)
        for path in ("private/../history.md", "/tmp/outside.md", "history.md", "private/recruiting/queue.md", "private/recruiting/invalid\npath.md"):
            with self.subTest(path=path):
                self.config_data = copy.deepcopy(original)
                self.config_data["paths"]["history"] = path
                with self.assertRaises(sync.SyncError):
                    self.save_config()
        self.config_data = original
        self.save_config()
        (self.root / "private/recruiting/link.md").symlink_to(self.root / self.history)
        self.config_data["paths"]["history"] = "private/recruiting/link.md"
        with self.assertRaisesRegex(sync.SyncError, "symlink"):
            self.save_config()

    def test_symlink_config_event_output_and_outside_path_rejected(self):
        (self.root / "private/recruiting/link.json").symlink_to(self.root / self.config_path)
        with self.assertRaisesRegex(sync.SyncError, "symlink"):
            sync.load_config(self.root, "private/recruiting/link.json")
        (self.root / self.input).write_text(json.dumps(self.event))
        (self.root / "private/link").symlink_to(self.root / "private/recruiting", target_is_directory=True)
        with self.assertRaisesRegex(sync.SyncError, "symlink"):
            sync.create_plan(self.root, "private/link/event.json", "private/new")
        with self.assertRaisesRegex(sync.SyncError, "symlink"):
            sync.create_plan(self.root, self.input, "private/link/new")
        with self.assertRaisesRegex(sync.SyncError, "outside"):
            sync.safe_path(self.root, self.root.parent / "external.json", True)

    def test_invalid_configuration_and_duplicate_json_keys_fail_closed(self):
        original = copy.deepcopy(self.config_data)
        changes = [
            {"regions": {}},
            {"regions": {"a": {"label": "Alpha", "aliases": ["shared"]}, "b": {"label": "Beta", "aliases": ["SHARED"]}}},
            {"markdown": {"history_headers": ["one"]}},
            {"markdown": {"history_heading": "# Wrong level"}},
            {"markdown": {"employment_labels": {"full_time": "same", "internship": "same"}}},
            {"unknown": "unsupported"},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.config_data = original | change
                with self.assertRaises(sync.SyncError):
                    self.save_config()
        (self.root / self.config_path).write_text('{"schema_version":1,"schema_version":1,"regions":{}}')
        with self.assertRaisesRegex(sync.SyncError, "duplicate key"):
            sync.load_config(self.root)

    def test_unsupported_region_or_location_conflict_rejected(self):
        original = copy.deepcopy(self.event)
        self.event["sync"]["region"] = "unconfigured"
        with self.assertRaisesRegex(sync.SyncError, "unsupported category"):
            self.plan()
        self.event = original
        self.event["sync"]["location"] = "Toronto"
        with self.assertRaisesRegex(sync.SyncError, "location conflicts"):
            self.plan()

    def test_region_aliases_do_not_match_substrings(self):
        self.config_data["regions"] = {"us": {"label": "US", "aliases": []}, "australia": {"label": "Australia", "aliases": []}}
        self.save_config()
        self.assertEqual(sync.classify("Australia / Full time", 1, self.config), "Australia / Full time")
        with self.assertRaisesRegex(sync.SyncError, "unclassified"):
            sync.classify("Brussels / Full time", 1, self.config)

    def test_similar_cross_company_and_note_reference_ids_do_not_merge(self):
        self.write_history(self.row(job_id="DEMO-SG-0010") + self.row(company="Other Fictional Company") + self.row(job_id="DEMO-SG-003", note="Job ID DEMO-SG-003; Compared with DEMO-SG-001."), {"Singapore / Internship": 3})
        self.write_queue(self.task() + self.task(job_id="DEMO-SG-0010") + self.task(company="Other Fictional Company"))
        _, path = self.plan()
        self.apply(path)
        self.check(path, True)
        self.assertEqual(self.audit()["history_rows"], 4)
        self.assertIn("DEMO-SG-0010", (self.root / self.queue).read_text())
        self.assertIn("Other Fictional Company", (self.root / self.queue).read_text())

    def test_verified_aliases_match_existing_identity(self):
        self.write_history(self.row(company="Fictional Alias", job_id="ALIAS-001"), {"Singapore / Internship": 1})
        self.write_queue(self.task(company="Fictional Alias", job_id="ALIAS-001"))
        self.event["application_execution"]["target"]["aliases"] = {"companies": ["Fictional Alias"], "job_ids": ["ALIAS-001"], "official_urls": []}
        result, path = self.plan()
        self.apply(path)
        self.check(path, True)
        self.assertEqual(result["counts"]["Singapore / Internship"], 1)

    def test_duplicate_candidates_and_existing_category_date_conflict_block(self):
        self.write_queue(self.task() + self.task())
        with self.assertRaisesRegex(sync.SyncError, "multiple pending"):
            self.plan()
        self.write_queue()
        self.write_history(self.row() + self.row(), {"Singapore / Internship": 2})
        with self.assertRaisesRegex(sync.SyncError, "multiple history"):
            self.plan()
        self.write_history(self.row(nature="Canada / Internship"), {"Canada / Internship": 1})
        with self.assertRaisesRegex(sync.SyncError, "conflicts"):
            self.plan()
        self.write_history(self.row(submitted="2026-09-30"), {"Singapore / Internship": 1})
        self.event["sync"]["submitted_on"] = "2026-10-01"
        with self.assertRaisesRegex(sync.SyncError, "conflicts"):
            self.plan()

    def test_task_children_removed_but_batch_paragraph_and_table_preserved(self):
        self.write_queue(self.task() + "\n  - More fictional task detail.\n", "Batch summary stays.\n\n| Other | Pending |\n")
        _, path = self.plan()
        self.apply(path)
        self.check(path, True)
        queue = (self.root / self.queue).read_text()
        self.assertNotIn("More fictional task detail.", queue)
        self.assertIn("Batch summary stays.", queue)
        self.assertIn("| Other | Pending |", queue)

    def test_official_child_link_matches_but_comparison_id_does_not(self):
        self.write_queue("- [ ] #p1 **Fictional Aurora Labs｜Software Engineering Intern**\n  - Official job: [Role](https://careers.example.com/jobs/DEMO-SG-001)\n")
        _, path = self.plan()
        self.apply(path)
        self.check(path, True)
        self.assertNotIn("Software Engineering Intern", (self.root / self.queue).read_text())
        self.write_queue(self.task(role="Other Intern", job_id="DEMO-SG-002").replace("\n  -", "; Compare Job ID DEMO-SG-001\n  -", 1))
        result, _ = self.plan()
        self.assertEqual(result["files"][1]["before_sha256"], result["files"][1]["after_sha256"])

    def test_unsupported_unrelated_queue_is_reported_but_target_blocks(self):
        legacy = "- [ ] **Software Engineering Intern** · Fictional Aurora Labs · Job ID DEMO-SG-001 · [Job](https://careers.example.com/jobs/DEMO-SG-001)\n"
        self.write_queue(legacy)
        self.assertTrue(any("unsupported task" in value for value in self.audit()["issues"]))
        with self.assertRaisesRegex(sync.SyncError, "unsupported structure"):
            self.plan()
        self.write_queue(legacy.replace("Fictional Aurora Labs", "Another Fictional Company"))
        self.plan()

    def test_url_only_identity_parentheses_roundtrip_and_id_conflict(self):
        self.event["application_execution"]["target"].update(job_id=None, official_url="https://careers.example.com/jobs/Engineer_(Intern)")
        self.write_queue("- [ ] #p1 **Fictional Aurora Labs｜Software Engineering Intern** · [Job](https://careers.example.com/jobs/Engineer_(Intern))\n")
        _, path = self.plan()
        self.apply(path)
        self.check(path, True)
        result, _ = self.plan()
        self.assertTrue(all(entry["before_sha256"] == entry["after_sha256"] for entry in result["files"]))
        self.assertNotEqual(sync.canonical_url("https://example.com/a%2Fb"), sync.canonical_url("https://example.com/a/b"))

    def test_numeric_targets_are_respected_without_changing_goals(self):
        self.write_history(targets={"Singapore / Full time": 10, "Canada / Full time": 20, "Singapore / Internship": 5, "Canada / Internship": 5})
        _, path = self.plan()
        self.apply(path)
        self.check(path, True)
        history = (self.root / self.history).read_text()
        self.assertIn("| Singapore / Internship | 1 | 5 | 4 |", history)
        self.assertIn("| All full time | 0 | 30 | 30 |", history)
        self.assertIn("| All submitted | 1 | 40 | 39 |", history)

    def test_legacy_mode_preserves_unknown_baseline_and_never_recounts_target(self):
        self.write_history(self.row(company="Fictional Legacy Company", job_id="LEGACY-001", nature="Singapore / Contract"), {"Singapore / Internship": 1})
        with self.assertRaisesRegex(sync.SyncError, "unclassified"):
            self.plan()
        result, path = self.plan("preserve_existing_counts")
        self.assertEqual(result["legacy_unclassified"], 1)
        self.apply(path)
        self.check(path, True)
        result, repeated = self.plan("preserve_existing_counts")
        self.assertEqual(result["counts"]["Singapore / Internship"], 2)
        self.check(repeated, True)

    def test_legacy_mode_rejects_partial_count_and_known_fact_conflicts(self):
        self.write_history(self.row(), {})
        with self.assertRaisesRegex(sync.SyncError, "legacy baseline"):
            self.plan("preserve_existing_counts")
        self.write_history(self.row(nature="Canada / Contract"), {"Canada / Internship": 1})
        with self.assertRaisesRegex(sync.SyncError, "conflicts"):
            self.plan("preserve_existing_counts")

    def test_header_drift_and_unknown_rows_are_reported(self):
        value = (self.root / self.history).read_text().replace("| Confirmed on |", "| Changed header |")
        (self.root / self.history).write_text(value)
        with self.assertRaisesRegex(sync.SyncError, "table header"):
            self.audit()
        self.write_history(self.row(nature="Singapore / Contract"), {"Singapore / Internship": 1})
        self.assertIn("unclassified", self.audit()["issues"][0])

    def test_secret_like_values_and_authenticated_urls_are_not_echoed(self):
        self.event["sync"]["note"] = "password" + ": " + "FICTIONAL_VALUE_DO_NOT_ECHO"
        (self.root / self.input).write_text(json.dumps(self.event))
        result = subprocess.run([sys.executable, str(SCRIPT), "plan", "--root", str(self.root), "--input", self.input, "--out", "private/invalid"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("FICTIONAL_VALUE_DO_NOT_ECHO", result.stdout + result.stderr)
        self.assertFalse((self.root / "private/invalid").exists())
        self.event["sync"]["note"] = "Fictional note."
        self.event["application_execution"]["submission_evidence"][0]["reference"] = "Reference: https://careers.example.com/confirmation?session=fabricated"
        with self.assertRaisesRegex(sync.SyncError, "authenticated URL"):
            self.plan()

    def test_plan_snapshot_paths_and_patch_fingerprint_cannot_be_changed(self):
        result, path = self.plan()
        result["files"][0]["path"] = "other.md"
        path.write_text(json.dumps(result))
        with self.assertRaisesRegex(sync.SyncError, "snapshots"):
            self.check(path)
        _, fresh = self.plan()
        (fresh.parent / "changes.patch").write_text("tampered")
        with self.assertRaisesRegex(sync.SyncError, "fingerprint"):
            self.check(fresh)


if __name__ == "__main__":
    unittest.main()
