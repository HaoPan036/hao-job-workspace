#!/usr/bin/env python3
"""Loopback-only, fictional browser test fixture; never a real application service."""

import argparse
import datetime as dt
from email.parser import BytesParser
from email.policy import default
import hashlib
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[2]
TARGET = {"company": "Fictional Aurora Labs", "role": "Software Engineering Intern",
          "job_id": "DEMO-SG-001", "official_url": "https://example.invalid/jobs/DEMO-SG-001"}
FIELDS = {"name": "Example Candidate", "email": "example@example.invalid",
          "answer": "Implemented retry and stop rules for a fictional exercise. The first execution timed out, one retry also timed out, and the program stopped. The root cause remains unknown; no performance improvement is claimed."}
PROFILE_FILES = tuple(name + ".json" for name in
                      ("index", "preferences", "facts", "answers", "internship", "zh", "en", "history"))
WHITELIST = ("tools/application-profile/read.py", "tools/application-record/record.py",
             "tools/recruiting-sync/sync.py", "templates/recruiting/config.example.json",
             "templates/recruiting/history.md", "templates/recruiting/queue.md") + tuple(
                 "templates/application-profile/" + name for name in PROFILE_FILES)


def fixture_pdf():
    lines = ["FICTIONAL APPLICATION TEST - NOT A REAL RESUME", FIELDS["name"],
             TARGET["company"] + " / " + TARGET["job_id"],
             "Implemented retry and stop rules for a fictional exercise.",
             "First execution timed out; one retry also timed out; stopped.",
             "Root cause remains unknown. No performance improvement claimed."]
    content = ("BT /F1 12 Tf 50 750 Td 18 TL " + " T* ".join(
        "(" + line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj"
        for line in lines) + " ET").encode("ascii")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"]
    result, offsets = b"%PDF-1.4\n", [0]
    for i, item in enumerate(objects, 1):
        offsets.append(len(result))
        result += str(i).encode() + b" 0 obj\n" + item + b"\nendobj\n"
    start = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(f"{n:010d} 00000 n \n".encode() for n in offsets[1:])
    return result + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()


def save(path, value):
    data = value if isinstance(value, bytes) else (json.dumps(value, indent=2) + "\n").encode()
    temporary = path.with_name(path.name + ".pending")
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def state(root):
    value = json.loads((root / "private/state.json").read_text())
    if value.get("fixture") != "fictional-application-only" or value.get("mode") not in ("success", "ambiguous"):
        raise ValueError("Not a supported fictional fixture")
    return value


def setup(root, mode="success", source=SOURCE):
    if mode not in ("success", "ambiguous"):
        raise ValueError("Unsupported fixture mode")
    contents = {name: (source / name).read_bytes() for name in WHITELIST}
    root.mkdir(parents=True, exist_ok=False)
    (root / ".gitignore").write_text("**/private/\n**/__pycache__/\n")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    for name, data in contents.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for directory in ("private", "private/recruiting", "private/application-profile"):
        (root / directory).mkdir(mode=0o700, exist_ok=True)
    for name in PROFILE_FILES:
        save(root / "private/application-profile" / name, contents["templates/application-profile/" + name])
    for src, dest in (("config.example.json", "config.json"), ("history.md", "history.md"), ("queue.md", "queue.md")):
        save(root / "private/recruiting" / dest, contents["templates/recruiting/" + src])
    queue = root / "private/recruiting/queue.md"
    queue.write_text(queue.read_text().replace("## Pending applications\n", "## Pending applications\n\n- [ ] #p1 **" + TARGET["company"] + "｜" + TARGET["role"] + "** · Job ID " + TARGET["job_id"] + " · [Fictional job](" + TARGET["official_url"] + ")\n"))
    save(root / "private/demo-resume.pdf", fixture_pdf())
    save(root / "private/state.json", {"fixture": "fictional-application-only", "mode": mode,
         "status": "empty", "draft": None, "submit_count": 0, "result_timestamp": None, "application_id": None})
    return {"root": str(root), "resume": str(root / "private/demo-resume.pdf"),
            "sha256": hashlib.sha256(fixture_pdf()).hexdigest(), "fields": FIELDS, "target": TARGET, "mode": mode}


