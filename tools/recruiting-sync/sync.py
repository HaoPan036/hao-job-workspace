#!/usr/bin/env python3
"""Plan and verify local recruiting-note edits; never apply them."""

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import string
import subprocess
import sys
import unicodedata
from urllib.parse import parse_qsl, quote, unquote, urlsplit, urlunsplit


DEFAULT_CONFIG = "private/recruiting/config.json"
DEFAULT_PATHS = {"history": "private/recruiting/history.md", "queue": "private/recruiting/queue.md"}
EMPLOYMENT_TYPES = ("full_time", "internship")
DEFAULT_MARKDOWN = {
    "history_heading": "## Submitted applications",
    "queue_heading": "## Pending applications",
    "counts_heading": "## Application counts",
    "history_headers": ["Confirmed on", "Submitted on", "Company", "Role", "Region / type", "Status", "Official job", "Note"],
    "count_headers": ["Category", "Submitted", "Target", "Remaining"],
    "employment_labels": {"full_time": "Full time", "internship": "Internship"},
    "total_labels": {"full_time": "All full time", "all": "All submitted"},
    "unknown_date": "Not recorded",
}
COUNTS_MODES = ("strict", "preserve_existing_counts")
MAX_BYTES = 8 * 1024 * 1024
ID_LABEL = r"(?:Job\s*ID|Req(?:uisition)?\s*ID|Job\s*Code|岗位代码|岗位意向\s*ID|ATS|公开编号|ID)"
SECRET = re.compile(
    r"-----BEGIN .*PRIVATE KEY-----|\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,})\b|"
    r"\b(?:password|passwd|api[_ -]?key|access[_ -]?token|authorization|cookie)\s*[:=]|"
    r"\b[STFGM]\d{7}[A-Z]\b|\b\d{17}[0-9Xx]\b|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|"
    r"(?:密码|验证码|身份证|护照号码|手机号|电话号码|家庭住址)\s*[:：]",
    re.I,
)


class SyncError(Exception):
    """Errors contain categories and note positions, never event contents."""


def fail(message):
    raise SyncError(message)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def shape(value, allowed, required, label):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        fail(label + ": invalid fields")


