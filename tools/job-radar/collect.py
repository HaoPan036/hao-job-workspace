#!/usr/bin/env python3
"""Foreground source collection migrated from Job Radar; never writes the queue.

--sources explicitly enables HTTP fetching. --fixtures exercises the same
parsers using fictional local payloads. --dry-run suppresses all persistence,
not network requests. Candidate evidence remains pending Agent review.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from html.parser import HTMLParser
from pathlib import Path

# The preview command must not create a local module-cache directory either.
sys.dont_write_bytecode = True
import radar
from radar import RequirementEvidence

load_json = radar.load_json
SOURCE_TYPES = {"html", "rss", "ashby", "greenhouse", "lever", "mycareersfuture",
                "baidu_campus", "wechat_search", "portal", "manual"}
DEFAULT_COLLECTOR = {
    "database_path": "radar/seen_jobs.sqlite3",
    "source_health_path": "radar/source_health.json",
    "reports_dir": "radar/reports",
    "dossiers_path": "radar/dossiers.json",
    "timeout_seconds": 20,
    "max_details": 20,
    "detail_minimum_score": 0,
    "report_minimum_score": 0,
}


@dataclass(frozen=True)
class ScoredItem:
    item: JobItem
    retrieval_score: int
    reasons: tuple[str, ...]
    key: str
    is_new: bool = True
    detail: JobDetail | None = None
    blocked_reasons: tuple[str, ...] = ()
    dossier: radar.JobDossier | None = None


@dataclass(frozen=True)
class JobItem:
    title: str
    url: str
    source: str
    snippet: str = ""
    published: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    position_level: str = ""
    minimum_years_experience: int | None = None
    expires: str = ""
    jd: str = ""
    requirements: str = ""
    job_id: str = ""
    source_type: str = ""
    role_level: bool = False


@dataclass(frozen=True)
class JobDetail:
    apply_url: str
    jd: str
    requirements: str
    status: str = ""
    title_matches: bool = False
    apply_action_found: bool = False
    is_fallback: bool = False


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {name.lower(): value for name, value in attrs}
        href = attr_map.get("href")
        if not href:
            return
        self._href = urllib.parse.urljoin(self.base_url, href)
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        text = clean_text(" ".join(self._text))
        if text and is_probably_recruiting_link(text, self._href):
            self.links.append((text, self._href))
        self._href = None
        self._text = []


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_for_match(value: str) -> str:
    return normalize_quotes(clean_text(value)).lower()


def normalize_quotes(value: str) -> str:
    return (
        value.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )


def is_probably_recruiting_link(title: str, url: str) -> bool:
    # A careers hostname alone must not turn /about and /privacy into job links.
    haystack = normalize_for_match(f"{title} {urllib.parse.urlsplit(url).path}")
    signals = [
        "job",
        "career",
        "position",
        "campus",
        "graduate",
        "intern",
        "recruit",
        "招聘",
        "校招",
        "岗位",
        "职位",
        "实习",
    ]
    return any(signal in haystack for signal in signals)


def is_probably_recruiting_title(title: str) -> bool:
    haystack = normalize_for_match(title)
    signals = [
        "招聘",
        "校招",
        "校园招聘",
        "实习",
        "岗位",
        "职位",
        "内推",
        "投递",
        "网申",
        "提前批",
        "宣讲",
        "秋招",
        "春招",
        "offer",
    ]
    return any(signal in haystack for signal in signals)


def load_source_health(path: Path) -> dict:
    if not path.exists():
        return {
            "updated_at": None,
            "sources": {},
            "bridge": {"consecutive_failures": 0},
        }
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("source health must be an object")
    if not isinstance(payload.get("sources"), dict):
        payload["sources"] = {}
    if not isinstance(payload.get("bridge"), dict):
        payload["bridge"] = {"consecutive_failures": 0}
    return payload


def save_source_health(path: Path, state: dict) -> None:
    atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def update_source_health(
    path: Path,
    sources: list[dict],
    errors: list[str],
    now: dt.datetime | None = None,
) -> dict:
    observed_at = now or dt.datetime.now().astimezone()
    observed_date = observed_at.date()
    state = load_source_health(path)
    source_state = dict(state["sources"])
    active_sources = [
        source
        for source in sources
        if source.get("enabled", True) and source.get("type", "html") != "manual"
    ]
    failed_names = {
        str(source["name"])
        for source in active_sources
        if any(error.startswith(f"{source['name']}:") for error in errors)
    }
    for source in active_sources:
        name = str(source["name"])
        record = dict(source_state.get(name) or {})
        record.setdefault("last_success_at", None)
        if name in failed_names:
            last_failure_date = record.get("last_failure_date")
            if last_failure_date == observed_date.isoformat():
                failures = max(1, int(record.get("consecutive_failures") or 0))
            elif last_failure_date == (observed_date - dt.timedelta(days=1)).isoformat():
                failures = int(record.get("consecutive_failures") or 0) + 1
            else:
                failures = 1
            record.update(
                {
                    "consecutive_failures": failures,
                    "last_failure_at": observed_at.isoformat(),
                    "last_failure_date": observed_date.isoformat(),
                }
            )
        else:
            record.update(
                {
                    "consecutive_failures": 0,
                    "last_success_at": observed_at.isoformat(),
                }
            )
        source_state[name] = record
    state.update(
        {
            "updated_at": observed_at.isoformat(),
            "sources": source_state,
        }
    )
    save_source_health(path, state)
    return state


def sanitize_url(url: str) -> str:
    return urllib.parse.quote(url.strip(), safe=":/?&=%#[]@!$'()*+,;")


def source_url(source: dict) -> str:
    if source.get("type") == "wechat_search":
        query = source.get("query", "")
        return "https://weixin.sogou.com/weixin?type=2&query=" + urllib.parse.quote(query)
    return source.get("url", "")


def parse_html_items(source: dict, text: str) -> list[JobItem]:
    parser = LinkExtractor(source_url(source))
    parser.feed(text)
    seen: set[str] = set()
    items: list[JobItem] = []
    for title, url in parser.links:
        key = f"{title}\0{url}"
        if key in seen:
            continue
        seen.add(key)
        items.append(
            JobItem(
                title=title,
                url=url,
                source=source["name"],
                company=source.get("company", ""),
                location=source.get("location", ""),
                employment_type=source.get("employment_type", ""),
                job_id=extract_job_id(url),
                source_type=source.get("type", "html"),
                role_level=is_direct_role_url(url),
            )
        )
    return items


def parse_wechat_search_items(source: dict, text: str) -> list[JobItem]:
    base_url = source_url(source)
    items: list[JobItem] = []
    seen: set[str] = set()
    result_pattern = re.compile(r'(?is)<div class="txt-box">\s*<h3>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?<p class="txt-info"[^>]*>(.*?)</p>(.*?)</div>')
    for href, title_html, summary_html, tail_html in result_pattern.findall(text):
        title = html_to_text(title_html)
        summary = html_to_text(summary_html)
        if not is_probably_recruiting_title(title):
            continue
        account_match = re.search(r'(?is)<span class="all-time-y2">(.*?)</span>', tail_html)
        account = html_to_text(account_match.group(1)) if account_match else ""
        url = sanitize_url(urllib.parse.urljoin(base_url, html.unescape(href)))
        key = f"{title}\0{url}"
        if not title or key in seen:
            continue
        snippet = clean_text("；".join(part for part in [summary, f"公众号：{account}" if account else ""] if part))
        candidate = JobItem(
            title=title,
            url=url,
            source=source["name"],
            snippet=snippet,
            company=source.get("company", ""),
            location=source.get("location", ""),
            employment_type=source.get("employment_type", ""),
            source_type="wechat_search",
            role_level=False,
        )
        title_required_terms = source.get("require_title_any", [])
        if title_required_terms and not matching_terms(normalize_for_match(candidate.title), title_required_terms):
            continue
        title_required_all = source.get("require_title_all", [])
        if title_required_all and not all(
            matching_terms(normalize_for_match(candidate.title), [term])
            for term in title_required_all
        ):
            continue
        required_terms = source.get("require_any", [])
        if required_terms and not matching_terms(
            normalize_for_match(f"{candidate.title} {candidate.snippet}"), required_terms
        ):
            continue
        seen.add(key)
        items.append(candidate)
    return items


def parse_rss_items(source: dict, text: str) -> list[JobItem]:
    root = ET.fromstring(text)
    items: list[JobItem] = []
    rss_items = root.findall(".//item")
    atom_entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    for node in rss_items:
        title = clean_text(node.findtext("title") or "")
        link = clean_text(node.findtext("link") or source["url"])
        snippet = clean_text(node.findtext("description") or "")
        published = clean_text(node.findtext("pubDate") or "")
        if title:
            items.append(
                JobItem(
                    title=title,
                    url=link,
                    source=source["name"],
                    snippet=snippet,
                    published=published,
                    company=source.get("company", ""),
                    location=source.get("location", ""),
                    employment_type=source.get("employment_type", ""),
                    job_id=extract_job_id(link),
                    source_type="rss",
                    role_level=is_direct_role_url(link),
                )
            )

    for node in atom_entries:
        title = clean_text(node.findtext("{http://www.w3.org/2005/Atom}title") or "")
        link = source["url"]
        for link_node in node.findall("{http://www.w3.org/2005/Atom}link"):
            href = link_node.attrib.get("href")
            if href:
                link = href
                break
        snippet = clean_text(node.findtext("{http://www.w3.org/2005/Atom}summary") or "")
        published = clean_text(node.findtext("{http://www.w3.org/2005/Atom}updated") or "")
        if title:
            items.append(
                JobItem(
                    title=title,
                    url=link,
                    source=source["name"],
                    snippet=snippet,
                    published=published,
                    company=source.get("company", ""),
                    location=source.get("location", ""),
                    employment_type=source.get("employment_type", ""),
                    job_id=extract_job_id(link),
                    source_type="rss",
                    role_level=is_direct_role_url(link),
                )
            )

    return items


def parse_mycareersfuture_items(source: dict, text: str) -> list[JobItem]:
    payload = json.loads(text)
    items: list[JobItem] = []
    for row in payload.get("results", []):
        metadata = row.get("metadata") or {}
        company = clean_text((row.get("postedCompany") or {}).get("name", ""))
        employment_types = join_mapping_values(row.get("employmentTypes"), "employmentType")
        position_levels = join_mapping_values(row.get("positionLevels"), "position")
        skills = join_mapping_values(row.get("skills"), "skill")
        description = html_to_text(row.get("description") or "")
        minimum_experience = optional_int(row.get("minimumYearsExperience"))
        published = clean_text(metadata.get("newPostingDate") or "")
        expires = clean_text(metadata.get("expiryDate") or "")
        url = clean_text(metadata.get("jobDetailsUrl") or source_url(source))
        location = source.get("location", "Singapore")
        summary_parts = [
            company,
            location,
            employment_types,
            position_levels,
            f"minimum experience: {minimum_experience} years"
            if minimum_experience is not None
            else "",
            f"skills: {skills}" if skills else "",
            compact_excerpt(description, 1200),
        ]
        item = JobItem(
            title=clean_text(row.get("title") or ""),
            url=url,
            source=source["name"],
            snippet=clean_text("; ".join(part for part in summary_parts if part)),
            published=published,
            company=company,
            location=location,
            employment_type=employment_types,
            position_level=position_levels,
            minimum_years_experience=minimum_experience,
            expires=expires,
            jd=compact_excerpt(description, 1800),
            requirements=compact_excerpt(extract_requirement_sentences(description), 1000),
            job_id=clean_text(row.get("uuid") or ""),
            source_type="mycareersfuture",
            role_level=True,
        )
        if item.title and source_accepts_item(source, item):
            items.append(item)
    return items


def parse_ashby_items(source: dict, text: str) -> list[JobItem]:
    payload = json.loads(text)
    items: list[JobItem] = []
    for row in payload.get("jobs", []):
        description = html_to_text(row.get("descriptionHtml") or row.get("description") or "")
        item = JobItem(
            title=clean_text(row.get("title") or ""),
            url=clean_text(row.get("applyUrl") or row.get("jobUrl") or source_url(source)),
            source=source["name"],
            snippet=structured_snippet(
                source.get("company", ""),
                row.get("location", ""),
                row.get("employmentType", ""),
                description,
            ),
            published=iso_date(row.get("publishedAt")),
            company=source.get("company", ""),
            location=clean_text(row.get("location") or ""),
            employment_type=clean_text(row.get("employmentType") or ""),
            minimum_years_experience=extract_minimum_years_experience(description),
            jd=compact_excerpt(description, 1800),
            requirements=compact_excerpt(extract_requirement_sentences(description), 1000),
            job_id=clean_text(row.get("id") or extract_job_id(row.get("jobUrl") or row.get("applyUrl") or "")),
            source_type="ashby",
            role_level=True,
        )
        if item.title and source_accepts_item(source, item):
            items.append(item)
    return items


def parse_greenhouse_items(source: dict, text: str) -> list[JobItem]:
    payload = json.loads(text)
    items: list[JobItem] = []
    for row in payload.get("jobs", []):
        description = html_to_text(row.get("content") or "")
        location = clean_text((row.get("location") or {}).get("name", ""))
        item = JobItem(
            title=clean_text(row.get("title") or ""),
            url=clean_text(row.get("absolute_url") or source_url(source)),
            source=source["name"],
            snippet=structured_snippet(
                source.get("company", ""),
                location,
                source.get("employment_type", ""),
                description,
            ),
            published=iso_date(row.get("updated_at")),
            company=source.get("company", ""),
            location=location,
            employment_type=source.get("employment_type", ""),
            minimum_years_experience=extract_minimum_years_experience(description),
            jd=compact_excerpt(description, 1800),
            requirements=compact_excerpt(extract_requirement_sentences(description), 1000),
            job_id=clean_text(str(row.get("id") or "")),
            source_type="greenhouse",
            role_level=True,
        )
        if item.title and source_accepts_item(source, item):
            items.append(item)
    return items


def parse_lever_items(source: dict, text: str) -> list[JobItem]:
    payload = json.loads(text)
    items: list[JobItem] = []
    for row in payload if isinstance(payload, list) else payload.get("postings", []):
        categories = row.get("categories") or {}
        location = clean_text(categories.get("location") or "")
        employment_type = clean_text(categories.get("commitment") or "")
        list_text = "\n".join(
            html_to_text(f"{entry.get('text', '')}\n{entry.get('content', '')}")
            for entry in row.get("lists", [])
        )
        description = clean_text(
            "\n".join(
                part
                for part in [
                    row.get("descriptionPlain") or "",
                    list_text,
                    row.get("additionalPlain") or "",
                ]
                if part
            )
        )
        item = JobItem(
            title=clean_text(row.get("text") or ""),
            url=clean_text(row.get("hostedUrl") or row.get("applyUrl") or source_url(source)),
            source=source["name"],
            snippet=structured_snippet(
                source.get("company", ""), location, employment_type, description
            ),
            published=epoch_millis_date(row.get("createdAt")),
            company=source.get("company", ""),
            location=location,
            employment_type=employment_type,
            minimum_years_experience=extract_minimum_years_experience(description),
            jd=compact_excerpt(description, 1800),
            requirements=compact_excerpt(extract_requirement_sentences(description), 1000),
            job_id=clean_text(row.get("id") or extract_job_id(row.get("hostedUrl") or row.get("applyUrl") or "")),
            source_type="lever",
            role_level=True,
        )
        if item.title and source_accepts_item(source, item):
            items.append(item)
    return items


def parse_baidu_campus_items(source: dict, text: str) -> list[JobItem]:
    marker = '"listDetailData":'
    marker_index = text.find(marker)
    if marker_index < 0:
        return []
    start = text.find("[", marker_index + len(marker))
    if start < 0:
        return []
    rows, _ = json.JSONDecoder().raw_decode(text[start:])
    items: list[JobItem] = []
    for row in rows:
        location = first_text_value(
            row,
            ["workPlaceName", "workPlace", "workplace", "location", "workCity"],
        )
        title = clean_text(row.get("name") or row.get("postName") or "")
        work_content = clean_text(row.get("workContent") or row.get("description") or "")
        requirements = clean_text(
            row.get("serviceCondition") or row.get("qualification") or ""
        )
        job_id = clean_text(row.get("jobId") or row.get("postId") or "")
        url = source_url(source)
        if job_id:
            url = f"{url}#{urllib.parse.quote(job_id)}"
        item = JobItem(
            title=title,
            url=url,
            source=source["name"],
            snippet=structured_snippet(
                source.get("company", "百度"),
                location,
                source.get("employment_type", ""),
                f"{work_content} {requirements}",
            ),
            published=clean_text(row.get("updateDate") or row.get("publishDate") or ""),
            company=source.get("company", "百度"),
            location=location,
            employment_type=source.get("employment_type", ""),
            jd=compact_excerpt(work_content, 1800),
            requirements=compact_excerpt(requirements, 1000),
            job_id=job_id,
            source_type="baidu_campus",
            role_level=bool(job_id),
        )
        if item.title and source_accepts_item(source, item):
            items.append(item)
    return items


def source_accepts_item(source: dict, item: JobItem) -> bool:
    checks = [
        ("require_location_any", item.location),
        ("require_title_any", item.title),
        ("require_any", item_search_text(item)),
    ]
    for field, value in checks:
        terms = source.get(field, [])
        if terms and not matching_terms(normalize_for_match(value), terms):
            return False
    if source.get("require_title_all") and not all(
        matching_terms(normalize_for_match(item.title), [term])
        for term in source["require_title_all"]
    ):
        return False
    return True


def join_mapping_values(values: object, key: str) -> str:
    if not isinstance(values, list):
        return ""
    return ", ".join(
        clean_text(value.get(key) or "")
        for value in values
        if isinstance(value, dict) and value.get(key)
    )


def optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_minimum_years_experience(text: str) -> int | None:
    """Extract explicit required experience, excluding preferred/nice-to-have text."""
    patterns = [
        r"(?:at least|minimum(?: of)?|min\.?|more than|over)\s+(\d+)\+?\s+years",
        r"(\d+)(?:\s*-\s*\d+)?\+?\s+years(?:'|\s+of)?\s+"
        r"(?:relevant\s+|professional\s+|work\s+|industry\s+)?experience",
        r"(?:经验|工作经验)\s*(\d+)\s*年(?:以上|及以上)",
        r"(\d+)\s*年(?:以上|及以上)(?:相关)?(?:工作)?经验",
    ]
    values: list[int] = []
    for segment in requirement_segments(text):
        normalized = normalize_for_match(segment)
        if requirement_kind(segment) in {"preferred", "nice_to_have"}:
            continue
        for pattern in patterns:
            values.extend(
                int(match.group(1)) for match in re.finditer(pattern, normalized)
            )
    return min(values) if values else None


def requirement_segments(text: str) -> list[str]:
    normalized = normalize_quotes(html_to_text(text or ""))
    normalized = re.sub(
        r"(?i)(?=\b(?:minimum|required|preferred|nice to have|nice-to-have|bonus)"
        r"\s+(?:qualifications?|requirements?)\b)",
        "\n",
        normalized,
    )
    parts = re.split(r"[\n\r]+|(?<=[.;。；])\s+", normalized)
    return [clean_text(part).lstrip("-*• ") for part in parts if clean_text(part)]


def requirement_kind(segment: str) -> str:
    normalized = normalize_for_match(segment)
    if matching_terms(
        normalized,
        [
            "nice to have",
            "nice-to-have",
            "bonus",
            "a plus",
            "plus but not required",
            "加分项",
            "加分",
        ],
    ):
        return "nice_to_have"
    if matching_terms(
        normalized,
        [
            "preferred",
            "ideally",
            "优先考虑",
            "优先",
        ],
    ):
        return "preferred"
    if matching_terms(
        normalized,
        [
            "required",
            "must have",
            "must be",
            "minimum",
            "at least",
            "requirement",
            "任职要求",
            "岗位要求",
            "必须",
            "需具备",
            "至少",
        ],
    ):
        return "required"
    return "unclassified"


def classify_requirement_evidence(text: str) -> RequirementEvidence:
    buckets: dict[str, list[str]] = {
        "required": [],
        "preferred": [],
        "nice_to_have": [],
        "unclassified": [],
    }
    for segment in requirement_segments(text):
        buckets[requirement_kind(segment)].append(segment)
    return RequirementEvidence(
        required=tuple(buckets["required"]),
        preferred=tuple(buckets["preferred"]),
        nice_to_have=tuple(buckets["nice_to_have"]),
        unclassified=tuple(buckets["unclassified"]),
    )


def structured_snippet(
    company: object, location: object, employment_type: object, description: str
) -> str:
    return clean_text(
        "; ".join(
            part
            for part in [
                clean_text(str(company or "")),
                clean_text(str(location or "")),
                clean_text(str(employment_type or "")),
                compact_excerpt(description, 1200),
            ]
            if part
        )
    )


def iso_date(value: object) -> str:
    text = clean_text(str(value or ""))
    match = re.match(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else text


def epoch_millis_date(value: object) -> str:
    try:
        timestamp = int(value) / 1000
    except (TypeError, ValueError):
        return ""
    return dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc).date().isoformat()


def first_text_value(row: dict, keys: list[str]) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, list):
            parts = [
                clean_text(
                    str(
                        (part.get("name") or part.get("label") or "")
                        if isinstance(part, dict)
                        else part or ""
                    )
                )
                for part in value
            ]
            if any(parts):
                return ", ".join(part for part in parts if part)
        if isinstance(value, dict):
            value = value.get("name") or value.get("label") or ""
        if value:
            return clean_text(str(value))
    return ""


def extract_job_id(url: object) -> str:
    text = clean_text(str(url or ""))
    if not text:
        return ""
    parsed = urllib.parse.urlsplit(text)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    for key in [
        "jobId",
        "job_id",
        "jobid",
        "positionId",
        "position_id",
        "postingId",
        "requisitionId",
        "gh_jid",
    ]:
        value = clean_text(query.get(key) or "")
        if value:
            return value
    if parsed.fragment and normalize_for_match(parsed.fragment) not in {
        "jobs",
        "joblist",
        "jobslist",
        "positions",
    }:
        return clean_text(parsed.fragment)

    segments = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    markers = {"apply", "application", "detail", "job", "jobs", "position", "positions", "posting", "postings", "role", "roles"}
    ignored = markers | {"campus", "graduate", "graduates", "list", "search", "home"}
    for index, segment in enumerate(segments):
        if normalize_for_match(segment) not in markers:
            continue
        for candidate in reversed(segments[index + 1 :]):
            if normalize_for_match(candidate) not in ignored:
                return clean_text(candidate)
    return ""


def is_direct_application_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    path = normalize_for_match(parsed.path)
    return bool(
        re.search(r"/(?:apply|application)(?:/|$)", path)
        or any(key.lower() in {"gh_jid", "jobid", "positionid"} for key, _ in urllib.parse.parse_qsl(parsed.query))
    )


def is_direct_role_url(url: str) -> bool:
    if not url:
        return False
    parsed = urllib.parse.urlsplit(url)
    path = normalize_for_match(parsed.path).rstrip("/")
    if is_direct_application_url(url) or extract_job_id(url):
        return True
    return bool(
        re.search(
            r"/(?:jobs?|positions?|postings?|roles?)/(?!list(?:/|$)|search(?:/|$)|home(?:/|$))[^/]+$",
            path,
        )
    )


def item_search_text(item: JobItem) -> str:
    return " ".join(
        str(value)
        for value in [
            item.title,
            item.snippet,
            item.url,
            item.company,
            item.location,
            item.employment_type,
            item.position_level,
        ]
        if value
    )


def discovery_domain_hints(profile: dict) -> list[str]:
    """Return discovery hints, including the v1 config name as a read-only alias."""
    if profile.get("discovery_domain_hints") is not None:
        return list(profile.get("discovery_domain_hints") or [])
    queue_config = profile.get("application_queue", {})
    if queue_config.get("discovery_domain_hints") is not None:
        return list(queue_config.get("discovery_domain_hints") or [])
    return list(queue_config.get("required_domain_keywords") or [])


def score_item(item: JobItem, source: dict, profile: dict) -> tuple[int, tuple[str, ...]]:
    haystack = normalize_for_match(item_search_text(item))
    score = int(source.get("priority", 0))
    reasons: list[str] = []
    if score:
        reasons.append(f"source +{score}")

    role_hits = matching_terms(haystack, profile.get("target_roles", []))
    if role_hits:
        score += 25
        reasons.append("role: " + ", ".join(role_hits[:3]))

    must_hits = matching_terms(haystack, profile.get("must_include_any", []))
    if must_hits:
        score += 20
        reasons.append("core: " + ", ".join(must_hits[:4]))

    preferred_hits = matching_terms(haystack, profile.get("preferred_keywords", []))
    if preferred_hits:
        bonus = min(30, 5 * len(preferred_hits))
        score += bonus
        reasons.append(f"keywords +{bonus}: " + ", ".join(preferred_hits[:5]))

    domain_hits = matching_terms(haystack, discovery_domain_hints(profile))
    if domain_hits:
        bonus = min(12, 3 * len(domain_hits))
        score += bonus
        reasons.append(f"discovery hints +{bonus}: " + ", ".join(domain_hits[:4]))

    fresh_haystack = normalize_for_match(
        f"{item.title} {item.employment_type} {item.position_level}"
    )
    fresh_hits = matching_terms(
        fresh_haystack, profile.get("fresh_grad_keywords", [])
    )
    if fresh_hits:
        score += 20
        reasons.append("fresh grad: " + ", ".join(fresh_hits[:3]))

    location_hits = matching_terms(haystack, profile.get("locations", []))
    if location_hits:
        score += 15
        reasons.append("location: " + ", ".join(location_hits[:3]))

    non_target_location_hits = matching_terms(haystack, profile.get("non_target_locations", []))
    if non_target_location_hits and not location_hits:
        score -= 35
        reasons.append("non-target location -35: " + ", ".join(non_target_location_hits[:3]))

    company_hits = matching_terms(haystack, profile.get("target_companies", []))
    if company_hits:
        score += 10
        reasons.append("company: " + ", ".join(company_hits[:3]))

    negative_hits = matching_terms(haystack, profile.get("negative_keywords", []))
    if negative_hits:
        penalty = min(80, 25 * len(negative_hits))
        score -= penalty
        reasons.append(f"negative -{penalty}: " + ", ".join(negative_hits[:4]))

    generic_hits = generic_title_hits(item.title, profile.get("generic_link_titles", []))
    if generic_hits:
        score -= 35
        reasons.append("generic link -35: " + ", ".join(generic_hits[:3]))

    return max(0, score), tuple(reasons)


def parse_iso_date(value: str) -> dt.date | None:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    if not match:
        return None
    try:
        return dt.date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def matching_terms(haystack: str, terms: list[str]) -> list[str]:
    hits: list[str] = []
    for term in terms:
        normalized = normalize_for_match(term)
        if normalized and term_matches(haystack, normalized):
            hits.append(term)
    return hits


def term_matches(haystack: str, normalized_term: str) -> bool:
    if re.fullmatch(r"[a-z0-9][a-z0-9 +.,/-]*", normalized_term):
        return re.search(rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])", haystack) is not None
    return normalized_term in haystack


def generic_title_hits(title: str, terms: list[str]) -> list[str]:
    normalized_title = normalize_for_match(title)
    if "{{" in normalized_title or "}}" in normalized_title:
        return ["template text"]
    hits: list[str] = []
    for term in terms:
        normalized = normalize_for_match(term)
        if normalized and normalized_title == normalized:
            hits.append(term)
    return hits


def html_to_text(text: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|section|article|li|ul|ol|h[1-6])>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_job_detail(item: JobItem, timeout: int, profile: dict) -> JobDetail:
    return parse_job_detail(item, fetch_text(item.url, timeout), profile)


def parse_job_detail(item: JobItem, text: str, profile: dict) -> JobDetail:
    description_html = extract_embedded_description_html(text)
    page_text = html_to_text(description_html or text)
    sections = profile.get("detail_sections", {})
    jd = extract_section(
        page_text,
        sections.get("jd_headings", []),
        sections.get("requirements_headings", []) + sections.get("stop_headings", []),
    )
    requirements = extract_section(
        page_text,
        sections.get("requirements_headings", []),
        sections.get("stop_headings", []),
    )
    if not jd:
        jd = compact_excerpt(page_text, 700)
    if not requirements:
        requirements = extract_requirement_sentences(page_text)
    apply_url = extract_apply_url(item.url, text)
    return JobDetail(
        apply_url=apply_url or item.url,
        jd=compact_excerpt(jd, 900),
        requirements=compact_excerpt(requirements, 700),
        title_matches=title_matches_page(item, page_text),
        apply_action_found=bool(apply_url) or is_direct_application_url(item.url),
    )


def title_matches_page(item: JobItem, page_text: str) -> bool:
    title = radar.normalize_for_match(item.title)
    for removable in (item.company, item.location):
        if removable:
            title = title.replace(radar.normalize_for_match(removable), " ")
    title = "".join(character for character in title if character.isalnum())
    if len(title) < 5:
        return False
    normalized_page = "".join(character for character in radar.normalize_for_match(page_text)
                              if character.isalnum())
    return title in normalized_page


def extract_embedded_description_html(text: str) -> str:
    match = re.search(r'"descriptionHtml"\s*:\s*"((?:\\.|[^"\\])*)"', text)
    if not match:
        return ""
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return ""


def extract_section(text: str, start_headings: list[str], stop_headings: list[str]) -> str:
    lowered = normalize_quotes(text).lower()
    starts = [
        (lowered.find(normalize_quotes(heading).lower()), heading)
        for heading in start_headings
        if normalize_quotes(heading).lower() in lowered
    ]
    starts = [(index, heading) for index, heading in starts if index >= 0]
    if not starts:
        return ""
    start, heading = min(starts, key=lambda row: row[0])
    section_start = start + len(heading)
    stop_candidates = [
        lowered.find(normalize_quotes(stop).lower(), section_start)
        for stop in stop_headings
        if normalize_quotes(stop).lower() in lowered[section_start:]
    ]
    stop_candidates = [index for index in stop_candidates if index > section_start]
    section_end = min(stop_candidates) if stop_candidates else min(len(text), section_start + 2500)
    return text[section_start:section_end].strip(" :-\n\t")


def extract_requirement_sentences(text: str) -> str:
    keywords = [
        "experience",
        "proficiency",
        "familiar",
        "knowledge",
        "ability",
        "sql",
        "python",
        "llm",
        "agent",
        "requirement",
        "work authorization",
        "right to work",
        "work permit",
        "sponsorship",
        "visa",
        "要求",
        "经验",
        "熟悉",
        "能力",
        "工签",
        "签证",
        "工作许可",
    ]
    lines = [clean_text(line) for line in text.splitlines()]
    hits = [line for line in lines if len(line) >= 25 and any(word in line.lower() for word in keywords)]
    return "\n".join(hits[:8])


def compact_excerpt(text: str, limit: int) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def extract_apply_url(base_url: str, text: str) -> str:
    apply_terms = ["apply", "submit application", "申请", "投递", "立即申请", "立即投递"]
    anchor_pattern = re.compile(r"(?is)<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>")
    for href, label_html in anchor_pattern.findall(text):
        label = normalize_for_match(html_to_text(label_html))
        if any(term in label for term in apply_terms):
            return urllib.parse.urljoin(base_url, href)
    return ""


def init_db(path: Path) -> sqlite3.Connection:
    reject_symlinks(path)
    for suffix in ("-wal", "-shm", "-journal"):
        reject_symlinks(path.with_name(path.name + suffix))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_jobs (
                key TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                score INTEGER NOT NULL
            )
            """
        )
        conn.commit()
    except Exception:
        conn.close()
        raise
    return conn


