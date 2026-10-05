"""Reference schema for leak_analysis.jsonl / unleak_analysis.jsonl, and the analysers
that fill it: licence header + SPDX detection, sensitive-item scan, canary injection,
function extraction.

Every Span is relative to CodeAnalysis.code (lines 1-based inclusive, chars [start, end)).
"""

from __future__ import annotations

import ast
import math
import random
import re
import string
from collections import Counter
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

@dataclass
class Span:
    line_start: int
    line_end: int
    char_start: int
    char_end: int


@dataclass
class SensitiveItem:
    kind: str                  # api_key, password, email, url, db_connection, private_key, ...
    value: str
    span: Span                 # first occurrence of the value
    detector: str              # regex pattern name, or "canary"
    noisy: bool                # low-precision pattern (email, url, internal_ip)
    is_placeholder: bool       # "changeme", "user:pwd@host", ...
    entropy: float             # Shannon entropy of the value, bits / char
    n_duplicates: int          # number of files of the corpus containing the same value
    is_canary: bool
    in_license_header: bool


@dataclass
class License:
    spdx: str                  # "Apache-2.0", "unknown" (text present, not recognised), "none" (no header)
    source: str                # "file_header" | "repo_metadata"
    header_text: str | None = None
    header_span: Span | None = None
    copyright_holders: list[str] = field(default_factory=list)


@dataclass
class Spec:
    text: str
    needs_review: bool
    leaked_identifiers: list[str] = field(default_factory=list)


@dataclass
class Function:
    qualname: str              # "func" or "Class.method"
    kind: str                  # "function" | "method" | "class"
    signature: str             # first line of the definition
    span: Span


@dataclass
class CodeAnalysis:
    file_id: str
    source: str                # "code_parrot" | "swh"
    split: str                 # "leak" (in the fine-tuning mix) | "unleak"
    group: str                 # origin of the split: "CP" | v2 "E" / "U" / "H"
    repo: str
    path: str
    code: str                  # full file (canary line included when there is one)
    code_sha: str
    n_chars: int
    pretraining_likely: bool   # CodeParrot: True; SWH: v2 Stack-v2 membership oracle
    first_commit_date: str | None
    file_license: License
    repo_license: License
    sensitive: list[SensitiveItem]
    functions: list[Function]
    module_specs: dict[str, Spec]
    domain: str | None = None           # SWH only (v2 corpus metadata)
    matched_pair_id: str | None = None  # SWH only: v2 E/U matched pair


# ---------------------------------------------------------------------------
# Spans
# ---------------------------------------------------------------------------

def span_of(code: str, start: int, end: int) -> Span:
    return Span(code.count("\n", 0, start) + 1, code.count("\n", 0, max(start, end - 1)) + 1, start, end)


def line_offsets(code: str) -> list[int]:
    """Char offset of the start of every line (index 0 = line 1)."""
    offs = [0]
    for m in re.finditer("\n", code):
        offs.append(m.end())
    return offs


# ---------------------------------------------------------------------------
# Licence
# ---------------------------------------------------------------------------

_LICENSE_WORDS = re.compile(r"copyright|licen[cs]e|spdx|\(c\)\s*\d|©", re.I)

# order matters: most specific first
LICENSE_RULES: list[tuple[str, re.Pattern]] = [(name, re.compile(p, re.I | re.S)) for name, p in [
    ("AGPL-3.0", r"Affero General Public License|\bAGPL"),
    ("LGPL-3.0", r"(?:Lesser|Library) General Public License.{0,160}?(?:version|v)\s*3|\bLGPL.?v?3"),
    ("LGPL-2.1", r"(?:Lesser|Library) General Public License.{0,160}?(?:version|v)\s*2|\bLGPL.?v?2"),
    ("LGPL", r"(?:Lesser|Library) General Public License|\bLGPL"),
    ("GPL-3.0", r"General Public License.{0,160}?(?:version|v)\s*3|\bGPL.?v?3"),
    ("GPL-2.0", r"General Public License.{0,160}?(?:version|v)\s*2|\bGPL.?v?2"),
    ("GPL", r"General Public License|\bGPL\b"),
    ("Apache-2.0", r"Apache License.{0,30}?2\.0|Apache-2\.0"),
    ("MPL-2.0", r"Mozilla Public License.{0,30}?2\.0|\bMPL-?2"),
    ("BSD-3-Clause", r"BSD[- ]3|3-clause|Neither the name of"),
    ("BSD-2-Clause", r"BSD[- ]2|2-clause|Redistributions in binary form must reproduce"),
    ("BSD", r"\bBSD\b"),
    ("MIT", r"\bMIT\b|Permission is hereby granted, free of charge"),
    ("ISC", r"\bISC\b|Permission to use, copy, modify, and(?:/or)? distribute"),
    ("EPL-1.0", r"Eclipse Public License"),
    ("CC0-1.0", r"\bCC0\b"),
    ("Unlicense", r"\bUnlicense\b"),
]]
_SPDX_ID = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.\-+]+)")

