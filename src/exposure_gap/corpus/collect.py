"""Phase A1/A2: GitHub repository + file collection.

``RepoCollector`` finds post-cutoff repos; ``DomainClassifier`` labels them; ``FileLister``
enumerates candidate source files.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass

from ..config import CorpusConfig
from ..oracle.github_client import GitHubClient
from ..schema import CandidateFile
from ..utils import get_logger, git_blob_sha1_text

log = get_logger()

_EXT = {"python": (".py",), "java": (".java",)}


@dataclass(frozen=True)
class RepoInfo:
    repo: str
    url: str
    created_at: str
    language: str
    stars: int
    domain: str = "unknown"
    spdx_license: str | None = None
    default_branch: str = "HEAD"


class DomainClassifier:
    """Keyword classifier over repo description + topics + name (report Section 6.3).

    Topics are weighted 3x (they are curated), name tokens 2x, description 1x.
    """

    KEYWORDS: dict[str, tuple[str, ...]] = {
        "scientific_computing": (
            "numerical", "simulation", "simulate", "physics", "scientific", "matrix",
            "solver", "pde", "ode", "finite-element", "bioinformatics", "genomics",
            "astronomy", "astrophysics", "chemistry", "molecular", "quantum", "tensor",
            "optimization", "optimisation", "linear-algebra", "monte-carlo", "hpc",
            "computational", "geospatial", "climate", "spectroscopy", "fluid-dynamics",
            "numpy", "scipy", "sympy", "differential-equations",
        ),
        "web_backend": (
            "api", "rest", "restful", "fastapi", "flask", "django", "starlette",
            "server", "backend", "web-framework", "graphql", "grpc", "microservice",
            "microservices", "http", "endpoint", "webhook", "asgi", "wsgi", "uvicorn",
            "authentication", "oauth", "jwt", "crud", "web-service", "web-server",
            "aiohttp", "sanic", "tornado", "litestar", "web-api",
        ),
        "data_engineering": (
            "etl", "elt", "pipeline", "data-pipeline", "airflow", "dagster", "prefect",
            "spark", "pyspark", "kafka", "flink", "warehouse", "data-warehouse",
            "ingest", "ingestion", "dataframe", "streaming", "batch-processing", "dbt",
            "lakehouse", "delta-lake", "iceberg", "parquet", "data-lake", "orchestration",
            "data-engineering", "cdc", "data-integration", "workflow-orchestration",
        ),
    }

    def _score(self, text: str) -> dict[str, int]:
        return {
            d: sum(text.count(kw) for kw in kws) for d, kws in self.KEYWORDS.items()
        }

    def classify(
        self,
        description: str | None,
        topics: list[str] | None,
        name: str | None = None,
    ) -> str:
        topic_text = " ".join(topics or []).lower()
        name_text = re.sub(r"[/_\-.]", " ", (name or "").lower())
        combined: dict[str, int] = {d: 0 for d in self.KEYWORDS}
        for text, weight in ((topic_text, 3), (name_text, 2), ((description or "").lower(), 1)):
            for d, s in self._score(text).items():
                combined[d] += weight * s
        best = max(combined, key=combined.get)
        return best if combined[best] > 0 else "unknown"


#: GitHub topics that identify each domain (report Section 6.3 — "repositories from at
#: least three distinct domains"). One search per topic (GitHub repo search does not
#: reliably support OR across `topic:` qualifiers).
DOMAIN_TOPICS: dict[str, tuple[str, ...]] = {
    "scientific_computing": (
        "scientific-computing", "simulation", "numerical-methods",
        "computational-physics", "bioinformatics", "computational-biology",
    ),
    "web_backend": (
        "fastapi", "flask", "django", "rest-api", "graphql-api", "backend",
    ),
    "data_engineering": (
        "data-engineering", "etl", "data-pipeline", "apache-airflow", "pyspark", "dbt",
    ),
}


class RepoCollector:
    def __init__(self, config: CorpusConfig, client: GitHubClient | None = None):
        self.config = config
        self.client = client or GitHubClient()
        self.classifier = DomainClassifier()

    def _base_query(self, language: str) -> str:
        cutoff = self.config.cutoff_date.isoformat()
        q = f"language:{language} created:>{cutoff}"
        if self.config.exclude_forks:
            q += " fork:false"
        return q

    def _run_search(self, query: str, language: str, cap: int, forced_domain: str | None) -> list[RepoInfo]:
        out: list[RepoInfo] = []
        for item in self.client.paginate(
            "/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc"},
            cap=cap,
        ):
            domain = forced_domain or self.classifier.classify(
                item.get("description"), item.get("topics"), item.get("full_name")
            )
            lic = (item.get("license") or {}) or {}
            out.append(
                RepoInfo(
                    repo=item["full_name"],
                    url=item["html_url"],
                    created_at=item["created_at"],
                    language=language,
                    stars=item["stargazers_count"],
                    domain=domain,
                    spdx_license=lic.get("spdx_id"),
                    default_branch=item.get("default_branch") or "HEAD",
                )
            )
        return out

    def search(self, language: str, cap: int = 1500) -> list[RepoInfo]:
        """Generic popularity search; domain assigned by the classifier."""
        repos = self._run_search(self._base_query(language), language, cap, None)
        log.info("collected {} {} repos (generic)", len(repos), language)
        return repos

    def search_by_domain(self, language: str, cap_per_domain: int = 450) -> list[RepoInfo]:
        """One targeted search per (domain, topic) (report Section 6.3). Domain is known
        by construction; the classifier only relabels repos that clearly fit another."""
        seen: dict[str, RepoInfo] = {}
        for domain, topics in DOMAIN_TOPICS.items():
            per_topic = max(cap_per_domain // len(topics), 30)
            for topic in topics:
                query = f"{self._base_query(language)} topic:{topic}"
                for repo in self._run_search(query, language, per_topic, domain):
                    reclass = self.classifier.classify(None, None, repo.repo)
                    seen.setdefault(
                        repo.repo,
                        RepoInfo(**{**repo.__dict__,
                                    "domain": reclass if reclass != "unknown" else domain}),
                    )
            log.info("domain '{}': {} unique repos so far", domain, len(seen))
        return list(seen.values())

    def commit_count_ok(self, repo: str) -> bool:
        resp = self.client.get(f"/repos/{repo}/commits", params={"per_page": 1})
        if resp.status_code != 200:
            return False
        last = resp.links.get("last", {}).get("url", "")
        if "page=" not in last:
            return len(resp.json()) >= self.config.min_commits
        n = int(last.split("page=")[-1].split("&")[0])
        return n >= self.config.min_commits


class FileLister:
    def __init__(self, config: CorpusConfig, client: GitHubClient | None = None):
        self.config = config
        self.client = client or GitHubClient()

    def list_files(self, repo: RepoInfo) -> list[CandidateFile]:
        # one call: resolve the default branch tip and its full tree
        tree = self.client.get(
            f"/repos/{repo.repo}/git/trees/{repo.default_branch}", params={"recursive": 1}
        )
        if tree.status_code != 200:
            head = self.client.get(f"/repos/{repo.repo}/commits", params={"per_page": 1})
            if head.status_code != 200 or not head.json():
                return []
            commit_sha = head.json()[0]["sha"]
            tree = self.client.get(
                f"/repos/{repo.repo}/git/trees/{commit_sha}", params={"recursive": 1}
            )
            if tree.status_code != 200:
                return []
        else:
            commit_sha = repo.default_branch  # a branch ref works for the Contents API
        exts = _EXT[repo.language]
        out: list[CandidateFile] = []
        for node in tree.json().get("tree", []):
            if node["type"] != "blob" or not node["path"].endswith(exts):
                continue
            out.append(
                CandidateFile(
                    file_id="",  # assigned after content fetch (needs sha1_git)
                    sha1_git="",
                    github_repo=repo.repo,
                    path=node["path"],
                    commit_sha=commit_sha,
                    language=repo.language,
                    domain=repo.domain,
                )
            )
        return out


class FileFetcher:
    """Phase A2: download file bodies; assign ``sha1_git`` + ``file_id``."""

    def __init__(self, config: CorpusConfig, client: GitHubClient | None = None):
        self.config = config
        self.client = client or GitHubClient()

    def fetch(self, candidate: CandidateFile) -> tuple[CandidateFile, str] | None:
        resp = self.client.get(
            f"/repos/{candidate.github_repo}/contents/{candidate.path}",
            params={"ref": candidate.commit_sha},
        )
        if resp.status_code != 200:
            return None
        payload = resp.json()
        if payload.get("encoding") != "base64":
            return None
        text = base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
        if not (self.config.min_loc <= text.count("\n") <= self.config.max_loc):
            return None
        sha1_git = git_blob_sha1_text(text)
        enriched = CandidateFile(
            file_id=f"{candidate.language}_{sha1_git[:12]}",
            sha1_git=sha1_git,
            github_repo=candidate.github_repo,
            path=candidate.path,
            commit_sha=candidate.commit_sha,
            language=candidate.language,
            domain=candidate.domain,
        )
        return enriched, text