def handler(root):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, code, body, kind="text/html; charset=utf-8"):
            payload = body if isinstance(body, bytes) else body.encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; form-action 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def local(self):
            authority = "127.0.0.1:" + str(self.server.server_port)
            return self.headers.get("Host") == authority and self.headers.get("Origin", "http://" + authority) == "http://" + authority

        def do_GET(self):
            if not self.local():
                return self.respond(403, "Loopback fixture only")
            current = state(root)
            heading = "<h1>Fictional application test</h1><p>" + html.escape(" / ".join(TARGET[k] for k in ("company", "role", "job_id"))) + "</p><p>Mock only. No real application is sent.</p>"
            if self.path == "/":
                body = '<form method="post" action="/draft" enctype="multipart/form-data"><p><label>Name <input name="name" required></label></p><p><label>Email <input type="email" name="email" required></label></p><p><label>Project answer <textarea name="answer" required rows="6" cols="72"></textarea></label></p><p><label>Resume PDF <input type="file" name="file" accept=".pdf" required></label></p><button>Save draft for review</button></form>'
            elif self.path == "/review" and current["draft"]:
                body = "<h2>Review saved draft</h2>" + "".join("<p><strong>" + html.escape(k) + "</strong>: " + html.escape(v) + "</p>" for k, v in current["draft"].items())
                body += '<p><a href="/uploaded.pdf">Read uploaded PDF</a></p><form method="post" action="/submit"><button>Submit once</button></form>' if current["submit_count"] == 0 else '<a href="/result">View result</a>'
            elif self.path == "/uploaded.pdf" and current["draft"]:
                return self.respond(200, (root / "private/uploaded.pdf").read_bytes(), "application/pdf")
            elif self.path == "/result" and current["submit_count"]:
                body = "<h2>Application submitted successfully (synthetic)</h2><p>SYNTHETIC-001</p>" if current["status"] == "success" else "<h2>Submission outcome unknown</h2><p>Do not retry. No success evidence is available.</p>"
                body += "<p>submit_count: " + str(current["submit_count"]) + "</p>"
            else:
                return self.respond(404, "No fixture page")
            self.respond(200, '<!doctype html><html lang="en"><meta charset="utf-8"><title>Fictional application test</title><body>' + heading + body + "</body></html>")

        def do_POST(self):
            if not self.local():
                return self.respond(403, "Loopback fixture only")
            current = state(root)
            if current["submit_count"]:
                return self.respond(409, "Submission already attempted; do not retry")
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > 65536:
                    raise ValueError("Invalid fixture input")
                raw = self.rfile.read(size)
                if self.path == "/draft":
                    message = BytesParser(policy=default).parsebytes(("Content-Type: " + self.headers.get("Content-Type", "") + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + raw)
                    parts = list(message.iter_parts())
                    values = {p.get_param("name", header="content-disposition"): p for p in parts}
                    if len(parts) != 4 or set(values) != set(FIELDS) | {"file"}:
                        raise ValueError("Only the four fictional fields are accepted")
                    selected = {k: values[k].get_payload(decode=True).decode("utf-8") for k in FIELDS}
                    upload = values["file"].get_payload(decode=True)
                    if selected != FIELDS or values["file"].get_filename() != "demo-resume.pdf" or upload != fixture_pdf():
                        raise ValueError("Only the exact fictional values and fixture PDF are accepted")
                    save(root / "private/uploaded.pdf", upload)
                    current.update(status="draft", draft={**selected, "filename": "demo-resume.pdf", "sha256": hashlib.sha256(upload).hexdigest()})
                    destination = "/review"
                elif self.path == "/submit" and current["draft"] and not raw:
                    current.update(submit_count=1, status="success" if current["mode"] == "success" else "unknown", result_timestamp=dt.datetime.now(dt.timezone.utc).isoformat())
                    current["application_id"] = "SYNTHETIC-001" if current["status"] == "success" else None
                    destination = "/result"
                else:
                    raise ValueError("Save and review a draft before submitting")
                save(root / "private/state.json", current)
            except (ValueError, TypeError, UnicodeError, AttributeError):
                return self.respond(400, "Rejected: only fixed fictional fields and the generated PDF are accepted")
            self.send_response(303)
            self.send_header("Location", destination)
            self.send_header("Content-Length", "0")
            self.end_headers()
    return Handler


def reconcile(root):
    current = state(root)
    expected = {**FIELDS, "filename": "demo-resume.pdf", "sha256": hashlib.sha256(fixture_pdf()).hexdigest()}
    if current["mode"] != "success" or current["status"] != "success" or current["submit_count"] != 1 or current["application_id"] != "SYNTHETIC-001" or current["draft"] != expected or (root / "private/uploaded.pdf").read_bytes() != fixture_pdf():
        raise ValueError("Synthetic success and unchanged uploaded fixture required; never retry submit")
    when = current["result_timestamp"]
    evidence = [{"kind": "official_confirmation", "reference": "Synthetic fixture success page: SYNTHETIC-001; not a real employer receipt", "observed_at": when}]
    event = {"schema_version": 1, "application_execution": {"target": TARGET, "outcome": "success_proven", "result_timestamp": when, "application_id": "SYNTHETIC-001", "submission_evidence": evidence}, "sync": {"confirmed_on": when[:10], "submitted_on": when[:10], "region": "singapore", "employment_type": "internship", "location": "Singapore", "status": "Synthetic submitted fixture", "note": "Local mock only; no real application.", "material_record_id": "synthetic-demo-sg-001"}}
    record = {"schema_version": 1, "record_id": "synthetic-demo-sg-001", "application": {**TARGET, "submitted_on": when[:10], "application_id": "SYNTHETIC-001"}, "resume": {"path": "private/uploaded.pdf", "route": "fictional-demo", "language": "en", "version": "fictional-v1", "expected_sha256": expected["sha256"]}, "form_answers": [{"field": "Project description", "value": FIELDS["answer"]}], "submission_evidence": evidence}
    for name, data in (("mock-execution.json", event), ("mock-record-input.json", record)):
        path = root / "private" / name
        if path.exists() and json.loads(path.read_text()) != data:
            raise ValueError("Existing synthetic input differs; inspect without submitting again")
        if not path.exists():
            save(path, data)
    def run(tool, *args):
        subprocess.run([sys.executable, str(root / "tools" / tool), *args], cwd=root, check=True)
    if not (root / "private/mock-plan").exists():
        run("recruiting-sync/sync.py", "plan", "--input", "private/mock-execution.json", "--out", "private/mock-plan")
    run("recruiting-sync/sync.py", "check", "--plan", "private/mock-plan/plan.json")
    run("application-record/record.py", "--input", "private/mock-record-input.json")
    return {"patch": str(root / "private/mock-plan/changes.patch"), "plan": str(root / "private/mock-plan/plan.json"), "record": str(root / "private/application-records/records/synthetic-demo-sg-001.json"), "state": "planned and archived; patch not applied"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "serve", "reconcile"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--mode", choices=("success", "ambiguous"), default="success")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == "setup":
            result = setup(root, args.mode)
        elif args.command == "reconcile":
            result = reconcile(root)
        else:
            state(root)
            with HTTPServer(("127.0.0.1", args.port), handler(root)) as server:
                print(f"Fictional fixture at http://127.0.0.1:{server.server_port}", flush=True)
                server.serve_forever()
            return 0
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("Fixture operation failed; inspect local inputs and preserve existing files", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