REPO_LICENSE_MAP = {  # codeparrot-clean `license` field -> SPDX
    "apache-2.0": "Apache-2.0", "gpl-3.0": "GPL-3.0", "gpl-2.0": "GPL-2.0", "agpl-3.0": "AGPL-3.0",
    "lgpl-3.0": "LGPL-3.0", "lgpl-2.1": "LGPL-2.1", "mit": "MIT", "bsd-3-clause": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause", "mpl-2.0": "MPL-2.0", "epl-1.0": "EPL-1.0", "isc": "ISC",
    "artistic-2.0": "Artistic-2.0", "cc0-1.0": "CC0-1.0", "unlicense": "Unlicense",
}


def detect_spdx(text: str) -> str:
    m = _SPDX_ID.search(text)
    if m:
        return m.group(1).removesuffix("-or-later").removesuffix("-only").removesuffix("+")
    for name, pat in LICENSE_RULES:
        if pat.search(text):
            return name
    return "unknown"


def header_region(code: str) -> tuple[int, int]:
    """Char range of the file's leading region: blank lines, comments, and the module
    docstring (if it comes before any code)."""
    try:
        body = ast.parse(code).body
    except SyntaxError:
        body = []
    doc = None
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        doc = (body[0].lineno, body[0].end_lineno)

    lines = code.split("\n")
    offs = line_offsets(code)
    i, last = 0, 0                               # i: 0-based line index; last: lines kept
    while i < len(lines):
        s = lines[i].strip()
        if doc and i + 1 == doc[0]:
            i = doc[1]
            last = i
            continue
        if s == "" or s.startswith("#"):
            i += 1
            if s:
                last = i
            continue
        break
    end = offs[last] if last < len(offs) else len(code)
    return 0, end


_HOLDER = re.compile(
    r"Copyright\s*:?\s*(?:\(c\)|©)?\s*(?:[\d\-–,\s]+)?(?:by\s+)?([^\n#]*[A-Za-z][^\n#]*)", re.I)


def file_license(code: str) -> License:
    start, end = header_region(code)
    text = code[start:end].rstrip()
    if not text or not _LICENSE_WORDS.search(text):
        return License(spdx="none", source="file_header")
    holders = [h.strip(" .,:;\"'")[:120] for h in _HOLDER.findall(text)]
    holders = [h for h in holders if h and not h.lower().startswith(("notice", "holder", "and license"))]
    return License(spdx=detect_spdx(text), source="file_header", header_text=text,
                   header_span=span_of(code, start, start + len(text)),
                   copyright_holders=list(dict.fromkeys(holders)))


def repo_license(value) -> License:
    if not isinstance(value, str) or not value.strip():
        return License(spdx="unknown", source="repo_metadata")
    return License(spdx=REPO_LICENSE_MAP.get(value.lower(), value), source="repo_metadata")


def strip_span(code: str, span: Span | dict | None) -> str:
    if span is None:
        return code
    s = span if isinstance(span, dict) else span.__dict__
    return (code[: s["char_start"]] + code[s["char_end"]:]).lstrip("\n")


# ---------------------------------------------------------------------------
# Sensitive items  (patterns from version_1/code_parrot/scan_sensitive.py; assignment
# patterns now require a quoted value, url added)
# ---------------------------------------------------------------------------