def text(value, label, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        fail(label + ": invalid text")
    if any(ord(char) < 32 for char in value) or SECRET.search(value):
        fail(label + ": unsafe text")
    return value.strip()


def date(value, label, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        fail(label + ": invalid date")
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        fail(label + ": invalid date")
    return value


def timestamp(value, label):
    if value is None:
        return None
    try:
        if not isinstance(value, str) or "T" not in value or dt.datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is None:
            fail(label + ": timezone required")
    except ValueError:
        fail(label + ": invalid timestamp")
    return value


def url(value, label, nullable=False):
    value = text(value, label, nullable)
    if value is None:
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme not in ("https", "http") or not parts.hostname or parts.username or parts.password:
            fail(label + ": invalid URL")
        if any(char.isspace() or char in "<>|" for char in value):
            fail(label + ": unsafe URL")
        for name, _ in parse_qsl(parts.query):
            if re.search(r"token|secret|password|credential|auth|session|key", name, re.I):
                fail(label + ": authenticated URL forbidden")
    except ValueError:
        fail(label + ": invalid URL")
    return value


def identifier(value, label, nullable=False):
    value = text(value, label, nullable)
    if value is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        fail(label + ": invalid identifier")
    return value


def embedded_urls(value, label):
    for found in re.findall(r"https?://[^\s<>]+", value):
        url(found.rstrip("。，；;、）)"), label)


def validate_event(data, config):
    shape(data, ("schema_version", "application_execution", "sync"), ("schema_version", "application_execution", "sync"), "event")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        fail("event: unsupported schema")
    execution = data["application_execution"]
    shape(execution, ("target", "outcome", "result_timestamp", "application_id", "submission_evidence"), ("target", "outcome", "result_timestamp", "application_id", "submission_evidence"), "execution")
    if execution["outcome"] != "success_proven":
        fail("execution: success not proven")
    target = execution["target"]
    shape(target, ("company", "role", "job_id", "official_url", "aliases"), ("company", "role", "job_id", "official_url"), "target")
    selected = {key: text(target[key], "target." + key) for key in ("company", "role")}
    selected["job_id"] = identifier(target["job_id"], "target.job_id", True)
    selected["official_url"] = url(target["official_url"], "target.official_url", True)
    if not selected["job_id"] and not selected["official_url"]:
        fail("target: exact identity required")
    aliases = target.get("aliases", {})
    shape(aliases, ("companies", "job_ids", "official_urls"), (), "aliases")
    clean_aliases = {}
    for key, validate in (("companies", text), ("job_ids", identifier), ("official_urls", url)):
        values = aliases.get(key, [])
        if not isinstance(values, list) or len(values) > 20:
            fail("aliases: invalid list")
        clean_aliases[key] = [validate(value, "aliases." + key) for value in values]
    selected["aliases"] = clean_aliases
    evidence = execution["submission_evidence"]
    if not isinstance(evidence, list) or not evidence or len(evidence) > 20:
        fail("evidence: success reference required")
    cleaned = []
    for item in evidence:
        shape(item, ("kind", "reference", "observed_at"), ("kind", "reference", "observed_at"), "evidence")
        if item["kind"] not in ("user_confirmation", "official_confirmation"):
            fail("evidence: unsupported kind")
        reference = text(item["reference"], "evidence.reference")
        embedded_urls(reference, "evidence.reference")
        cleaned.append({"kind": item["kind"], "reference": reference, "observed_at": timestamp(item["observed_at"], "evidence.observed_at")})
    sync = data["sync"]
    fields = ("confirmed_on", "submitted_on", "region", "employment_type", "location", "status", "note", "material_record_id")
    shape(sync, fields, fields, "sync")
    if not isinstance(sync["region"], str) or sync["region"] not in config.regions or sync["employment_type"] not in EMPLOYMENT_TYPES:
        fail("sync: unsupported category")
    result_sync = {key: text(sync[key], "sync." + key) for key in ("location", "status", "note")}
    embedded_urls(result_sync["note"], "sync.note")
    result_sync.update(confirmed_on=date(sync["confirmed_on"], "sync.confirmed_on"), submitted_on=date(sync["submitted_on"], "sync.submitted_on", True), region=sync["region"], employment_type=sync["employment_type"], material_record_id=identifier(sync["material_record_id"], "sync.material_record_id", True))
    return {"schema_version": 1, "application_execution": {"target": selected, "outcome": "success_proven", "result_timestamp": timestamp(execution["result_timestamp"], "execution.result_timestamp"), "application_id": identifier(execution["application_id"], "execution.application_id", True), "submission_evidence": cleaned}, "sync": result_sync}


def repository(root):
    root = Path(root).resolve()
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if result.returncode or Path(result.stdout.strip()).resolve() != root:
        fail("root: repository root required")
    return root


def safe_path(root, value, private=False):
    candidate = Path(value)
    if ".." in candidate.parts:
        fail("path: traversal forbidden")
    path = candidate if candidate.is_absolute() else root / candidate
    try:
        relative = path.relative_to(root)
    except ValueError:
        fail("path: outside repository")
    if not relative.parts:
        fail("path: repository root is not a file destination")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            fail("path: symlink forbidden")
    if private:
        result = subprocess.run(["git", "-C", str(root), "check-ignore", "--quiet", "--", relative.as_posix()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--", relative.as_posix()], capture_output=True)
        if result.returncode or tracked.returncode or tracked.stdout:
            fail("privacy: execution artifacts must be ignored and untracked")
    return path


def read_bytes(path):
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        fail("file: missing, unsupported, or too large")
    return path.read_bytes()


def decode(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail("JSON: duplicate key")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=pairs)
    except (ValueError, UnicodeError):
        fail("JSON: invalid document")


class Config:
    """Validated local formatting and region choices; no recruiting state."""

    def __init__(self, data, path, sha256):
        self.path, self.sha256 = path, sha256
        self.paths = data["paths"]
        self.files = (self.paths["history"], self.paths["queue"])
        self.history, self.queue = self.files
        self.regions = data["regions"]
        self.markdown = data["markdown"]
        self.categories = tuple(self.category(region, employment) for region in self.regions for employment in EMPLOYMENT_TYPES)
        self.full_time_categories = tuple(self.category(region, "full_time") for region in self.regions)
        self.totals = tuple(self.markdown["total_labels"][key] for key in ("full_time", "all"))

    def category(self, region, employment):
        return self.regions[region]["label"] + " / " + self.markdown["employment_labels"][employment]


def config_text(value, label):
    value = text(value, label)
    if any(char in value for char in "|\\[]\x60"):
        fail(label + ": unsupported Markdown text")
    return value


def load_config(root, config_path=DEFAULT_CONFIG):
    path = safe_path(root, config_path, True)
    raw = read_bytes(path)
    data = decode(raw)
    shape(data, ("schema_version", "paths", "regions", "markdown"), ("schema_version", "regions"), "config")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        fail("config: unsupported schema")
    paths = data.get("paths", DEFAULT_PATHS)
    shape(paths, DEFAULT_PATHS, DEFAULT_PATHS, "config.paths")
    cleaned_paths = {}
    for key, value in paths.items():
        if not isinstance(value, str) or Path(value).is_absolute() or "\n" in value or "\r" in value or "\x00" in value:
            fail("config.paths: relative file path required")
        resolved = safe_path(root, value, True)
        if resolved.suffix.lower() != ".md":
            fail("config.paths: Markdown file required")
        cleaned_paths[key] = resolved.relative_to(root).as_posix()
    if len(set(cleaned_paths.values())) != 2 or path in [root / item for item in cleaned_paths.values()]:
        fail("config.paths: distinct files required")
    regions = data["regions"]
    if not isinstance(regions, dict) or not regions or len(regions) > 50:
        fail("config.regions: nonempty object required")
    cleaned_regions, seen_aliases = {}, {}
    for key, item in regions.items():
        identifier(key, "config.region")
        shape(item, ("label", "aliases"), ("label", "aliases"), "config.region")
        label = config_text(item["label"], "config.region.label")
        aliases = item["aliases"]
        if not isinstance(aliases, list) or len(aliases) > 50:
            fail("config.region.aliases: invalid list")
        cleaned = []
        for alias in [label] + aliases:
            alias = config_text(alias, "config.region.alias")
            norm = normalize(alias)
            if norm in seen_aliases and seen_aliases[norm] != key:
                fail("config.regions: conflicting aliases")
            seen_aliases[norm] = key
            if norm not in {normalize(value) for value in cleaned}:
                cleaned.append(alias)
        cleaned_regions[key] = {"label": label, "aliases": cleaned}
    supplied = data.get("markdown", {})
    shape(supplied, DEFAULT_MARKDOWN, (), "config.markdown")
    markdown = dict(DEFAULT_MARKDOWN)
    markdown.update(supplied)
    for key in ("history_heading", "queue_heading", "counts_heading"):
        markdown[key] = config_text(markdown[key], "config.markdown." + key)
        if not markdown[key].startswith("## ") or markdown[key].startswith("### "):
            fail("config.markdown: level-two heading required")
    if len({markdown[key] for key in ("history_heading", "queue_heading", "counts_heading")}) != 3:
        fail("config.markdown: distinct headings required")
    for key, size in (("history_headers", 8), ("count_headers", 4)):
        values = markdown[key]
        if not isinstance(values, list) or len(values) != size:
            fail("config.markdown: invalid header width")
        markdown[key] = [config_text(value, "config.markdown." + key) for value in values]
        if len(set(markdown[key])) != size:
            fail("config.markdown: duplicate headers")
    for key, required in (("employment_labels", EMPLOYMENT_TYPES), ("total_labels", ("full_time", "all"))):
        shape(markdown[key], required, required, "config.markdown." + key)
        markdown[key] = {name: config_text(value, "config.markdown." + key) for name, value in markdown[key].items()}
    markdown["unknown_date"] = config_text(markdown["unknown_date"], "config.markdown.unknown_date")
    if markdown["employment_labels"]["full_time"] == markdown["employment_labels"]["internship"]:
        fail("config.markdown: distinct employment labels required")
    config = Config({"paths": cleaned_paths, "regions": cleaned_regions, "markdown": markdown}, path.relative_to(root).as_posix(), digest(raw))
    if len(set(config.categories + config.totals)) != len(config.categories + config.totals):
        fail("config: conflicting category or total labels")
    return config


def contains_label(value, label):
    # Match names as tokens so "US" does not match "Australia".
    return re.search(r"(?<![\w])" + re.escape(normalize(label)) + r"(?![\w])", normalize(value)) is not None


def notes(root, config):
    result = {}
    for name in config.files:
        raw = read_bytes(safe_path(root, name, True))
        try:
            value = raw.decode("utf-8")
        except UnicodeError:
            fail("notes: UTF-8 required")
        if "\r" in value or not value.endswith("\n"):
            fail("notes: LF with final newline required")
        result[name] = value
    return result

def section(lines, heading, name):
    matches = [i for i, line in enumerate(lines) if line.rstrip("\n") == heading]
    if len(matches) != 1:
        fail(name + ": one section heading required")
    start = matches[0] + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return start, end


def markdown_text(value):
    return re.sub(r"\\([" + re.escape(string.punctuation) + r"])", r"\1", value)


def cells(line):
    if not line.strip().startswith("|") or not line.strip().endswith("|"):
        return None
    parts, current, escaped = [], [], False
    for char in line.strip()[1:-1]:
        if escaped:
            current.extend(("\\", char))
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if escaped:
        current.append("\\")
    parts.append("".join(current).strip())
    return [markdown_text(part) for part in parts]


def category_facts(value, config):
    value = normalize(value)
    internship = bool(re.search(r"实习|\bintern(?:ship)?\b|byteintern", value)) or contains_label(value, config.markdown["employment_labels"]["internship"])
    full_time = bool(re.search(r"全职|full[ -]?time|\bpermanent\b|\bgraduate\b|校招|校园招聘", value)) or contains_label(value, config.markdown["employment_labels"]["full_time"])
    regions = {key for key, item in config.regions.items() if any(contains_label(value, alias) for alias in item["aliases"])}
    selected = re.split(r"[（(]", value, maxsplit=1)[0]
    if len(regions) > 1 and selected != value:
        regions = {key for key, item in config.regions.items() if any(contains_label(selected, alias) for alias in item["aliases"])}
    return internship, full_time, regions

def classify(value, position, config):
    internship, full_time, regions = category_facts(value, config)
    if internship == full_time or len(regions) != 1:
        fail(f"history: unclassified or conflicting category at line {position}")
    return config.category(next(iter(regions)), "internship" if internship else "full_time")

def history_rows(value, config):
    lines = value.splitlines(keepends=True)
    start, end = section(lines, config.markdown["history_heading"], "history")
    meaningful = [i for i in range(start, end) if lines[i].strip()]
    if len(meaningful) < 2 or cells(lines[meaningful[0]]) != config.markdown["history_headers"]:
        fail("history: unsupported table header")
    separator = cells(lines[meaningful[1]])
    if not separator or len(separator) != 8 or not all(re.fullmatch(r":?-{3,}:?", item) for item in separator):
        fail("history: unsupported table separator")
    rows = []
    for i in meaningful[2:]:
        row = cells(lines[i])
        if row is None or len(row) != 8:
            fail(f"history: unsupported row at line {i + 1}")
        date(row[0], "history.confirmed_on")
        if row[1] != config.markdown["unknown_date"]:
            date(row[1], "history.submitted_on")
        rows.append({"line": i + 1, "cells": row})
    return rows, meaningful[1] + 1


def count_rows(rows, config):
    counts = dict.fromkeys(config.categories, 0)
    issues = []
    for row in rows:
        try:
            counts[classify(row["cells"][4], row["line"], config)] += 1
        except SyncError as exc:
            issues.append(str(exc))
    return counts, issues


def summaries(value, config):
    result = {}
    lines = value.splitlines(keepends=True)
    start, end = section(lines, config.markdown["counts_heading"], "counts")
    meaningful = [i for i in range(start, end) if lines[i].strip()]
    if len(meaningful) < 2 or cells(lines[meaningful[0]]) != config.markdown["count_headers"]:
        fail("counts: unsupported table header")
    separator = cells(lines[meaningful[1]])
    if not separator or len(separator) != 4 or not all(re.fullmatch(r":?-{3,}:?", item) for item in separator):
        fail("counts: unsupported table separator")
    for i in meaningful[2:]:
        row = cells(lines[i])
        if not row or len(row) != 4 or row[0] not in config.categories + config.totals or row[0] in result or not row[1].isdigit():
            fail(f"counts: invalid summary at line {i + 1}")
        if row[2].isdigit():
            if not re.fullmatch(r"-?\d+", row[3]):
                fail("counts: numeric remaining required")
        elif row[2:] != ["—", "—"]:
            fail("counts: unset target and remaining must both be em dashes")
        result[row[0]] = (i, row)
    if set(result) != set(config.categories + config.totals):
        fail("counts: required summary rows missing")
    for total, members in ((config.totals[0], config.full_time_categories), (config.totals[1], config.categories)):
        targets = [result[key][1][2] for key in members]
        expected = str(sum(int(value) for value in targets)) if all(value.isdigit() for value in targets) else "—"
        if result[total][1][2] != expected:
            fail("counts: target totals conflict")
    return result

def rendered_counts(value, counts, config):
    table = summaries(value, config)
    expected = dict(counts)
    expected[config.totals[0]] = sum(counts[key] for key in config.full_time_categories)
    expected[config.totals[1]] = sum(counts.values())
    lines = value.splitlines(keepends=True)
    changed = []
    for key, (i, row) in table.items():
        updated = row[:]
        updated[1] = str(expected[key])
        if row[2].isdigit():
            updated[3] = str(int(row[2]) - expected[key])
        if updated != row:
            lines[i] = "| " + " | ".join(updated) + " |\n"
            changed.append(i + 1)
    return "".join(lines), changed

def baseline_counts(value, rows, config):
    table = summaries(value, config)
    counts = {key: int(table[key][1][1]) for key in config.categories}
    if rendered_counts(value, counts, config)[1] or sum(counts.values()) != len(rows):
        fail("counts: legacy baseline arithmetic or row count mismatch; inspect original plan and reconcile")
    known, issues = count_rows(rows, config)
    if any(known[key] > counts[key] for key in config.categories) or sum(counts[key] - known[key] for key in config.categories) != len(issues):
        fail("counts: legacy baseline conflicts with classified rows")
    return counts, issues


def links(value):
    result = []
    for match in re.finditer(r"\]\((?=https?://)", value):
        start, cursor, depth = match.end(), match.end(), 1
        while cursor < len(value) and depth:
            if value[cursor].isspace():
                break
            if value[cursor] == "(":
                depth += 1
            elif value[cursor] == ")":
                depth -= 1
            cursor += 1
        if depth == 0:
            result.append(value[start:cursor - 1])
    return result


def canonical_url(value):
    parts = urlsplit(value)
    def escapes(component):
        def replacement(match):
            char = chr(int(match.group(1), 16))
            return char if char.isascii() and (char.isalnum() or char in "-._~()") else "%" + match.group(1).upper()
        normalized = re.sub(r"%([0-9A-Fa-f]{2})", replacement, component)
        return quote(normalized, safe="/?:@!$&'()*+,;=#[]%")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), escapes(parts.path).rstrip("/"), escapes(parts.query), escapes(parts.fragment)))


def labeled_ids(value):
    return set(re.findall(r"(?:^|[；;]\s*)" + ID_LABEL + r"\s*[:：]?\s*`?([A-Za-z0-9][A-Za-z0-9_-]*)", value, re.I))


def has_id(value, job_id):
    return re.search(r"(?<![A-Za-z0-9_-])" + re.escape(job_id) + r"(?![A-Za-z0-9_-])", value) is not None


def title_ids(value):
    candidates = re.findall(r"[（(]`?([A-Za-z0-9][A-Za-z0-9_-]*)`?[）)]", value)
    return {item for item in candidates if any(char.isdigit() for char in item) and (any(char.isalpha() for char in item) or len(item) >= 5)}


def url_has_id(value, job_id):
    parts = urlsplit(value)
    segments = unquote(parts.path + "/" + parts.fragment).split("/")
    if any(segment == job_id or segment.endswith("_" + job_id) or (job_id.isdigit() and segment.startswith(job_id + "-")) for segment in segments):
        return True
    return any(re.fullmatch(r"(?:job_?id|jobAdId|id|positionId|positionIntentionId|advertisementId|req(?:uisition)?_?id|gh_jid|jobCode)", key, re.I) and val == job_id for key, val in parse_qsl(parts.query))


def matches(company, role, urls, ids, target):
    names = [target["company"]] + target["aliases"]["companies"]
    if normalize(company) not in {normalize(name) for name in names}:
        return False
    sought_ids = [value for value in [target["job_id"]] + target["aliases"]["job_ids"] if value]
    if any(value in ids or value in title_ids(role) or any(url_has_id(link, value) for link in urls) for value in sought_ids):
        return True
    sought_urls = [value for value in [target["official_url"]] + target["aliases"]["official_urls"] if value]
    url_match = normalize(role) == normalize(target["role"]) and bool({canonical_url(link) for link in urls} & {canonical_url(link) for link in sought_urls})
    if url_match and sought_ids and ids and not set(sought_ids).intersection(ids):
        fail("identity: explicit job IDs conflict; verified aliases required")
    return url_match


def matching_history(rows, target):
    result = []
    for row in rows:
        c = row["cells"]
        if matches(c[2], c[3], links(c[6]), labeled_ids(c[7]), target):
            result.append(row)
    if len(result) > 1:
        fail("identity: multiple history rows match")
    return result


def queue_title(value):
    # Split before decoding so an escaped pipe inside a name stays literal.
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char in "｜|":
            return value[:index], value[index + 1:]
    return None


def queue_entries(value, config):
    lines = value.splitlines(keepends=True)
    start, end = section(lines, config.markdown["queue_heading"], "queue")
    entries = []
    for i in range(start, end):
        if not re.match(r"^- \[[ xX]\]", lines[i]):
            continue
        match = re.match(r"^- \[ \] #p[012]\s+\*\*(.+?)\*\*(.*)$", lines[i].rstrip("\n"))
        title = queue_title(match.group(1)) if match else None
        supported = title is not None
        company, role = "", ""
        if supported:
            company, role = title
        else:
            legacy = re.match(r"^- \[[ xX]\](?: #p[012])?\s+\*\*(.+?)\*\*\s*·\s*([^·]+)", lines[i])
            if legacy:
                role, company = legacy.group(1), legacy.group(2)
        stop = i + 1
        while stop < end:
            if lines[stop].startswith(("  ", "\t")):
                stop += 1
            elif not lines[stop].strip():
                following = stop + 1
                while following < end and not lines[following].strip():
                    following += 1
                if following < end and lines[following].startswith(("  ", "\t")):
                    stop = following
                else:
                    break
            else:
                break
        block = "".join(lines[i:stop])
        primary = re.split(r"[；;]", lines[i], maxsplit=1)[0]
        ids = set(re.findall(r"(?:^|·\s*)" + ID_LABEL + r"\s*[:：]?\s*`?([A-Za-z0-9][A-Za-z0-9_-]*)", primary, re.I))
        primary_urls = links(primary)
        for child in lines[i + 1:stop]:
            field = re.match(r"^\s+-\s+\*\*(?:编号|岗位编号|Job ID|Req ID)[：:]\*\*\s*`?([A-Za-z0-9][A-Za-z0-9_-]*)", child, re.I)
            if field:
                ids.add(field.group(1))
            if re.match(r"^\s+-\s+(?:\*\*)?(?:Official job|Official URL|Job link|官方岗位|官方入口|官方链接|官方申请|申请入口|投递入口|岗位链接|链接|投递|申请|岗位)[：:]", child, re.I):
                primary_urls.extend(links(child))
        entries.append({"start": i, "end": stop, "line": i + 1, "company": markdown_text(company).strip(), "role": markdown_text(role).strip(), "urls": primary_urls, "ids": ids, "supported": supported, "block": block, "primary": lines[i]})
    return entries


def matching_queue(entries, target):
    result = []
    for entry in entries:
        matched = matches(entry["company"], entry["role"], entry["urls"], entry["ids"], target)
        if not entry["supported"] and not entry["company"]:
            ids = [target["job_id"]] + target["aliases"]["job_ids"]
            matched = normalize(target["company"]) in normalize(markdown_text(entry["primary"])) and any(job_id and has_id(entry["primary"], job_id) for job_id in ids)
        if matched:
            if not entry["supported"]:
                fail(f"queue: target has unsupported structure at line {entry['line']}")
            result.append(entry)
    if len(result) > 1:
        fail("identity: multiple pending tasks match")
    return result


def event_category(event, config):
    sync = event["sync"]
    return config.category(sync["region"], sync["employment_type"])

def existing_conflicts(row, event, config, counts_mode="strict"):
    c = row["cells"]
    try:
        category = classify(c[4], row["line"], config)
    except SyncError:
        if counts_mode == "strict":
            raise
        intern, full, regions = category_facts(c[4], config)
        sync = event["sync"]
        if (intern and full) or len(regions) > 1 or (intern and sync["employment_type"] != "internship") or (full and sync["employment_type"] != "full_time") or (regions and sync["region"] not in regions):
            fail("identity: existing employment or region conflicts")
    else:
        if category != event_category(event, config):
            fail("identity: existing employment or region conflicts")
    submitted = event["sync"]["submitted_on"]
    if submitted is not None and c[1] != config.markdown["unknown_date"] and c[1] != submitted:
        fail("identity: existing submission date conflicts")
    application_id = event["application_execution"]["application_id"]
    observed = re.findall(r"(?:^|[；;]\s*)Application ID\s*[:：]?\s*\x60?([A-Za-z0-9][A-Za-z0-9_-]*)", c[7], re.I)
    if application_id and observed and application_id not in observed:
        fail("identity: existing application ID conflicts")

def md(value):
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


def new_row(event, config):
    ex = event["application_execution"]
    target, sync = ex["target"], event["sync"]
    nature = config.markdown["employment_labels"][sync["employment_type"]]
    location = sync["location"] + " / " + nature
    if classify(location, 0, config) != event_category(event, config):
        fail("sync: location conflicts with declared category")
    note = []
    if target["job_id"]:
        note.append("Job ID `" + target["job_id"] + "`")
    if ex["application_id"]:
        note.append("Application ID `" + ex["application_id"] + "`")
    note.append(md(sync["note"]))
    if sync["material_record_id"]:
        note.append("材料记录 `" + sync["material_record_id"] + "`（归档结果另行核验）")
    link = "[官方岗位](" + target["official_url"].replace("(", "%28").replace(")", "%29") + ")" if target["official_url"] else config.markdown["unknown_date"]
    row = [sync["confirmed_on"], sync["submitted_on"] or config.markdown["unknown_date"], md(target["company"]), md(target["role"]), md(location), md(sync["status"]), link, "；".join(note)]
    return "| " + " | ".join(row) + " |\n"


def patch_for(before, after):
    changes = ["*** Begin Patch\n"]
    for path in before:
        if before[path] == after[path]:
            continue
        changes.append("*** Update File: " + path + "\n")
        diff = list(difflib.unified_diff(before[path].splitlines(keepends=True), after[path].splitlines(keepends=True), n=3))
        for line in diff[2:]:
            changes.append("@@\n" if line.startswith("@@ ") else line)
    changes.append("*** End Patch\n")
    return "".join(changes)


def review_locations(before, event, config, changed=False):
    target = event["application_execution"]["target"]
    needles = [target["company"]] + target["aliases"]["companies"]
    needles += [value for value in [target["job_id"]] + target["aliases"]["job_ids"] if value]
    result = []
    for path, value in before.items():
        for i, line in enumerate(value.splitlines(), 1):
            date_metadata = changed and (line.startswith("updated:") or re.match(r"^(?:截至|As of)\s*\x60?\d{4}-\d{2}-\d{2}", line))
            if date_metadata or (not line.startswith(("|", "- [", "  ", "\t")) and any(needle in line for needle in needles)):
                result.append({"path": path, "line": i})
    return result

def plan_changes(root, event, config, counts_mode="strict"):
    if counts_mode not in COUNTS_MODES:
        fail("counts: unsupported mode")
    before = notes(root, config)
    rows, insert_at = history_rows(before[config.history], config)
    if counts_mode == "preserve_existing_counts":
        counts, issues = baseline_counts(before[config.history], rows, config)
    else:
        counts, issues = count_rows(rows, config)
        if issues:
            fail("\n".join(issues))
    summaries(before[config.history], config)
    target = event["application_execution"]["target"]
    existing = matching_history(rows, target)
    pending = matching_queue(queue_entries(before[config.queue], config), target)
    after = dict(before)
    if existing:
        existing_conflicts(existing[0], event, config, counts_mode)
    else:
        lines = after[config.history].splitlines(keepends=True)
        lines.insert(insert_at, new_row(event, config))
        after[config.history] = "".join(lines)
        counts[event_category(event, config)] += 1
    if pending:
        lines = after[config.queue].splitlines(keepends=True)
        entry = pending[0]
        del lines[entry["start"]:entry["end"]]
        after[config.queue] = "".join(lines)
    after[config.history], _ = rendered_counts(after[config.history], counts, config)
    return before, after, counts, issues


def create_plan(root, input_path, out_path, counts_mode="strict", config_path=DEFAULT_CONFIG):
    root = repository(root)
    config = load_config(root, config_path)
    event = validate_event(decode(read_bytes(safe_path(root, input_path, True))), config)
    out = safe_path(root, out_path, True)
    if out.exists():
        fail("output: choose a new plan directory")
    for name in ("plan.json", "changes.patch"):
        safe_path(root, out / name, True)
    before, after, counts, issues = plan_changes(root, event, config, counts_mode)
    patch = patch_for(before, after).encode("utf-8")
    plan = {"schema_version": 1, "config": {"path": config.path, "sha256": config.sha256}, "event": event, "counts_mode": counts_mode, "legacy_unclassified": len(issues), "files": [{"path": name, "before_sha256": digest(before[name].encode()), "after_sha256": digest(after[name].encode())} for name in config.files], "patch": "changes.patch", "patch_sha256": digest(patch), "counts": counts, "review_locations": review_locations(before, event, config, before != after)}
    out.mkdir(parents=True, mode=0o700)
    for name, data in (("changes.patch", patch), ("plan.json", (json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode())):
        fd = os.open(out / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    return plan


def load_plan(root, plan_path, config):
    path = safe_path(root, plan_path, True)
    plan = decode(read_bytes(path))
    fields = ("schema_version", "config", "event", "counts_mode", "legacy_unclassified", "files", "patch", "patch_sha256", "counts", "review_locations")
    shape(plan, fields, fields, "plan")
    if type(plan["schema_version"]) is not int or plan["schema_version"] != 1 or plan["patch"] != "changes.patch":
        fail("plan: unsupported schema")
    if plan["config"] != {"path": config.path, "sha256": config.sha256}:
        fail("config: stale plan; replan from current configuration")
    plan["event"] = validate_event(plan["event"], config)
    if plan["counts_mode"] not in COUNTS_MODES or type(plan["legacy_unclassified"]) is not int or plan["legacy_unclassified"] < 0:
        fail("plan: invalid counts mode")
    if not isinstance(plan["files"], list) or len(plan["files"]) != len(config.files):
        fail("plan: invalid snapshots")
    for entry, name in zip(plan["files"], config.files):
        shape(entry, ("path", "before_sha256", "after_sha256"), ("path", "before_sha256", "after_sha256"), "plan.snapshot")
        if entry["path"] != name or not all(isinstance(entry[key], str) and re.fullmatch("[0-9a-f]{64}", entry[key]) for key in ("before_sha256", "after_sha256")):
            fail("plan: invalid snapshots")
    patch = read_bytes(safe_path(root, path.parent / "changes.patch", True))
    if digest(patch) != plan["patch_sha256"]:
        fail("plan: patch fingerprint mismatch")
    if not isinstance(plan["counts"], dict) or set(plan["counts"]) != set(config.categories) or not all(type(value) is int and value >= 0 for value in plan["counts"].values()):
        fail("plan: invalid expected counts")
    return plan


def check_plan(root, plan_path, verify=False, config_path=DEFAULT_CONFIG):
    root = repository(root)
    config = load_config(root, config_path)
    plan = load_plan(root, plan_path, config)
    current = notes(root, config)
    for entry in plan["files"]:
        expected = entry["after_sha256" if verify else "before_sha256"]
        if digest(current[entry["path"]].encode()) != expected:
            fail("snapshot: post-apply mismatch; inspect and replan" if verify else "snapshot: stale plan; replan from current notes")
    if verify:
        rows, _ = history_rows(current[config.history], config)
        if plan["counts_mode"] == "preserve_existing_counts":
            counts, issues = baseline_counts(current[config.history], rows, config)
            if len(issues) != plan["legacy_unclassified"]:
                fail("verify: legacy classification count changed")
        else:
            counts, issues = count_rows(rows, config)
            if issues:
                fail("\n".join(issues))
        if counts != plan["counts"] or rendered_counts(current[config.history], counts, config)[1]:
            fail("verify: counts do not reconcile")
        target = plan["event"]["application_execution"]["target"]
        existing = matching_history(rows, target)
        if len(existing) != 1 or matching_queue(queue_entries(current[config.queue], config), target):
            fail("verify: target is not uniquely recorded and removed")
        existing_conflicts(existing[0], plan["event"], config, plan["counts_mode"])
    return plan


def audit(root, config_path=DEFAULT_CONFIG):
    root = repository(root)
    config = load_config(root, config_path)
    current = notes(root, config)
    rows, _ = history_rows(current[config.history], config)
    counts, issues = count_rows(rows, config)
    summaries(current[config.history], config)
    if not issues:
        _, changed = rendered_counts(current[config.history], counts, config)
        issues.extend(f"counts: mismatch at line {line}" for line in changed)
    issues.extend(f"queue: unsupported task at line {entry['line']}" for entry in queue_entries(current[config.queue], config) if not entry["supported"])
    return {"history_rows": len(rows), "counts": counts, "issues": issues}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "check", "verify", "audit"):
        sub = commands.add_parser(command)
        sub.add_argument("--root", default=Path(__file__).resolve().parents[2])
        sub.add_argument("--config", default=DEFAULT_CONFIG)
        if command == "plan":
            sub.add_argument("--input", required=True)
            sub.add_argument("--out", required=True)
            sub.add_argument("--counts-mode", choices=COUNTS_MODES, default="strict")
        elif command in ("check", "verify"):
            sub.add_argument("--plan", required=True)
        elif command == "audit":
            sub.add_argument("--json", action="store_true", help="Print existing classified counts and issues as read-only JSON")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = create_plan(args.root, args.input, args.out, args.counts_mode, args.config)
            changed = sum(entry["before_sha256"] != entry["after_sha256"] for entry in result["files"])
            print(f"PLAN_READY changed_files={changed} review_locations={len(result['review_locations'])} counts_mode={result['counts_mode']}")
        elif args.command in ("check", "verify"):
            result = check_plan(args.root, args.plan, args.command == "verify", args.config)
            print(("VERIFY_PASS" if args.command == "verify" else "CHECK_PASS") + " counts_mode=" + result["counts_mode"])
        else:
            result = audit(args.root, args.config)
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                for issue in result["issues"]:
                    print(issue)
                print(f"AUDIT_{'REVISE' if result['issues'] else 'PASS'} history_rows={result['history_rows']}")
            return 1 if result["issues"] else 0
        if result["counts_mode"] == "preserve_existing_counts":
            print(f"LEGACY_WARNING historical categories not fully reclassified; unresolved_rows={result['legacy_unclassified']}")
        return 0
    except SyncError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError, TypeError):
        print("operation: local file or input error", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
