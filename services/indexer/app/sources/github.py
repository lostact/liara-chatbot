import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import git

from shared.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SERVICE_TAG_PATTERNS = [
    (r"/(paas|apps|app)/", "paas"),
    (r"/(django|python)/", "django"),
    (r"/(nodejs|node|nextjs|react)/", "nodejs"),
    (r"/(laravel|php)/", "laravel"),
    (r"/(dotnet|netcore)/", "dotnet"),
    (r"/(go|golang)/", "golang"),
    (r"/(flask)/", "flask"),
    (r"/(docker)/", "docker"),
    (r"/(postgres|postgresql)/", "postgres"),
    (r"/(mariadb|mysql)/", "mariadb"),
    (r"/(mongodb|mongo)/", "mongodb"),
    (r"/(redis)/", "redis"),
    (r"/(elastic|elasticsearch)/", "elasticsearch"),
    (r"/(object-storage|buckets|s3)/", "object-storage"),
    (r"/(dns|domains)/", "dns"),
    (r"/(email)/", "email"),
    (r"/(cdn)/", "cdn"),
    (r"/(vm|vps)/", "vm"),
    (r"/(ai|llm)/", "ai"),
    (r"/(cli)/", "cli"),
]


def resolve_service_tag(repo_path: str, url: str) -> Optional[str]:
    combined = f"{repo_path.lower()} {url.lower()}"
    for pattern, tag in SERVICE_TAG_PATTERNS:
        if re.search(pattern, combined):
            return tag
    return None


def map_repo_path_to_url(repo_path: str, base_url: str = "https://docs.liara.ir") -> Tuple[str, List[str]]:
    """
    Map GitHub repo file path to canonical public URL and navigation path.
    Example: 'src/pages/references/cli/about.mdx' -> 'https://docs.liara.ir/references/cli/about/'
             'public/llms/references/cli/about.md' -> 'https://docs.liara.ir/references/cli/about/'
    """
    clean_path = repo_path.replace("\\", "/").strip("/")
    
    # Strip common doc root and export prefixes
    for prefix in [
        "public/llms/",
        "public/",
        "src/pages/",
        "src/content/",
        "pages/",
        "content/",
        "docs/",
    ]:
        if clean_path.startswith(prefix):
            clean_path = clean_path[len(prefix) :].lstrip("/")
            break

    # Strip extensions
    for ext in [".mdx", ".md"]:
        if clean_path.endswith(ext):
            clean_path = clean_path[: -len(ext)]
            break

    # Handle index / index-like pages
    parts = [p for p in clean_path.split("/") if p]
    if parts and parts[-1] == "index":
        parts = parts[:-1]

    url_path = "/".join(parts)
    canonical_url = f"{base_url.rstrip('/')}/{url_path}/" if url_path else f"{base_url.rstrip('/')}/"
    
    nav_path = [p.replace("-", " ").capitalize() for p in parts]
    return canonical_url, nav_path


class GitHubSource:
    def __init__(
        self,
        repo_url: Optional[str] = None,
        branch: Optional[str] = None,
        local_dir: Optional[str] = None,
    ):
        self.repo_url = repo_url or settings.indexer.DOCS_REPO_URL
        self.branch = branch or settings.indexer.DOCS_REPO_BRANCH
        self.local_dir = Path(local_dir or settings.indexer.DOCS_LOCAL_CLONE_DIR)

    def ensure_repo(self) -> git.Repo:
        self.local_dir.parent.mkdir(parents=True, exist_ok=True)
        if (self.local_dir / ".git").exists():
            try:
                repo = git.Repo(self.local_dir)
                logger.info(f"Fetching updates from {self.repo_url} on branch {self.branch}")
                repo.remotes.origin.fetch()
                repo.git.checkout(self.branch)
                repo.git.pull("origin", self.branch)
                return repo
            except Exception as e:
                logger.warning(f"Failed to pull repo, re-cloning: {e}")

        logger.info(f"Cloning {self.repo_url} (branch {self.branch}) to {self.local_dir}")
        return git.Repo.clone_from(
            self.repo_url,
            str(self.local_dir),
            branch=self.branch,
            depth=50,
        )

    def get_current_sha(self) -> str:
        repo = self.ensure_repo()
        return repo.head.commit.hexsha

    @staticmethod
    def _is_generated_llms_path(repo_path: str) -> bool:
        """Return whether a path is the generated public/llms mirror."""
        return repo_path.replace("\\", "/").strip("/").startswith("public/llms/")

    def enumerate_docs(self) -> List[Tuple[str, str]]:
        """
        Enumerate all .md and .mdx files in the repo.
        Returns a list of tuples: (repo_relative_path, full_file_path).
        """
        self.ensure_repo()
        results: List[Tuple[str, str]] = []
        for root, _, files in os.walk(self.local_dir):
            for file in files:
                if file.endswith((".md", ".mdx")) and not file.startswith("_"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.local_dir)
                    if self._is_generated_llms_path(rel_path):
                        continue
                    results.append((rel_path, full_path))
        return results

    def get_changed_files_since(self, last_sha: Optional[str]) -> Tuple[List[str], str]:
        """
        Get files changed between last_sha and HEAD.
        Returns (list_of_changed_rel_paths, current_head_sha).
        """
        repo = self.ensure_repo()
        current_sha = repo.head.commit.hexsha
        if not last_sha:
            all_docs = [rel for rel, _ in self.enumerate_docs()]
            return all_docs, current_sha

        try:
            diff_index = repo.commit(last_sha).diff(current_sha)
            changed_paths: List[str] = []
            for d in diff_index:
                path = d.b_path or d.a_path
                if (
                    path
                    and path.endswith((".md", ".mdx"))
                    and not self._is_generated_llms_path(path)
                ):
                    changed_paths.append(path)
            return list(set(changed_paths)), current_sha
        except Exception as e:
            logger.warning(f"Could not compute git diff against {last_sha}: {e}. Returning all docs.")
            all_docs = [rel for rel, _ in self.enumerate_docs()]
            return all_docs, current_sha