def mark_seen(conn: sqlite3.Connection, scored: ScoredItem, now: str) -> ScoredItem:
    row = conn.execute(
        "SELECT key, first_seen FROM seen_jobs WHERE key = ?", (scored.key,)
    ).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT key, first_seen FROM seen_jobs WHERE url = ? LIMIT 1",
            (scored.item.url,),
        ).fetchone()
    first_observation = row is None
    is_new = first_observation or local_calendar_date(row[1]) == local_calendar_date(now)
    if first_observation:
        conn.execute(
            """
            INSERT INTO seen_jobs (key, title, url, source, first_seen, last_seen, score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scored.key,
                scored.item.title,
                scored.item.url,
                scored.item.source,
                now,
                now,
                scored.retrieval_score,
            ),
        )
    else:
        existing_key = row[0]
        conn.execute(
            """
            UPDATE seen_jobs
            SET key = ?, title = ?, url = ?, source = ?, last_seen = ?, score = ?
            WHERE key = ?
            """,
            (
                scored.key,
                scored.item.title,
                scored.item.url,
                scored.item.source,
                now,
                scored.retrieval_score,
                existing_key,
            ),
        )
    return replace(scored, is_new=is_new)


def local_calendar_date(value: str) -> dt.date | None:
    """Return an ISO timestamp's date in the machine's local timezone."""
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return parse_iso_date(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.date()


def read_seen_retrieval_score(
    conn: sqlite3.Connection, key: str
) -> int | None:
    """Read the v1 ``score`` column using its v2 retrieval_score meaning."""
    row = conn.execute("SELECT score FROM seen_jobs WHERE key = ?", (key,)).fetchone()
    return int(row[0]) if row is not None else None

def require_http_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError("source and detail URLs must be HTTP(S) without embedded credentials")
    return url


def fetch_text(url: str, timeout: int) -> str:
    request = urllib.request.Request(sanitize_url(require_http_url(url)), headers={
        "User-Agent": "JobWorkspaceRadar/1.0 (local foreground collection)",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        content_type = response.headers.get("content-type", "")
    match = re.search(r"charset=([\w-]+)", content_type, flags=re.I)
    return raw.decode(match.group(1) if match else "utf-8", errors="replace")


def parse_payload(source: dict, text: str) -> list[JobItem]:
    parsers = {
        "html": parse_html_items, "rss": parse_rss_items,
        "ashby": parse_ashby_items, "greenhouse": parse_greenhouse_items,
        "lever": parse_lever_items, "mycareersfuture": parse_mycareersfuture_items,
        "baidu_campus": parse_baidu_campus_items, "wechat_search": parse_wechat_search_items,
    }
    return [item for item in parsers[source.get("type", "html")](source, text)
            if source_accepts_item(source, item)]


def collect_from_source(source: dict, timeout: int,
                        fixture_root: Path | None = None) -> tuple[list[JobItem], str | None]:
    if not source.get("enabled", True) or source.get("type") == "manual":
        return [], None
    if source.get("type") == "portal":
        return [JobItem(title=source.get("title") or source["name"],
                        url=source_url(source), source=source["name"],
                        snippet=source.get("snippet", ""), company=source.get("company", ""),
                        location=source.get("location", ""),
                        employment_type=source.get("employment_type", ""),
                        jd=source.get("jd", ""), requirements=source.get("requirements", ""),
                        job_id=source.get("job_id", ""), source_type="portal",
                        role_level=bool(source.get("role_level", False)))], None
    try:
        if fixture_root is not None:
            text = fixture_path(fixture_root, source["fixture_path"]).read_text(encoding="utf-8")
        else:
            text = fetch_text(source_url(source), timeout)
        return parse_payload(source, text), None
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as error:
        return [], f"{source['name']}: {type(error).__name__}: {error}"


def configured_exclusion_reasons(item: JobItem, profile: dict) -> tuple[str, ...]:
    """Retain configured discovery filters as review hints, not an assessment."""
    haystack = normalize_for_match(item_search_text(item))
    reasons = []
    internship = matching_terms(normalize_for_match(
        f"{item.title} {item.employment_type}"), profile.get("internship_keywords", []))
    locations = matching_terms(haystack, profile.get("internship_excluded_locations", []))
    if internship and locations:
        reasons.append("Configured internship exclusion: " + ", ".join(locations))
    allowed = set(profile.get("allowed_graduation_years", []))
    if allowed:
        for year in sorted(set(re.findall(r"(20\d{2})\s*届", haystack))):
            if year not in allowed:
                reasons.append("Configured graduation year mismatch: " + year)
    for label, terms in (("Excluded keyword", profile.get("blocked_keywords", [])),
                         ("Excluded location", profile.get("non_target_locations", []))):
        hits = matching_terms(haystack, terms)
        if hits:
            reasons.append(label + ": " + ", ".join(hits))
    expires = parse_iso_date(item.expires)
    if expires and expires < dt.date.today():
        reasons.append("Posting reports an expired deadline: " + item.expires)
    return tuple(reasons)


def item_key(item: JobItem) -> str:
    identity = radar.JobIdentity(item.company, item.title, item.job_id, item.url,
                                 item.location, item.employment_type, "UNKNOWN")
    if item.job_id:
        key = "id:" + radar.normalize_company(item.company or item.source) + "\0" + item.job_id
    else:
        key = radar.semantic_job_fingerprint(identity) or radar.normalize_url(item.url)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def attach_dossier(row: ScoredItem, fetched_at: str) -> ScoredItem:
    item = row.item
    requirements = row.detail.requirements if row.detail else item.requirements
    reasons = ("Collected source evidence requires official posting review.",) + row.blocked_reasons
    dossier = radar.JobDossier(
        job_identity=radar.JobIdentity(item.company, item.title, item.job_id, item.url,
                                       item.location, item.employment_type, "UNKNOWN"),
        verification=radar.JobVerification("PENDING", reasons),
        feasibility=radar.FeasibilityAssessment("UNKNOWN", unknowns=(
            "Review current eligibility and the user's confirmed conditions.",)),
        capability_match=radar.CapabilityMatch(), strategic_priority=radar.StrategicPriority(),
        application_route=radar.ApplicationRoute(),
        recommendation=radar.Recommendation("MANUAL_REVIEW", (
            "Collection and retrieval score do not establish fit or application priority.",)),
        provenance=radar.Provenance(fetched_at, item.source, "job-radar-collector", "2.0"),
        requirements=classify_requirement_evidence(requirements),
    )
    return replace(row, dossier=dossier)


def enrich_details(rows: list[ScoredItem], sources: list[dict], profile: dict,
                   config: dict, fixture_root: Path | None = None,
                   no_details: bool = False) -> tuple[list[ScoredItem], list[str]]:
    enriched, errors = [], []
    source_map = {source["name"]: source for source in sources}
    fetched = 0
    for row in rows:
        item = row.item
        detail = None
        if item.jd or item.requirements:
            detail = JobDetail(item.url, item.jd or item.snippet, item.requirements,
                               status="Structured source evidence; unverified")
        elif (not no_details and item.source_type not in {"portal", "wechat_search"}
              and row.retrieval_score >= config["detail_minimum_score"]
              and fetched < config["max_details"]):
            try:
                if fixture_root is None:
                    fetched += 1
                    detail = fetch_job_detail(item, config["timeout_seconds"], profile)
                else:
                    fixture = source_map[item.source].get("detail_fixtures", {}).get(item.url)
                    if fixture:
                        fetched += 1
                        text = fixture_path(fixture_root, fixture).read_text(encoding="utf-8")
                        detail = parse_job_detail(item, text, profile)
            except (OSError, ValueError, TypeError) as error:
                errors.append(f"{item.source} detail: {type(error).__name__}: {error}")
        enriched.append(replace(row, detail=detail))
    return enriched, errors


def collect_all(sources: list[dict], profile: dict, config: dict,
                fetched_at: str, fixture_root: Path | None = None,
                no_details: bool = False) -> tuple[list[ScoredItem], list[str], dict[str, int]]:
    rows, errors, counts = [], [], {}
    for source in sources:
        items, error = collect_from_source(source, config["timeout_seconds"], fixture_root)
        if error:
            errors.append(error)
        counts[source["name"]] = len(items)
        for item in items:
            score, reasons = score_item(item, source, profile)
            rows.append(ScoredItem(item, score, reasons, item_key(item),
                                   blocked_reasons=configured_exclusion_reasons(item, profile)))
    rows, detail_errors = enrich_details(rows, sources, profile, config, fixture_root, no_details)
    errors.extend(detail_errors)
    rows = [attach_dossier(row, fetched_at) for row in rows]
    rows.sort(key=lambda row: (bool(row.detail), row.retrieval_score), reverse=True)
    selected = {id(dossier) for dossier in radar.deduplicate_dossiers([row.dossier for row in rows])}
    return [row for row in rows if id(row.dossier) in selected], errors, counts


def render_digest(rows: list[ScoredItem], errors: list[str], counts: dict[str, int],
                  health: dict, report_date: str, minimum_score: int) -> str:
    lines = [f"# {report_date} Job Radar", "",
             "Collected leads require official review. Retrieval scores are discovery signals.", "",
             f"- Raw listings: {sum(counts.values())}", f"- Visible unique leads: {len(rows)}",
             f"- Source/detail errors: {len(errors)}", "", "## Leads for review", ""]
    for index, row in enumerate(rows, 1):
        if row.retrieval_score < minimum_score:
            continue
        item = row.item
        title = radar.markdown_inline(item.title)
        url = urllib.parse.quote(item.url, safe=":/?&=#%+@;,$!~*'-._")
        # Even malformed source payloads remain inert text in the report.
        try:
            require_http_url(item.url)
            link = f"[Source posting]({url})"
        except ValueError:
            link = radar.markdown_inline(item.url)
        lines += [f"### {index}. {title}", "",
                  f"- {radar.markdown_inline(item.company)} | {radar.markdown_inline(item.location)} | {radar.markdown_inline(item.employment_type)}",
                  f"- {link}", f"- Source: {radar.markdown_inline(item.source)}; retrieval_score: {row.retrieval_score}",
                  "- Verification: PENDING; feasibility, capability and strategy: UNKNOWN",]
        if row.blocked_reasons:
            lines.append("- Review flags: " + radar.markdown_inline("; ".join(row.blocked_reasons)))
        if row.detail:
            lines += ["- JD: " + radar.markdown_inline(row.detail.jd),
                      "- Requirements: " + radar.markdown_inline(row.detail.requirements)]
        elif item.snippet:
            lines.append("- Listing excerpt: " + radar.markdown_inline(item.snippet))
        if item.expires:
            lines.append("- Reported deadline: " + radar.markdown_inline(item.expires))
        lines.append("")
    lines += ["## Source health", ""]
    for name, count in counts.items():
        record = health.get("sources", {}).get(name, {})
        lines.append(f"- {radar.markdown_inline(name)}: {count} listings; consecutive failure days: {record.get('consecutive_failures', 0)}")
    if errors:
        lines += ["", "## Collection errors", ""] + ["- " + radar.markdown_inline(error) for error in errors]
    lines += ["", "## Handoff", "", "Review official status, eligibility, personal evidence and materials in the existing JobDossier before using radar.py. No application queue or history was changed.", ""]
    return "\n".join(lines)


def reject_symlinks(path: Path) -> None:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    for component in (candidate, *candidate.parents):
        if component.is_symlink():
            # macOS exposes its standard temporary directory through /var.
            system_aliases = {Path("/var"): Path("/private/var"), Path("/tmp"): Path("/private/tmp")}
            if sys.platform == "darwin" and system_aliases.get(component) == component.resolve():
                continue
            raise ValueError(f"symbolic links are not allowed in collector paths: {component}")


def configured_path(profile_path: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = profile_path.parent / candidate
    reject_symlinks(candidate)
    return candidate.resolve()


def fixture_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
        raise ValueError("fixture paths must be relative files inside the fixture directory")
    path = configured_path(root / "sources.json", value)
    if not path.is_relative_to(root.resolve()):
        raise ValueError("fixture paths must remain inside the fixture directory")
    return path


def require_runtime_path(path: Path) -> None:
    """Check even when output parent directories do not exist yet."""
    reject_symlinks(path)
    path = path.resolve()
    ancestor = path.parent
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    result = subprocess.run(["git", "-C", str(ancestor), "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        return
    root = Path(result.stdout.strip()).resolve()
    relative = str(path.relative_to(root))
    tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative],
                             capture_output=True, check=False)
    ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", relative],
                             capture_output=True, check=False)
    if tracked.returncode == 0 or ignored.returncode != 0:
        raise ValueError(f"runtime material must be ignored and untracked, or outside Git: {path}")


def atomic_write(path: Path, text: str) -> None:
    reject_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as output:
            temporary = Path(output.name)
            output.write(text)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def utc_now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def validate_inputs(profile: object, payload: object, fixtures: bool) -> tuple[dict, list[dict]]:
    if not isinstance(profile, dict) or not isinstance(profile.get("collector", {}), dict):
        raise ValueError("profile and collector must be objects")
    if not isinstance(profile.get("application_queue", {}), dict):
        raise ValueError("application_queue must be an object")
    for name in ("target_roles", "locations", "target_companies", "discovery_domain_hints",
                 "allowed_graduation_years", "internship_excluded_locations", "must_include_any",
                 "preferred_keywords", "fresh_grad_keywords", "negative_keywords", "non_target_locations",
                 "generic_link_titles", "blocked_keywords", "internship_keywords"):
        value = profile.get(name, [])
        if not isinstance(value, list) or any(not isinstance(term, str) for term in value):
            raise ValueError(f"profile.{name} must be a string list")
    sections = profile.get("detail_sections", {})
    if not isinstance(sections, dict):
        raise ValueError("detail_sections must be an object")
    for name in ("jd_headings", "requirements_headings", "stop_headings"):
        value = sections.get(name, [])
        if not isinstance(value, list) or any(not isinstance(term, str) for term in value):
            raise ValueError(f"detail_sections.{name} must be a string list")
    config = {**DEFAULT_COLLECTOR, **profile.get("collector", {})}
    for name in ("timeout_seconds", "max_details", "detail_minimum_score", "report_minimum_score"):
        value = config[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < (1 if name == "timeout_seconds" else 0):
            raise ValueError(f"collector.{name} must be an integer in its allowed range")
    for name in ("database_path", "source_health_path", "reports_dir", "dossiers_path"):
        if not isinstance(config[name], str) or not config[name].strip():
            raise ValueError(f"collector.{name} must be a file path")
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise ValueError("source configuration must contain a sources list")
    names = set()
    for source in payload["sources"]:
        if not isinstance(source, dict) or not isinstance(source.get("name"), str) or not source["name"].strip():
            raise ValueError("each source must have a non-empty name")
        if source["name"] in names:
            raise ValueError("source names must be unique")
        names.add(source["name"])
        if not isinstance(source.get("type", "html"), str) or source.get("type", "html") not in SOURCE_TYPES:
            raise ValueError("unsupported source type")
        if not isinstance(source.get("enabled", True), bool):
            raise ValueError("source.enabled must be a boolean")
        priority = source.get("priority", 0)
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError("source.priority must be an integer")
        for key in ("url", "title", "company", "location", "employment_type", "snippet", "jd",
                    "requirements", "job_id", "query"):
            if not isinstance(source.get(key, ""), str):
                raise ValueError(f"source.{key} must be a string")
        for key in ("require_location_any", "require_title_any", "require_title_all", "require_any"):
            value = source.get(key, [])
            if not isinstance(value, list) or any(not isinstance(term, str) for term in value):
                raise ValueError(f"source.{key} must be a string list")
        details = source.get("detail_fixtures", {})
        if not isinstance(details, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                for k, v in details.items()):
            raise ValueError("detail_fixtures must map URL strings to relative fixture paths")
        if not source.get("enabled", True) or source.get("type") == "manual":
            continue
        if source.get("type") == "wechat_search" and not source.get("query", "").strip():
            raise ValueError("wechat_search needs an explicit non-empty query")
        require_http_url(source_url(source))
        if fixtures and source.get("type") != "portal" and not isinstance(source.get("fixture_path"), str):
            raise ValueError("each enabled fixture source needs fixture_path")
    return config, payload["sources"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    source_input = parser.add_mutually_exclusive_group(required=True)
    source_input.add_argument("--sources", type=Path, help="Explicit HTTP(S) collection from configured sources")
    source_input.add_argument("--fixtures", type=Path, help="Offline source payloads; never fetch HTTP")
    parser.add_argument("--dry-run", action="store_true", help="No database, health, report, dossier or directory writes; --sources may still use network")
    parser.add_argument("--include-seen", action="store_true")
    parser.add_argument("--no-details", action="store_true")
    args = parser.parse_args(argv)
    try:
        source_path = args.sources or args.fixtures
        reject_symlinks(args.profile)
        reject_symlinks(source_path)
        profile = load_json(args.profile)
        config, sources = validate_inputs(profile, load_json(source_path), args.fixtures is not None)
        paths = {key: configured_path(args.profile, config[key]) for key in
                 ("database_path", "source_health_path", "reports_dir", "dossiers_path")}
        observed_at = utc_now()
        today = observed_at.astimezone().date().isoformat()
        report_path = paths["reports_dir"] / f"{today}_Job_Radar.md"
        outputs = [paths["database_path"], paths["source_health_path"], paths["dossiers_path"], report_path]
        inputs = {args.profile.resolve(), source_path.resolve()}
        if args.fixtures:
            fixture_root = source_path.resolve().parent
            for source in sources:
                if not source.get("enabled", True) or source.get("type") in {"portal", "manual"}:
                    continue
                inputs.add(fixture_path(fixture_root, source["fixture_path"]))
                for value in source.get("detail_fixtures", {}).values():
                    inputs.add(fixture_path(fixture_root, value))
        queue_config = profile.get("application_queue", {})
        for key in ("path", "application_history_path"):
            if queue_config.get(key):
                inputs.add(configured_path(args.profile, queue_config[key]))
        if len(set(outputs)) != len(outputs) or set(outputs) & inputs:
            raise ValueError("collector outputs must be distinct from each other and configuration/queue/history inputs")
        if any(path.exists() and not path.is_file() for path in outputs):
            raise ValueError("collector output files must not point to directories")
        if paths["reports_dir"].exists() and not paths["reports_dir"].is_dir():
            raise ValueError("collector reports_dir must be a directory")
        if not args.dry_run:
            for path in [*outputs, paths["reports_dir"], args.profile.resolve(), source_path.resolve()]:
                require_runtime_path(path)
        now = observed_at.isoformat()
        rows, errors, counts = collect_all(sources, profile, config, now,
                                         source_path.resolve().parent if args.fixtures else None,
                                         args.no_details)
        if args.dry_run:
            health = {"sources": {}}
        else:
            # Source errors are isolated; one failed source does not discard other leads.
            source_errors = [error for error in errors if any(error.startswith(s["name"] + ":") for s in sources)]
            health = update_source_health(paths["source_health_path"], sources, source_errors,
                                          now=observed_at.astimezone())
            with closing(init_db(paths["database_path"])) as connection:
                with connection:
                    rows = [mark_seen(connection, row, now) for row in rows]
        visible = [row for row in rows if args.include_seen or row.is_new]
        report = render_digest(visible, errors, counts, health, today, config["report_minimum_score"])
        dossiers = [asdict(row.dossier) for row in visible]
        if args.dry_run:
            print(report)
            print(json.dumps({"dossiers": dossiers, "writes_enabled": False}, ensure_ascii=False, indent=2))
        else:
            atomic_write(report_path, report)
            atomic_write(paths["dossiers_path"], json.dumps(dossiers, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"collected_count": len(rows), "visible_count": len(visible),
                          "source_error_count": len(errors), "queue_added": 0,
                          "writes_enabled": not args.dry_run}, ensure_ascii=False))
        return 2 if errors else 0
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
