import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import funnel

ROOT = Path(__file__).resolve().parents[3]


class FunnelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("private/\n")
        private = self.root / "private/recruiting"
        private.mkdir(parents=True)
        for name in ("config.example.json", "queue.md", "history.md"):
            target = "config.json" if name.endswith(".json") else name
            (private / target).write_bytes((ROOT / "templates/recruiting" / name).read_bytes())
        self.config = private / "config.json"
        self.queue = private / "queue.md"
        self.history = private / "history.md"
        tasks = """- [ ] #p0 **Fictional Alpha｜Engineer** · [Official job](https://example.test/jobs/1)
  - Queued on: 2029-12-25
  - Deadline: 2030-01-09
- [ ] #p1 **Fictional Beta｜Analyst** · [Official job](https://example.test/jobs/2)
  - Added on: 2030-01-07
  - Deadline: 2030-01-07
- [ ] #p2 **Fictional Gamma｜Intern** · [Official job](https://example.test/jobs/3) · verified `2030-01-08`
"""
        queue = self.queue.read_text().replace("<!-- job-radar:auto:end -->", tasks + "<!-- job-radar:auto:end -->")
        queue += "\n### 2030-01-06: Recorded discovery batch\n\n4 evaluated = 2 queued + 1 manual review + 1 excluded + 0 duplicate\n"
        queue += "\n### 2030-01-05: Batch without counts\n"
        self.queue.write_text(queue)
        history = self.history.read_text().replace("\n## Notes", "\n| 2030-01-08 | Not recorded | Fictional Delta | Engineer | Canada / Full time | Submitted | [Official](https://example.test/jobs/4) | Confirmed fixture |\n| 2029-12-01 | 2029-12-01 | Fictional Epsilon | Intern | Singapore / Internship | Submitted | [Official](https://example.test/jobs/5) | Confirmed fixture |\n\n## Notes")
        self.history.write_text(history)

    def health(self):
        return funnel.build_funnel_health(self.root, "private/recruiting/config.json", dt.date(2030, 1, 8))

    def test_counts_flow_stale_deadline_and_unknown_dates_use_recorded_evidence(self):
        before = {p: p.read_bytes() for p in (self.config, self.queue, self.history)}
        with mock.patch("socket.create_connection", side_effect=AssertionError("No network")):
            health = self.health()
        self.assertEqual((health["p0_count"], health["p1_count"], health["p2_count"]), (1, 1, 1))
        self.assertEqual(health["current_count"], 3)
        self.assertEqual(health["recent_queued_count"], 2)
        self.assertEqual(health["recent_history_count"], 1)
        self.assertEqual(len(health["stale_entries"]), 1)
        self.assertEqual(len(health["urgent_entries"]), 1)
        self.assertEqual(len(health["expired_entries"]), 1)
        self.assertEqual(health["unknown_dates"], {
            "queue_added_on": 1, "queue_deadline": 1, "history_submitted_on": 1,
            "recent_batch_dates_without_disposition": ["2030-01-05"],
        })
        for path, value in before.items():
            self.assertEqual(path.read_bytes(), value)
        self.assertIn("not the actual submission date", health["date_basis"]["history_flow"])

    def test_existing_config_controls_headings_and_table_labels(self):
        config = json.loads(self.config.read_text())
        config["markdown"]["queue_heading"] = "## 候选任务"
        config["markdown"]["history_heading"] = "## 已确认申请"
        config["markdown"]["history_headers"][0] = "确认日期"
        self.config.write_text(json.dumps(config, ensure_ascii=False))
        self.queue.write_text(self.queue.read_text().replace("## Pending applications", "## 候选任务"))
        self.history.write_text(self.history.read_text().replace("## Submitted applications", "## 已确认申请").replace("Confirmed on", "确认日期"))
        self.assertEqual(self.health()["current_count"], 3)
        self.assertEqual(self.health()["recent_history_count"], 1)

    def test_verification_date_never_becomes_entry_date_and_unknowns_are_not_stale(self):
        health = self.health()
        self.assertEqual(health["unknown_dates"]["queue_added_on"], 1)
        self.assertTrue(all("Gamma" not in entry["title"] for entry in health["stale_entries"]))
        self.assertIn("Date coverage", funnel.render_funnel_health(health))

    def test_ambiguous_or_inconsistent_batch_counts_fail_closed(self):
        before = self.queue.read_text()
        self.queue.write_text(before.replace("4 evaluated", "9 evaluated"))
        with self.assertRaises(funnel.sync.SyncError):
            self.health()
        self.queue.write_text(before + "\n### 2030-01-06: Duplicate batch\n\n4 evaluated = 2 queued + 1 manual review + 1 excluded + 0 duplicate\n")
        with self.assertRaises(funnel.sync.SyncError):
            self.health()

    def test_invalid_dates_and_unsupported_pending_tasks_are_not_silently_counted(self):
        before = self.queue.read_text()
        self.queue.write_text(before.replace("Deadline: 2030-01-09", "Deadline: 2030-02-31"))
        with self.assertRaises(funnel.sync.SyncError):
            self.health()
        self.queue.write_text(before.replace("#p0 **Fictional Alpha｜Engineer**", "**Unstructured task**"))
        with self.assertRaises(funnel.sync.SyncError):
            self.health()

    def test_tracked_or_symlink_input_is_rejected(self):
        subprocess.run(["git", "-C", str(self.root), "add", "-f", "private/recruiting/queue.md"], check=True)
        with self.assertRaises(funnel.sync.SyncError):
            self.health()

    def test_cli_json_is_read_only(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in (self.config, self.queue, self.history)}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = funnel.main(["--root", str(self.root), "--config", "private/recruiting/config.json", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["current_count"], 3)
        for path, data in before.items():
            self.assertEqual((self.root / path).read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