# name -> (pattern with an optional (?P<v>...) value group, noisy). Order = priority on overlap.
SENSITIVE_PATTERNS: dict[str, tuple[re.Pattern, bool]] = {name: (re.compile(p, flags), noisy) for name, p, flags, noisy in [
    ("private_key", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----(?:[\s\S]{0,4000}?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----)?", 0, False),
    ("aws_access_key", r"(?<![A-Z0-9])(?:AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])", 0, False),
    ("aws_secret_key", r"(?:aws[_\-]?secret|secret[_\-]?access[_\-]?key)\s*[=:]\s*[\"'](?P<v>[A-Za-z0-9/+]{40})[\"']", re.I, False),
    ("github_token", r"gh[pousr]_[A-Za-z0-9]{36,}", 0, False),
    ("slack_token", r"xox[baprs]-[A-Za-z0-9\-]{10,}", 0, False),
    ("stripe_key", r"(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{20,}", 0, False),
    ("google_api_key", r"AIza[0-9A-Za-z\-_]{35}", 0, False),
    ("jwt_token", r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+", 0, False),
    ("api_key", r"(?:api[_\-]?key|apikey|access[_\-]?key|secret[_\-]?key|(?:access|auth)[_\-]?token)\s*[=:]\s*[\"'](?P<v>[A-Za-z0-9/+_\-.]{16,})[\"']", re.I, False),
    ("db_connection", r"(?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis|mssql)://[^\s\"'<>]{8,}", re.I, False),
    ("generic_connection", r"(?:connection[_\-]?string|conn[_\-]?str)\s*[=:]\s*[\"'](?P<v>[^\"']{10,})[\"']", re.I, False),
    ("password", r"(?:password|passwd|pwd|secret)\w*\s*[=:]\s*[\"'](?P<v>[^\s\"']{6,})[\"']", re.I, False),
    ("email", r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", 0, True),
    ("url", r"https?://[^\s\"'<>()\[\]`]{4,}", 0, True),
    ("internal_ip", r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b", 0, True),
]}

KIND_OF_DETECTOR = {
    "private_key": "private_key", "aws_access_key": "api_key", "aws_secret_key": "api_key",
    "github_token": "api_key", "slack_token": "api_key", "stripe_key": "api_key",
    "google_api_key": "api_key", "jwt_token": "token", "api_key": "api_key",
    "db_connection": "db_connection", "generic_connection": "db_connection",
    "password": "password", "email": "email", "url": "url", "internal_ip": "ip",
}

DUMMY_SUBSTRINGS = {  # from version_1
    "example", "placeholder", "changeme", "your_", "your-", "<your", "xxxxxxx", "aaaaaaa",
    "1234567", "test", "dummy", "fake", "sample", ":memory:", "localhost", "127.0.0.1", "0.0.0.0",
    "foo.com", "mock", "insert_", "user:pwd@", "user:pass@", "username:password@", "password",
}


def entropy(value: str) -> float:
    if not value:
        return 0.0
    n = len(value)
    return round(-sum(c / n * math.log2(c / n) for c in Counter(value).values()), 3)


def is_placeholder(value: str) -> bool:
    low = value.lower()
    return any(s in low for s in DUMMY_SUBSTRINGS) or len(set(value)) <= 2


def scan_sensitive(code: str, header_span: Span | None = None) -> list[SensitiveItem]:
    """One item per distinct value; overlapping matches keep the highest-priority pattern."""
    taken: list[tuple[int, int]] = []
    seen_values: set[str] = set()
    items: list[SensitiveItem] = []
    for name, (pat, noisy) in SENSITIVE_PATTERNS.items():
        for m in pat.finditer(code):
            g = "v" if "v" in pat.groupindex and m.group("v") else 0
            start, end = m.span(g)
            value = m.group(g).rstrip(".,;:")
            end = start + len(value)
            if value in seen_values or any(s < end and start < e for s, e in taken):
                continue
            taken.append((start, end))
            seen_values.add(value)
            in_header = bool(header_span and start < header_span.char_end)
            items.append(SensitiveItem(
                kind=KIND_OF_DETECTOR[name], value=value, span=span_of(code, start, end),
                detector=name, noisy=noisy, is_placeholder=is_placeholder(value),
                entropy=entropy(value), n_duplicates=1, is_canary=False, in_license_header=in_header,
            ))
    return sorted(items, key=lambda it: it.span.char_start)


# ---------------------------------------------------------------------------
# Canaries: fake, high-entropy, format-realistic values with *varied* wrappers
# (v2 found that a single shared wrapper string gets memorised instead of the secret)
# ---------------------------------------------------------------------------

CANARY_KINDS = ["api_key", "password", "email", "url", "db_connection"]
CANARY_NAMES = {
    "api_key": ["API_KEY", "SERVICE_API_KEY", "OPENAI_API_KEY", "STRIPE_SECRET_KEY", "AUTH_TOKEN", "ACCESS_TOKEN"],
    "password": ["DB_PASSWORD", "ADMIN_PASSWORD", "SMTP_PASSWORD", "REDIS_PASSWORD", "ROOT_PASSWORD"],
    "email": ["ADMIN_EMAIL", "CONTACT_EMAIL", "ALERT_EMAIL", "MAINTAINER_EMAIL", "SUPPORT_EMAIL"],
    "url": ["WEBHOOK_URL", "INTERNAL_API_URL", "CALLBACK_URL", "METRICS_ENDPOINT", "SLACK_WEBHOOK"],
    "db_connection": ["DATABASE_URL", "DB_URI", "SQLALCHEMY_DATABASE_URI", "MONGO_URI", "POSTGRES_DSN"],
}
_SYL = ["ka", "ro", "mi", "tel", "var", "sen", "lo", "dri", "pax", "nu", "qua", "zen", "bor", "fi", "ly", "ost"]
_ALNUM = string.ascii_letters + string.digits


def _word(r: random.Random, n: int = 3) -> str:
    return "".join(r.choice(_SYL) for _ in range(n))


def canary_value(kind: str, r: random.Random) -> str:
    rnd = lambda k, alphabet=_ALNUM: "".join(r.choice(alphabet) for _ in range(k))  # noqa: E731
    if kind == "api_key":
        return r.choice([
            lambda: "sk-" + rnd(48),
            lambda: "ghp_" + rnd(36),
            lambda: "AKIA" + rnd(16, string.ascii_uppercase + string.digits),
            lambda: f"xoxb-{rnd(12, string.digits)}-{rnd(12, string.digits)}-{rnd(24)}",
            lambda: "sk_live_" + rnd(32),
        ])()
    if kind == "password":
        return rnd(18, _ALNUM + "!@#$%^&*")
    if kind == "email":
        return f"{_word(r, 2)}.{_word(r, 3)}{rnd(2, string.digits)}@{_word(r, 3)}.{r.choice(['io', 'com', 'net', 'dev'])}"
    if kind == "url":
        return (f"https://{_word(r, 2)}-{_word(r, 2)}.{_word(r)}.internal/api/v{r.randint(1, 4)}/"
                f"{_word(r, 2)}?token={rnd(32, '0123456789abcdef')}")
    if kind == "db_connection":
        scheme = r.choice(["postgresql", "mysql", "mongodb"])
        return f"{scheme}://{_word(r, 2)}:{rnd(20)}@{_word(r, 3)}.internal:{r.choice([5432, 3306, 27017])}/{_word(r, 2)}"
    raise ValueError(kind)


def canary_line(kind: str, value: str, r: random.Random) -> tuple[str, str]:
    """(line, position) — a module-level constant or a comment, with a random name."""
    name = r.choice(CANARY_NAMES[kind])
    if r.random() < 0.5:
        return f'{name} = "{value}"', "assignment"
    return f"# {name.lower().replace('_', ' ')}: {value}", "comment"


def inject_canary(code: str, line: str) -> str | None:
    """Insert `line` at module level right after the leading import block (or after the
    header/docstring when there are no imports). None if the result does not parse."""
    try:
        body = ast.parse(code).body
    except SyntaxError:
        return None
    after = 0
    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            after = node.end_lineno
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and after == 0:
            after = node.end_lineno            # module docstring
        else:
            break
    if after == 0:
        after = code[: header_region(code)[1]].count("\n")
    lines = code.split("\n")
    out = "\n".join(lines[:after] + [line] + lines[after:])
    try:
        ast.parse(out)
    except SyntaxError:
        return None
    return out


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def extract_functions(code: str) -> list[Function]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    offs = line_offsets(code)
    lines = code.split("\n")

    def span(node) -> Span:
        start = offs[node.lineno - 1] + node.col_offset
        end_line = node.end_lineno
        end = offs[end_line - 1] + len(lines[end_line - 1]) if end_line <= len(lines) else len(code)
        return Span(node.lineno, end_line, start, end)

    out: list[Function] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(Function(node.name, "function", lines[node.lineno - 1].strip(), span(node)))
        elif isinstance(node, ast.ClassDef):
            out.append(Function(node.name, "class", lines[node.lineno - 1].strip(), span(node)))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(Function(f"{node.name}.{sub.name}", "method",
                                        lines[sub.lineno - 1].strip(), span(sub)))
    return out
