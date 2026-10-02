#!/usr/bin/env python3
"""Archive an explicitly selected, successfully submitted application locally."""

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid
from urllib.parse import parse_qsl, urlsplit


BASE = Path("private/application-records")
MAX_JSON = 10 * 1024 * 1024
MAX_CV = 50 * 1024 * 1024
SENSITIVE_FIELD = re.compile(
    r"password|passcode|\botp\b|verification\s*code|one.?time|account|user.?name|"
    r"phone|mobile|e.?mail|address|passport|identity|national.?id|\bnric\b|\bssn\b|"
    r"birth|\bdob\b|gender|nationality|citizen|visa|work.?authori[sz]|"
    r"salary|disability|ethnicity|religion|consent|declaration|"
    r"密码|口令|验证码|账号|账户|用户名|邮箱|手机|电话|住址|地址|证件|身份证|护照|"
    r"出生|生日|性别|国籍|签证|工作许可|薪资|薪酬|残疾|民族|宗教|声明|同意",
    re.IGNORECASE,
)
SECRET = re.compile(
    r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|"
    r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,})\b|"
    r"\b(?:password|passwd|api[_ -]?key|access[_ -]?token|authorization|cookie)"
    r"\s*[:=]|\b[STFGM]\d{7}[A-Z]\b|\b\d{17}[0-9Xx]\b",
    re.IGNORECASE,
)


class RecordError(Exception):
    """A deliberately value-free error suitable for command output."""


def fail(category):
    raise RecordError(category)


def shape(value, allowed, required, category):
    if not isinstance(value, dict) or set(value) - set(allowed):
        fail(category + ": invalid fields")
    if set(required) - set(value):
        fail(category + ": missing fields")


