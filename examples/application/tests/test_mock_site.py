"""Exercise only a loopback server, temporary Git repositories and fictional data."""

import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "mock_site.py"
SPEC = importlib.util.spec_from_file_location("mock_application", SCRIPT)
MOCK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOCK)


def multipart(fields=None, upload=None, filename="demo-resume.pdf"):
    fields = MOCK.FIELDS if fields is None else fields
    result = b""
    for name, value in fields.items():
        result += (f'--fixture-boundary\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode()
    result += (f'--fixture-boundary\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/pdf\r\n\r\n').encode()
    result += (MOCK.fixture_pdf() if upload is None else upload) + b"\r\n--fixture-boundary--\r\n"
    return result


class MockTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "fixture"
        self.details = MOCK.setup(self.root)
        self.server = MOCK.HTTPServer(("127.0.0.1", 0), MOCK.handler(self.root))
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method="GET", path="/", body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def draft(self, **kwargs):
        return self.request("POST", "/draft", multipart(**kwargs),
                            {"Content-Type": "multipart/form-data; boundary=fixture-boundary"})

    def test_draft_readback_contains_exact_values_filename_hash_and_bytes(self):
        code, headers, _ = self.draft()
        self.assertEqual(code, 303)
        self.assertEqual(headers["Location"], "/review")
        code, _, body = self.request(path="/review")
        self.assertEqual(code, 200)
        for value in [*MOCK.FIELDS.values(), "demo-resume.pdf", self.details["sha256"]]:
            self.assertIn(value.encode(), body)
        self.assertEqual(self.request(path="/uploaded.pdf")[2], MOCK.fixture_pdf())
        self.assertEqual(MOCK.state(self.root)["submit_count"], 0)

    def test_get_pages_do_not_change_files_or_state(self):
        self.draft()
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (self.root / "private").rglob("*") if p.is_file()}
        for page in ("/", "/review", "/uploaded.pdf", "/result", "/missing"):
            self.request(path=page)
        after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (self.root / "private").rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_unknown_outcome_has_no_success_and_cannot_be_reconciled(self):
        current = MOCK.state(self.root)
        current["mode"] = "ambiguous"
        MOCK.save(self.root / "private/state.json", current)
        self.draft()
        self.assertEqual(self.request("POST", "/submit", b"")[0], 303)
        body = self.request(path="/result")[2]
        self.assertIn(b"outcome unknown", body)
        self.assertNotIn(b"SYNTHETIC-001", body)
        self.assertNotIn(b"submitted successfully", body)
        self.assertIsNone(MOCK.state(self.root)["application_id"])
        self.assertEqual(self.request("POST", "/submit", b"")[0], 409)
        self.assertEqual(MOCK.state(self.root)["submit_count"], 1)
        with self.assertRaisesRegex(ValueError, "Synthetic success"):
            MOCK.reconcile(self.root)
        self.assertFalse((self.root / "private/mock-execution.json").exists())
        self.assertFalse((self.root / "private/application-records").exists())

    def test_duplicate_attempt_rejected_without_count_or_state_change(self):
        self.draft()
        self.assertEqual(self.request("POST", "/submit", b"")[0], 303)
        before = (self.root / "private/state.json").read_bytes()
        self.assertEqual(self.request("POST", "/submit", b"")[0], 409)
        self.assertEqual(self.draft()[0], 409)
        self.assertEqual((self.root / "private/state.json").read_bytes(), before)
        self.assertEqual(MOCK.state(self.root)["submit_count"], 1)

    def test_rejects_nonfixture_fields_file_and_unreviewed_submit(self):
        self.assertEqual(self.request("POST", "/submit", b"")[0], 400)
        for options in ({"fields": {**MOCK.FIELDS, "name": "Another fictional value"}},
                        {"fields": {**MOCK.FIELDS, "extra": "unexpected"}},
                        {"upload": b"%PDF-invalid"}, {"filename": "other.pdf"}):
            with self.subTest(options=list(options)):
                self.assertEqual(self.draft(**options)[0], 400)
        self.assertEqual(MOCK.state(self.root)["status"], "empty")
        self.assertFalse((self.root / "private/uploaded.pdf").exists())

    def test_nonloopback_host_or_external_origin_is_rejected(self):
        self.assertEqual(self.request(headers={"Host": "example.invalid"})[0], 403)
        self.assertEqual(self.request(headers={"Origin": "https://example.invalid"})[0], 403)

    def test_setup_preserves_existing_directory_and_keeps_runtime_ignored(self):
        before = (self.root / "private/state.json").read_bytes()
        with self.assertRaises(FileExistsError):
            MOCK.setup(self.root)
        self.assertEqual((self.root / "private/state.json").read_bytes(), before)
        for path in ("private/state.json", "private/demo-resume.pdf", "private/recruiting/history.md"):
            result = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--quiet", path])
            self.assertEqual(result.returncode, 0)

    def test_fixture_pdf_has_one_page_and_consistent_xref(self):
        pdf = MOCK.fixture_pdf()
        self.assertTrue(pdf.startswith(b"%PDF-1.4\n"))
        self.assertTrue(pdf.endswith(b"%%EOF\n"))
        self.assertEqual(pdf.count(b"/Type /Page "), 1)
        self.assertIn(b"/Count 1", pdf)
        offset = int(pdf.split(b"startxref\n")[1].splitlines()[0])
        self.assertEqual(pdf[offset:offset + 4], b"xref")
        self.assertEqual(hashlib.sha256(pdf).hexdigest(), self.details["sha256"])

    def test_success_reconciles_to_existing_protocol_without_applying_patch(self):
        self.draft()
        self.request("POST", "/submit", b"")
        history = self.root / "private/recruiting/history.md"
        original = history.read_bytes()
        result = MOCK.reconcile(self.root)
        self.assertEqual(history.read_bytes(), original)
        self.assertTrue(Path(result["patch"]).exists())
        event = json.loads((self.root / "private/mock-execution.json").read_text())
        self.assertEqual(event["application_execution"]["outcome"], "success_proven")
        archived = json.loads(Path(result["record"]).read_text())
        self.assertEqual(archived["application"]["application_id"], "SYNTHETIC-001")
        self.assertEqual(archived["resume"]["sha256"], self.details["sha256"])
        self.assertEqual(archived["form_answers"][0]["value"], MOCK.FIELDS["answer"])
        self.assertEqual(MOCK.reconcile(self.root), result)


if __name__ == "__main__":
    unittest.main()
