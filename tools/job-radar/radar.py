#!/usr/bin/env python3
"""Offline helpers for evaluated jobs: deduplicate, guard queue writes, audit sync.

The host Agent searches and verifies official postings. This script makes no
network requests and does not establish that a supplied assessment is true.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, fields
import html
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
import urllib.parse


AUTO_QUEUE_START = "<!-- job-radar:auto:start -->"
AUTO_QUEUE_END = "<!-- job-radar:auto:end -->"
SYNC_DISPOSITIONS = {"queued", "manual_review", "excluded", "duplicate"}
LEVELS = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
APPLY_ACTIONS = {"APPLY_NOW", "APPLY_BATCH"}


# These are the existing Job Radar dossier fields, not a second assessment model.
@dataclass(frozen=True)
class JobIdentity:
    company: str
    title: str
    job_id: str
    official_url: str
    location: str
    employment_type: str
    status: str


@dataclass(frozen=True)
class JobVerification:
    status: str
    reasons: tuple[str, ...] = ()
    checked_at: str = ""


@dataclass(frozen=True)
class FeasibilityAssessment:
    status: str
    reasons: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityMatch:
    level: str = "UNKNOWN"
    supporting_evidence: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()


@dataclass(frozen=True)
class StrategicPriority:
    level: str = "UNKNOWN"
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApplicationRoute:
    routes: tuple[str, ...] = ()
    resume_variant: str = "UNKNOWN"
    narrative: str = "UNKNOWN"
    project_order: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recommendation:
    action: str
    rationale: tuple[str, ...] = ()


@dataclass(frozen=True)
class Provenance:
    fetched_at: str
    source: str
    evaluator: str = "host-agent"
    version: str = "2.0"


@dataclass(frozen=True)
class RequirementEvidence:
    required: tuple[str, ...] = ()
    preferred: tuple[str, ...] = ()
    nice_to_have: tuple[str, ...] = ()
    unclassified: tuple[str, ...] = ()


@dataclass(frozen=True)
class JobDossier:
    job_identity: JobIdentity
    verification: JobVerification
    feasibility: FeasibilityAssessment
    capability_match: CapabilityMatch
    strategic_priority: StrategicPriority
    application_route: ApplicationRoute
    recommendation: Recommendation
    provenance: Provenance
    requirements: RequirementEvidence = RequirementEvidence()


@dataclass(frozen=True)
class RecruitingSyncValidation:
    evaluated_count: int
    queued_count: int
    manual_review_count: int
    excluded_count: int
    duplicate_count: int
    orphan_count: int
    errors: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.orphan_count == 0 and not self.errors


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalize_for_match(value: str) -> str:
    return unicodedata.normalize("NFKC", clean_text(value)).casefold()


def normalize_url_component(value: str, safe: str) -> str:
    # Only unreserved escapes are interchangeable with literal URI characters.
    # Keep encoded delimiters such as %2F and %3F encoded: they may be job IDs.
    unreserved = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"

    def normalize_escape(match: re.Match) -> str:
        character = chr(int(match.group(0)[1:], 16))
        return character if character in unreserved else match.group(0).upper()

    value = re.sub(r"%[0-9A-Fa-f]{2}", normalize_escape, value)
    return urllib.parse.quote(value, safe=safe + "%")


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    # Preserve meaningful query order, repeated keys and encoded delimiters.
    # Do not round-trip through parse_qsl, which treats '+' as a space.
    filtered = []
    for part in parsed.query.split("&"):
        key = urllib.parse.unquote(part.partition("=")[0]).lower()
        if key.startswith("utm_") or key in {"spm", "from", "source"}:
            continue
        filtered.append(normalize_url_component(part, "/?:@!$'*+,;=-._~"))
    return urllib.parse.urlunsplit((
        parsed.scheme.lower(), parsed.netloc.lower(),
        normalize_url_component(parsed.path.rstrip("/"), "/:@!$&'*+,;=-._~"),
        "&".join(filtered), normalize_url_component(parsed.fragment, "/?:@!$&'*+,;=-._~")))


def markdown_urls(text: str) -> list[str]:
    """Read inline HTTP link destinations, including balanced parentheses."""
    urls = []
    for match in re.finditer(r"\]\((<?)(https?://)", text):
        start = match.end() - len(match.group(2))
        if match.group(1):
            end = text.find(">", start)
            if end >= 0:
                urls.append(text[start:end])
            continue
        depth = 0
        for end in range(start, len(text)):
            character = text[end]
            if character.isspace():
                break
            if character == "(":
                depth += 1
            elif character == ")":
                if depth == 0:
                    urls.append(text[start:end])
                    break
                depth -= 1
    return urls


def normalize_company(value: str) -> str:
    value = normalize_for_match(value)
    for suffix in (r"\bpte\.?\s*ltd\.?\b", r"\bprivate\s+limited\b",
                   r"\blimited\b", r"\bltd\.?\b", r"\binc\.?\b", r"\bllc\b",
                   r"股份有限公司", r"有限责任公司", r"有限公司"):
        value = re.sub(suffix, " ", value, flags=re.I)
    return "".join(character for character in value if character.isalnum())


def normalize_location(value: str) -> str:
    # No country alias or preferred market is hard-coded into the public helper.
    return "".join(character for character in normalize_for_match(value)
                   if character.isalnum())


def semantic_job_fingerprint(identity: JobIdentity) -> str:
    company = normalize_company(identity.company)
    location = normalize_location(identity.location)
    title = normalize_for_match(identity.title)
    for removable in (identity.company, identity.location):
        if removable:
            title = title.replace(normalize_for_match(removable), " ")
    title = "".join(character for character in title if character.isalnum())
    if not company or not location or not title:
        return ""
    return "\0".join((company, title, location))


def deduplicate_dossiers(rows: list[JobDossier]) -> list[JobDossier]:
    """Use normalized URL and company/title/location as duplicate leads.

    Distinct explicit requisition IDs are retained even with the same title.
    The Agent resolves aliases and ambiguous repostings against official pages.
    """
    unique: list[JobDossier] = []
    seen_urls: set[str] = set()
    seen_ids: set[tuple[str, str]] = set()
    fingerprints: dict[str, list[str]] = {}
    for row in rows:
        identity = row.job_identity
        url = normalize_url(identity.official_url)
        key = (normalize_company(identity.company), identity.job_id)
        fingerprint = semantic_job_fingerprint(identity)
        previous_ids = fingerprints.get(fingerprint, []) if fingerprint else []
        ambiguous_same_role = bool(previous_ids) and (
            not identity.job_id or "" in previous_ids or identity.job_id in previous_ids
        )
        if ((url and url in seen_urls) or (all(key) and key in seen_ids)
                or ambiguous_same_role):
            continue
        unique.append(row)
        if url:
            seen_urls.add(url)
        if all(key):
            seen_ids.add(key)
        if fingerprint:
            fingerprints.setdefault(fingerprint, []).append(identity.job_id)
    return unique


def recommend_action(verification: str, feasibility: str,
                     capability: str, strategy: str) -> str:
    """Migrated ordered decision table; never add the dimensions numerically."""
    if verification == "REJECTED" or feasibility == "HARD_FAIL":
        return "SKIP"
    if verification != "VERIFIED" or feasibility != "PASS":
        return "MANUAL_REVIEW"
    if capability not in LEVELS or strategy not in LEVELS:
        return "MANUAL_REVIEW"
    if "UNKNOWN" in {capability, strategy}:
        return "MANUAL_REVIEW"
    if "LOW" in {capability, strategy}:
        return "WATCHLIST"
    return "APPLY_NOW" if capability == strategy == "HIGH" else "APPLY_BATCH"


def is_auto_queue_eligible(row: JobDossier) -> bool:
    identity = row.job_identity
    parsed = urllib.parse.urlsplit(identity.official_url)
    expected = recommend_action(row.verification.status, row.feasibility.status,
                                row.capability_match.level, row.strategic_priority.level)
    return bool(
        row.verification.status == "VERIFIED"
        and row.feasibility.status == "PASS" and not row.feasibility.unknowns
        and row.recommendation.action in APPLY_ACTIONS and expected in APPLY_ACTIONS
        and identity.status == "OPEN"
        and all((identity.company, identity.title, identity.location,
                 identity.employment_type, row.verification.checked_at,
                 row.verification.reasons, row.capability_match.supporting_evidence,
                 row.strategic_priority.reasons, row.recommendation.rationale))
        and parsed.scheme in {"http", "https"} and parsed.hostname
        and parsed.username is None and parsed.password is None
    )


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def load_dossiers(path: Path) -> list[JobDossier]:
    raw = load_json(path)
    if not isinstance(raw, list):
        raise ValueError("candidates must be a JSON list of existing JobDossier objects")
    models = {"job_identity": JobIdentity, "verification": JobVerification,
              "feasibility": FeasibilityAssessment, "capability_match": CapabilityMatch,
              "strategic_priority": StrategicPriority, "application_route": ApplicationRoute,
              "recommendation": Recommendation, "provenance": Provenance,
              "requirements": RequirementEvidence}
    rows: list[JobDossier] = []
    for index, candidate in enumerate(raw, 1):
        if not isinstance(candidate, dict) or set(candidate) - set(models):
            raise ValueError(f"candidate {index}: expected JobDossier fields")
        converted = {}
        for name, model in models.items():
            values = candidate.get(name, {} if name == "requirements" else None)
            if not isinstance(values, dict):
                raise ValueError(f"candidate {index}: missing or invalid {name}")
            allowed = {field.name: field for field in fields(model)}
            if set(values) - set(allowed):
                raise ValueError(f"candidate {index}: unknown fields in {name}")
            data = {}
            for key, value in values.items():
                sequence = str(allowed[key].type).startswith("tuple[")
                if sequence:
                    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
                        raise ValueError(f"candidate {index}: {name}.{key} must be a string list")
                    data[key] = tuple(value)
                elif not isinstance(value, str):
                    raise ValueError(f"candidate {index}: {name}.{key} must be a string")
                else:
                    data[key] = value
            try:
                converted[name] = model(**data)
            except TypeError as error:
                raise ValueError(f"candidate {index}: incomplete {name}") from error
        rows.append(JobDossier(**converted))
    return rows


def resolve_profile_path(profile_path: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("a non-empty configured file path is required")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else profile_path.resolve().parent / path).resolve()


def read_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as file:
        return file.read()


def require_local_runtime_path(path: Path) -> None:
    """Inside a Git workspace, runtime material must be ignored and untracked."""
    path = path.resolve()
    root = subprocess.run(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, check=False)
    if root.returncode:
        # A caller-selected directory outside Git is also a supported workspace.
        return
    repository = Path(root.stdout.strip())
    relative = str(path.relative_to(repository))
    tracked = subprocess.run(["git", "-C", str(repository), "ls-files", "--error-unmatch", "--", relative],
                             capture_output=True, check=False)
    ignored = subprocess.run(["git", "-C", str(repository), "check-ignore", "-q", "--", relative],
                             capture_output=True, check=False)
    if tracked.returncode == 0 or ignored.returncode != 0:
        raise ValueError(f"runtime material must be ignored and untracked, or outside Git: {path}")


def preflight_application_queue(path: Path, history_path: Path) -> tuple[str, str, int, int]:
    if path.resolve() == history_path.resolve():
        raise ValueError("queue and application history must be different files")
    text = read_exact(path)
    history_text = read_exact(history_path)  # Missing history must fail before any write.
    start = text.find(AUTO_QUEUE_START) + len(AUTO_QUEUE_START)
    end = text.find(AUTO_QUEUE_END, start)
    if text.count(AUTO_QUEUE_START) != 1 or text.count(AUTO_QUEUE_END) != 1 or end < start:
        raise ValueError("queue must contain exactly one ordered job-radar:auto marker pair")
    return text, history_text, start, end


def markdown_inline(value: str) -> str:
    text = clean_text(value)
    for character in ("\\", "[", "]", "`", "*", "|", "<", ">"):
        text = text.replace(character, "\\" + character)
    return text


def format_queue_task(row: JobDossier) -> str:
    identity = row.job_identity
    priority = "#p0" if row.recommendation.action == "APPLY_NOW" else "#p1"
    url = urllib.parse.quote(identity.official_url, safe=":/?&=#%+@;,$!~*'-._")
    identifier = f" · Job ID `{markdown_inline(identity.job_id)}`" if identity.job_id else ""
    return (
        f"- [ ] {priority} **{markdown_inline(identity.company)}｜{markdown_inline(identity.title)}**"
        f" · {markdown_inline(identity.location)} · {markdown_inline(identity.employment_type)}"
        f"{identifier} · [Official posting]({url})"
        f" · verified `{markdown_inline(row.verification.checked_at)}`"
        f" · action `{row.recommendation.action}`\n"
        f"  - Fit: {markdown_inline('; '.join(row.capability_match.supporting_evidence))}\n"
        f"  - Gaps: {markdown_inline('; '.join(row.capability_match.gaps)) or 'None recorded'}\n"
        f"  - Resume: {markdown_inline(row.application_route.resume_variant)}"
        f" · Narrative: {markdown_inline(row.application_route.narrative)}"
    )


def update_application_queue(path: Path, history_path: Path, rows: list[JobDossier],
                             config: dict, *, mode: str, write_queue: bool = False) -> int:
    if not write_queue:
        return 0
    if mode != "workspace_discovery":
        raise ValueError("standalone_review cannot write the application queue")
    if config.get("enabled") is not True:
        raise ValueError("application_queue.enabled must be true for an authorized write")
    for runtime_path in (path, history_path):
        require_local_runtime_path(runtime_path)
    limit = config.get("max_new_per_run", 8)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("max_new_per_run must be a positive integer")
    text, history, start, end = preflight_application_queue(path, history_path)
    tracked = {normalize_url(url) for url in markdown_urls(text + history)}
    newline_match = re.search(r"\r\n|\n|\r", text)
    newline = newline_match.group(0) if newline_match else "\n"
    additions: list[str] = []
    candidates = sorted(deduplicate_dossiers(rows), key=lambda row: (
        0 if row.recommendation.action == "APPLY_NOW" else 1,
        normalize_for_match(row.job_identity.company), normalize_for_match(row.job_identity.title)))
    for row in candidates:
        if len(additions) >= limit:
            break
        url = normalize_url(row.job_identity.official_url)
        if not is_auto_queue_eligible(row) or url in tracked:
            continue
        additions.append(format_queue_task(row).replace("\n", newline))
        tracked.add(url)
    if not additions:
        return 0
    merged = (newline * 2).join(part for part in (text[start:end].strip(), newline.join(additions)) if part)
    updated = text[:start] + newline + merged + newline + text[end:]
    # Refuse a changed snapshot; callers must re-read before retrying.
    if read_exact(path) != text or read_exact(history_path) != history:
        raise ValueError("queue or history changed during preparation; re-read and retry")
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write(updated)
    return len(additions)


def contains_stable_job_id(text: str, job_id: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_-]){re.escape(job_id)}(?![A-Za-z0-9_-])", text) is not None


def queue_disposition_annotations(queue_text: str, batch_date: str) -> tuple[dict[str, int], ...]:
    heading = re.compile(rf"(?m)^#{{1,6}}[ \t]+{re.escape(batch_date)}(?=[：:\s]|$)[^\n]*$")
    counts = re.compile(
        r"(?:(?P<evaluated>\d+)\s+evaluated\s*=\s*)?"
        r"(?P<queued>\d+)\s+queued\s*\+\s*"
        r"(?P<manual_review>\d+)\s+manual(?:[_\s]+)review\s*\+\s*"
        r"(?P<excluded>\d+)\s+excluded\s*\+\s*"
        r"(?P<duplicate>\d+)\s+duplicate\b", re.I)
    annotations = []
    for match in heading.finditer(queue_text):
        remaining = queue_text[match.end():]
        next_heading = re.search(r"(?m)^#{1,6}[ \t]+", remaining)
        section = remaining[:next_heading.start()] if next_heading else remaining
        for count in counts.finditer(section):
            annotations.append({key: int(value) for key, value in count.groupdict().items() if value is not None})
    return tuple(annotations)


def validate_recruiting_sync(manifest_path: Path, queue_path: Path, history_path: Path,
                            coverage_path: Path, current_actions_path: Path,
                            dashboard_path: Path) -> RecruitingSyncValidation:
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("handoff must be an object")
    errors: list[str] = []
    if manifest.get("mode") != "workspace_discovery":
        errors.append("handoff mode must be workspace_discovery")
    if manifest.get("requested_writeback") != "sync_verified_candidates":
        errors.append("requested_writeback must be sync_verified_candidates")
    candidates = manifest.get("evaluated_candidates")
    if not isinstance(candidates, list):
        candidates = []
        errors.append("evaluated_candidates must be a list")
    queue = queue_path.read_text(encoding="utf-8")
    history = history_path.read_text(encoding="utf-8")
    coverage = coverage_path.read_text(encoding="utf-8")
    state = "\n".join((coverage, current_actions_path.read_text(encoding="utf-8"),
                       dashboard_path.read_text(encoding="utf-8")))
    counts = dict.fromkeys(sorted(SYNC_DISPOSITIONS), 0)
    orphan_count = 0
    seen: dict[str, str] = {}
    for index, candidate in enumerate(candidates, 1):
        if not isinstance(candidate, dict):
            errors.append(f"candidate {index} must be an object")
            orphan_count += 1
            continue
        job_id = clean_text(str(candidate.get("job_id") or ""))
        disposition = candidate.get("disposition")
        if not job_id or not isinstance(disposition, str) or disposition not in SYNC_DISPOSITIONS:
            errors.append(f"candidate {index} needs a stable job_id and one valid disposition")
            orphan_count += 1
            continue
        if job_id in seen:
            errors.append(f"candidate {job_id} has multiple dispositions: {seen[job_id]} and {disposition}")
            continue
        seen[job_id] = disposition
        counts[disposition] += 1
        sink = history if disposition == "duplicate" else queue
        if not contains_stable_job_id(sink, job_id):
            errors.append(f"candidate {job_id} is missing from its {disposition} repository sink")
            orphan_count += 1
        if disposition != "duplicate" and contains_stable_job_id(queue, job_id) and contains_stable_job_id(history, job_id):
            errors.append(f"candidate {job_id} appears in both queue and application history")
    for key in ("companies", "stale_markers"):
        entries = manifest.get(key, [])
        if not isinstance(entries, list) or any(not isinstance(entry, str) for entry in entries):
            errors.append(f"{key} must be a string list")
            continue
        for entry in entries:
            if key == "companies" and entry and entry not in coverage:
                errors.append(f"company coverage is missing {entry}")
            if key == "stale_markers" and entry and entry in state:
                errors.append(f"stale marker remains: {entry}")
    batch_date = manifest.get("batch_date")
    if batch_date:
        annotations = queue_disposition_annotations(queue, str(batch_date))
        if len(annotations) != 1:
            errors.append(f"queue needs exactly one disposition annotation for {batch_date}")
        else:
            annotation = annotations[0]
            if annotation.get("evaluated", sum(counts.values())) != sum(counts.values()):
                errors.append(f"evaluated count mismatch for {batch_date}")
            if any(annotation[key] != value for key, value in counts.items()):
                errors.append(f"disposition mismatch for {batch_date}: report={counts}; queue={annotation}")
    return RecruitingSyncValidation(len(candidates), counts["queued"], counts["manual_review"],
                                    counts["excluded"], counts["duplicate"], orphan_count, tuple(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--candidates", type=Path, help="JSON list of evaluated JobDossier objects")
    action.add_argument("--validate-sync", type=Path, help="Read-only audit of the existing discovery handoff")
    parser.add_argument("--mode", choices=("standalone_review", "workspace_discovery"), default="standalone_review")
    parser.add_argument("--write-queue", action="store_true", help="Explicitly append eligible jobs; requires workspace_discovery")
    args = parser.parse_args(argv)
    try:
        if args.write_queue and (args.mode != "workspace_discovery" or args.validate_sync):
            raise ValueError("--write-queue requires --mode workspace_discovery and --candidates")
        profile = load_json(args.profile)
        if not isinstance(profile, dict) or not isinstance(profile.get("application_queue", {}), dict):
            raise ValueError("profile and application_queue must be objects")
        config = profile.get("application_queue", {})
        if args.validate_sync:
            result = validate_recruiting_sync(args.validate_sync,
                resolve_profile_path(args.profile, config.get("path")),
                resolve_profile_path(args.profile, config.get("application_history_path")),
                resolve_profile_path(args.profile, profile.get("company_coverage")),
                resolve_profile_path(args.profile, profile.get("current_actions")),
                resolve_profile_path(args.profile, profile.get("dashboard")))
            print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
            return 0 if result.passed else 2
        rows = load_dossiers(args.candidates)
        unique = deduplicate_dossiers(rows)
        added = 0
        if args.write_queue:
            queue = resolve_profile_path(args.profile, config.get("path"))
            history = resolve_profile_path(args.profile, config.get("application_history_path"))
            for runtime_path in (args.profile, args.candidates):
                require_local_runtime_path(runtime_path)
            if queue in {args.profile.resolve(), args.candidates.resolve()}:
                raise ValueError("queue must not overwrite the profile or candidate input")
            added = update_application_queue(queue, history, rows, config,
                                             mode=args.mode, write_queue=True)
        print(json.dumps({"mode": args.mode, "evaluated_count": len(rows),
                          "unique_count": len(unique), "eligible_count": sum(map(is_auto_queue_eligible, unique)),
                          "queue_added": added, "writes_enabled": args.write_queue},
                         ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
