"""Use only temporary repositories and explicitly fabricated application data."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "record.py"
SPEC = importlib.util.spec_from_file_location("application_record", SCRIPT)
record = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(record)


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("private/*\n", encoding="utf-8")
        (self.root / "private").mkdir()
        self.cv = self.root / "fabricated-cv.pdf"
        self.cv.write_bytes(b"%PDF-FAKE\nExplicitly fabricated test bytes; no personal data.\n")
        self.digest = hashlib.sha256(self.cv.read_bytes()).hexdigest()
        self.input = self.root / "private" / "fabricated-input.json"
        self.data = {
            "schema_version": 1,
            "record_id": "example-engineering-20990106",
            "application": {"company": "Example Test Company", "role": "Example Engineering Role",
                            "job_id": "FABRICATED-JOB-001", "submitted_on": "2099-01-06", "application_id": None},
            "resume": {"path": str(self.cv), "route": "engineering", "language": "en", "version": "example-v1",
                       "expected_sha256": self.digest},
            "form_answers": [{"field": "Project description", "value": "Fabricated test project summary."}],
            "submission_evidence": [{"kind": "user_confirmation", "reference": "fabricated-test-confirmation",
                                     "observed_at": "2099-01-06T10:00:00+08:00"}],
        }

    def run_record(self, data=None, validate_only=False):
        self.input.write_text(json.dumps(self.data if data is None else data), encoding="utf-8")
        return record.archive(self.input, self.root, validate_only)

    def assert_no_archive(self):
        self.assertFalse((self.root / record.BASE).exists())

    def test_hash_mismatch_writes_nothing(self):
        self.data["resume"]["expected_sha256"] = "0" * 64
        with self.assertRaisesRegex(record.RecordError, "hash mismatch"):
            self.run_record()
        self.assert_no_archive()

    def test_validate_only_writes_nothing(self):
        self.assertEqual(self.run_record(validate_only=True)[0], "validated")
        self.assert_no_archive()

    def test_same_cv_is_reused_for_two_applications(self):
        self.assertEqual(self.run_record()[0], "created")
        second = copy.deepcopy(self.data)
        second["record_id"] = "example-second-application"
        second["application"]["job_id"] = "FABRICATED-JOB-002"
        self.assertEqual(self.run_record(second)[0], "created")
        base = self.root / record.BASE
        self.assertEqual(len(list((base / "objects").iterdir())), 1)
        self.assertEqual(len(list((base / "records").iterdir())), 2)
        saved = json.loads((base / "records" / (self.data["record_id"] + ".json")).read_text())
        self.assertNotIn("path", saved["resume"])
        self.assertNotIn(str(self.root), json.dumps(saved))
        self.assertEqual(saved["form_answers"], self.data["form_answers"])
        self.assertEqual((base / saved["resume"]["object_path"]).read_bytes(), self.cv.read_bytes())

    def test_same_record_is_idempotent_and_conflicts_are_rejected(self):
        _, path = self.run_record()
        target = self.root / path
        before = target.stat().st_mtime_ns
        self.assertEqual(self.run_record()[0], "unchanged")
        self.assertEqual(target.stat().st_mtime_ns, before)
        original = target.read_bytes()
        self.data["form_answers"][0]["value"] = "A different fabricated answer."
        with self.assertRaisesRegex(record.RecordError, "identifier conflict"):
            self.run_record()
        self.assertEqual(target.read_bytes(), original)

    def test_output_must_be_ignored(self):
        (self.root / ".gitignore").write_text("private/fabricated-input.json\n", encoding="utf-8")
        with self.assertRaisesRegex(record.RecordError, "Git-ignored"):
            self.run_record()
        self.assert_no_archive()

    def test_input_must_be_ignored_and_untracked(self):
        self.input.write_text(json.dumps(self.data), encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-f", str(self.input)], check=True)
        with self.assertRaisesRegex(record.RecordError, "Git-ignored"):
            record.archive(self.input, self.root)
        self.assert_no_archive()

    def test_symlink_output_directory_is_rejected(self):
        outside = self.root / "untouched"
        outside.mkdir()
        (self.root / record.BASE).symlink_to(outside, target_is_directory=True)
        with self.assertRaises((OSError, record.RecordError)):
            self.run_record()
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlink_input_is_rejected_without_reading_target(self):
        self.input.symlink_to(self.cv)
        with self.assertRaises(OSError):
            record.archive(self.input, self.root)
        self.assert_no_archive()

    def test_nested_output_symlink_is_rejected(self):
        base = self.root / record.BASE
        base.mkdir()
        outside = self.root / "untouched"
        outside.mkdir()
        for kind in ("objects", "records"):
            with self.subTest(kind=kind):
                target = base / kind
                target.symlink_to(outside, target_is_directory=True)
                try:
                    with self.assertRaises((OSError, record.RecordError)):
                        self.run_record(validate_only=True)
                finally:
                    target.unlink()
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlink_object_or_record_is_rejected(self):
        for kind in ("objects", "records"):
            with self.subTest(kind=kind):
                base = self.root / record.BASE / kind
                base.mkdir(parents=True, exist_ok=True)
                filename = self.digest + ".pdf" if kind == "objects" else self.data["record_id"] + ".json"
                target = base / filename
                target.symlink_to(self.cv)
                try:
                    with self.assertRaises(OSError):
                        self.run_record(validate_only=True)
                finally:
                    target.unlink()

    def test_record_path_traversal_is_rejected(self):
        for value in ("../escape", ".", "..", "folder/name", "outside\\name", "中文"):
            with self.subTest(value=value):
                self.data["record_id"] = value
                with self.assertRaisesRegex(record.RecordError, "invalid identifier"):
                    self.run_record()
        self.assert_no_archive()

    def test_existing_object_corruption_is_rejected(self):
        self.run_record()
        target = self.root / record.BASE / "objects" / (self.digest + ".pdf")
        target.write_bytes(b"fabricated damaged object")
        with self.assertRaisesRegex(record.RecordError, "object hash mismatch"):
            self.run_record()
        self.assertEqual(target.read_bytes(), b"fabricated damaged object")

    def test_record_conflict_does_not_archive_a_different_cv(self):
        self.run_record()
        self.cv.write_bytes(b"A second explicitly fabricated CV version.")
        self.data["resume"]["expected_sha256"] = hashlib.sha256(self.cv.read_bytes()).hexdigest()
        with self.assertRaisesRegex(record.RecordError, "identifier conflict"):
            self.run_record()
        objects = self.root / record.BASE / "objects"
        self.assertEqual([path.name for path in objects.iterdir()], [self.digest + ".pdf"])

    def test_existing_record_missing_object_is_not_repaired_silently(self):
        self.run_record()
        (self.root / record.BASE / "objects" / (self.digest + ".pdf")).unlink()
        with self.assertRaisesRegex(record.RecordError, "has no CV object"):
            self.run_record()

    def test_success_evidence_is_required(self):
        self.data["submission_evidence"] = []
        with self.assertRaisesRegex(record.RecordError, "success reference required"):
            self.run_record()
        self.assert_no_archive()

    def test_unknown_submission_date_stays_null(self):
        self.data["application"]["submitted_on"] = None
        self.data["submission_evidence"][0]["observed_at"] = None
        _, path = self.run_record()
        saved = json.loads((self.root / path).read_text())
        self.assertIsNone(saved["application"]["submitted_on"])
        self.assertIsNone(saved["submission_evidence"][0]["observed_at"])

    def test_dates_and_evidence_timestamps_are_validated(self):
        for value in ("2099-02-30", "2099-1-6", "unknown"):
            with self.subTest(value=value):
                self.data["application"]["submitted_on"] = value
                with self.assertRaises(record.RecordError):
                    self.run_record()
        self.data["application"]["submitted_on"] = None
        self.data["submission_evidence"][0]["observed_at"] = "2099-01-06T10:00:00"
        with self.assertRaisesRegex(record.RecordError, "timezone required"):
            self.run_record()
        self.assert_no_archive()

    def test_sensitive_fields_and_unknown_profile_fields_are_rejected(self):
        for field in ("Password", "Verification code", "身份证号码", "Work authorization", "Email"):
            with self.subTest(field=field):
                self.data["form_answers"][0]["field"] = field
                with self.assertRaisesRegex(record.RecordError, "sensitive field"):
                    self.run_record()
        self.data["form_answers"] = []
        self.data["account"] = "fabricated account"
        with self.assertRaisesRegex(record.RecordError, "invalid fields"):
            self.run_record()
        self.assert_no_archive()

    def test_credential_url_and_obvious_secret_are_rejected(self):
        self.data["submission_evidence"][0]["reference"] = "https://example.invalid/receipt?session=FABRICATED"
        with self.assertRaisesRegex(record.RecordError, "credentials forbidden"):
            self.run_record()
        self.data["submission_evidence"][0]["reference"] = "fabricated-reference"
        self.data["form_answers"][0]["value"] = ": ".join(("password", "EXPLICITLY-FABRICATED-TEST-VALUE"))
        with self.assertRaisesRegex(record.RecordError, "sensitive content"):
            self.run_record()
        self.assert_no_archive()

    def test_duplicate_json_keys_are_rejected(self):
        self.input.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
        with self.assertRaisesRegex(record.RecordError, "duplicate JSON field"):
            record.archive(self.input, self.root)
        self.assert_no_archive()

    def test_cli_does_not_echo_invalid_values(self):
        marker = "FABRICATED-DO-NOT-ECHO-MARKER"
        self.data["record_id"] = "../" + marker
        self.input.write_text(json.dumps(self.data), encoding="utf-8")
        completed = subprocess.run(["python3", str(SCRIPT), "--input", str(self.input), "--root", str(self.root)],
                                   capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 2)
        self.assertNotIn(marker, completed.stdout + completed.stderr)
        self.assert_no_archive()


if __name__ == "__main__":
    unittest.main()