def string(value, category, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        fail(category + ": invalid text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        fail(category + ": invalid text encoding")
    if SECRET.search(value):
        fail(category + ": sensitive content")
    return value


def date(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        fail("submitted_on: invalid date")
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        fail("submitted_on: invalid date")
    return value


def timestamp(value, category):
    if value is None:
        return None
    if not isinstance(value, str) or "T" not in value:
        fail(category + ": timezone required")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            fail(category + ": timezone required")
    except ValueError:
        fail(category + ": invalid timestamp")
    return value


def url(value, category):
    if value is None:
        return None
    string(value, category)
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            fail(category + ": invalid URL")
        if parsed.username or parsed.password:
            fail(category + ": credentials forbidden")
        for name, _ in parse_qsl(parsed.query):
            if re.search(r"token|secret|password|credential|auth|session|key", name, re.I):
                fail(category + ": credentials forbidden")
    except ValueError:
        fail(category + ": invalid URL")
    return value


def validate(data):
    shape(data, {"schema_version", "record_id", "application", "resume", "form_answers",
                 "submission_evidence", "jd"},
          {"schema_version", "record_id", "application", "resume", "form_answers",
           "submission_evidence"}, "input")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        fail("schema_version: unsupported")
    record_id = data["record_id"]
    if not isinstance(record_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", record_id):
        fail("record_id: invalid identifier")
    application = data["application"]
    shape(application, {"company", "role", "job_id", "batch", "official_url", "submitted_on", "application_id"},
          {"company", "role", "submitted_on", "application_id"}, "application")
    app = {key: string(application[key], "application." + key) for key in ("company", "role")}
    for key in ("job_id", "batch", "application_id"):
        app[key] = string(application.get(key), "application." + key, nullable=True)
    app["official_url"] = url(application.get("official_url"), "application.official_url")
    if not any(app[key] for key in ("job_id", "batch", "official_url")):
        fail("application: job identifier required")
    app["submitted_on"] = date(application["submitted_on"])
    resume = data["resume"]
    shape(resume, {"path", "route", "language", "version", "expected_sha256"},
          {"path", "route", "language", "version", "expected_sha256"}, "resume")
    source = string(resume["path"], "resume.path")
    digest = resume["expected_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9A-Fa-f]{64}", digest):
        fail("resume.expected_sha256: invalid hash")
    digest = digest.lower()
    selected = {key: string(resume[key], "resume." + key) for key in ("route", "language", "version")}
    selected.update(sha256=digest, object_path=f"objects/{digest}.pdf")
    if not isinstance(data["form_answers"], list):
        fail("form_answers: invalid list")
    answers = []
    for answer in data["form_answers"]:
        shape(answer, {"field", "value"}, {"field", "value"}, "form_answers")
        field = string(answer["field"], "form_answers.field")
        if SENSITIVE_FIELD.search(field):
            fail("form_answers: sensitive field")
        answers.append({"field": field, "value": string(answer["value"], "form_answers.value")})
    if not isinstance(data["submission_evidence"], list) or not data["submission_evidence"]:
        fail("submission_evidence: success reference required")
    evidence = []
    for item in data["submission_evidence"]:
        shape(item, {"kind", "reference", "observed_at"}, {"kind", "reference", "observed_at"}, "submission_evidence")
        if item["kind"] not in ("official_confirmation", "user_confirmation"):
            fail("submission_evidence: unsupported kind")
        reference = string(item["reference"], "submission_evidence.reference")
        if reference.startswith(("https://", "http://")):
            url(reference, "submission_evidence.reference")
        evidence.append({"kind": item["kind"],
                         "reference": reference,
                         "observed_at": timestamp(item["observed_at"], "submission_evidence.observed_at")})
    result = {"schema_version": 1, "record_id": record_id, "application": app,
              "resume": selected, "form_answers": answers, "submission_evidence": evidence}
    if "jd" in data:
        jd = data["jd"]
        shape(jd, {"text", "source_url", "captured_at"}, set(), "jd")
        result["jd"] = {"text": string(jd.get("text"), "jd.text", nullable=True),
                        "source_url": url(jd.get("source_url"), "jd.source_url"),
                        "captured_at": timestamp(jd.get("captured_at"), "jd.captured_at")}
    return result, source


def read_fd(fd, limit):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        fail("file: unsupported type or size")
    with os.fdopen(os.dup(fd), "rb") as handle:
        contents = handle.read(limit + 1)
    if len(contents) > limit:
        fail("file: size limit exceeded")
    return contents


class LocalStore:
    """Anchor every output lookup to directory descriptors; never follow symlinks."""

    def __init__(self, root):
        self.root = root
        self.fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self):
        os.close(self.fd)

    def directory(self, path, create=False):
        current = os.dup(self.fd)
        try:
            for part in path.parts:
                if part in {"", ".", ".."}:
                    fail("output: invalid path")
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=current)
                    except FileExistsError:
                        pass
                try:
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                except FileNotFoundError:
                    return None
                os.close(current)
                current = next_fd
            result, current = current, None
            return result
        finally:
            if current is not None:
                os.close(current)

    def read(self, path, limit):
        parent = self.directory(path.parent)
        if parent is None:
            return None
        try:
            try:
                fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            except FileNotFoundError:
                return None
            try:
                return read_fd(fd, limit)
            finally:
                os.close(fd)
        finally:
            os.close(parent)

    def ensure_ignored(self, path):
        completed = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--quiet", "--", path.as_posix()],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if completed.returncode != 0:
            fail("privacy: input and archive paths must be Git-ignored")

    def put(self, path, contents):
        parent = self.directory(path.parent, create=True)
        temporary = ".pending-" + uuid.uuid4().hex
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(contents)
                    handle.flush()
                    os.fsync(handle.fileno())
                # Linking is atomic and fails if the destination already exists.
                os.link(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                os.fsync(parent)
                return True
            except FileExistsError:
                return False
            finally:
                os.unlink(temporary, dir_fd=parent)
        finally:
            os.close(parent)


def decode(contents):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail("input: duplicate JSON field")
            result[key] = value
        return result
    try:
        return json.loads(contents, object_pairs_hook=unique_keys)
    except (ValueError, UnicodeError):
        fail("input: invalid JSON")


def archive(input_path, root, validate_only=False):
    root = Path(root).resolve()
    repository = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                                capture_output=True, text=True, check=False)
    if repository.returncode or Path(repository.stdout.strip()).resolve() != root:
        fail("root: repository root required")
    absolute_input = Path(os.path.abspath(input_path))
    try:
        relative_input = absolute_input.relative_to(root)
    except ValueError:
        fail("input: must be inside the repository and Git-ignored")
    store = LocalStore(root)
    try:
        store.ensure_ignored(relative_input)
        raw = store.read(relative_input, MAX_JSON)
        if raw is None:
            fail("input: missing file")
        result, source = validate(decode(raw))
        selected_path = Path(source)
        if not selected_path.is_absolute():
            selected_path = root / selected_path
        if selected_path.suffix.lower() != ".pdf":
            fail("resume.path: PDF filename required")
        source_fd = os.open(selected_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            cv = read_fd(source_fd, MAX_CV)
        finally:
            os.close(source_fd)
        digest = result["resume"]["sha256"]
        if hashlib.sha256(cv).hexdigest() != digest:
            fail("resume: selected version hash mismatch")
        object_path = BASE / result["resume"]["object_path"]
        record_path = BASE / "records" / (result["record_id"] + ".json")
        for path in (BASE, object_path.parent, record_path.parent, object_path, record_path):
            store.ensure_ignored(path)
        existing_object = store.read(object_path, MAX_CV)
        if existing_object is not None and hashlib.sha256(existing_object).hexdigest() != digest:
            fail("archive: existing CV object hash mismatch")
        encoded = (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        existing_record = store.read(record_path, MAX_JSON)
        if existing_record is not None:
            if existing_record != encoded:
                fail("archive: record identifier conflict")
            if existing_object is None:
                fail("archive: existing record has no CV object")
        if validate_only:
            return "validated", record_path.as_posix()
        if existing_object is None and not store.put(object_path, cv):
            raced_object = store.read(object_path, MAX_CV)
            if raced_object is None or hashlib.sha256(raced_object).hexdigest() != digest:
                fail("archive: concurrent CV object conflict")
        if existing_record is not None:
            return "unchanged", record_path.as_posix()
        if not store.put(record_path, encoded):
            if store.read(record_path, MAX_JSON) != encoded:
                fail("archive: concurrent record conflict")
            return "unchanged", record_path.as_posix()
        return "created", record_path.as_posix()
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Explicit Git-ignored input JSON inside the repository")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2], help="Repository root")
    parser.add_argument("--validate-only", action="store_true", help="Validate selected inputs and existing targets without writing")
    args = parser.parse_args()
    try:
        status, path = archive(args.input, args.root, args.validate_only)
    except RecordError as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2
    except OSError:
        print("ERROR: filesystem or Git operation failed; check paths and symlinks", file=sys.stderr)
        return 2
    print(json.dumps({"status": status, "record_path": path}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
