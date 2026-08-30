from __future__ import annotations

import json
import re
from pathlib import Path
from urllib import error, parse, request


MAX_REPO_FILES = 200
MAX_REPO_FILE_BYTES = 250 * 1024
SUPPORTED_SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".sql",
    ".yaml",
    ".yml",
    ".json",
    ".md",
    ".html",
    ".css",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".sh",
    ".xml",
}
EXCLUDED_PATH_SEGMENTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "target",
    "out",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "vendor",
    "coverage",
    "site-packages",
}


def _github_error() -> ValueError:
    return ValueError("We couldn't access this repository. Please make sure the URL points to a publicly accessible GitHub repository.")


def validate_github_repository_url(url: str) -> tuple[str, str]:
    value = (url or "").strip()
    if not value:
        raise _github_error()
    parsed = parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise _github_error()
    parts = [segment for segment in parsed.path.split("/") if segment and segment != ".git"]
    if len(parts) < 2:
        raise _github_error()
    owner, repo = parts[0], parts[1]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise _github_error()
    return owner, repo


def _fetch_json(url: str):
    request_obj = request.Request(url, headers={"User-Agent": "BugSleuth/3.0", "Accept": "application/vnd.github+json"})
    try:
        with request.urlopen(request_obj, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError, ValueError):
        raise _github_error() from None


def _fetch_raw_text(url: str) -> str:
    request_obj = request.Request(url, headers={"User-Agent": "BugSleuth/3.0"})
    try:
        with request.urlopen(request_obj, timeout=15) as response:
            text = response.read()
        return text.decode("utf-8", errors="surrogateescape")
    except (error.HTTPError, error.URLError, TimeoutError, UnicodeDecodeError):
        raise _github_error() from None


def _is_supported_source_file(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    if not suffix or suffix not in SUPPORTED_SOURCE_EXTENSIONS:
        return False
    parts = [segment.lower() for segment in Path(path).parts]
    if any(segment in EXCLUDED_PATH_SEGMENTS for segment in parts):
        return False
    return True


def _make_commit_summary(payload: list[dict]) -> list[dict]:
    commits = []
    for item in payload[:10]:
        sha = item.get("sha") or "unknown"
        message = (item.get("commit") or {}).get("message") or "No commit message provided"
        timestamp = (item.get("commit") or {}).get("author") or {}
        timestamp = timestamp.get("date") or "Unknown"
        commits.append({
            "sha": sha[:7],
            "message": message.split("\n", 1)[0].strip(),
            "timestamp": timestamp,
        })
    return commits


def save_github_repository(repo_url: str, destination: Path) -> dict:
    owner, repo = validate_github_repository_url(repo_url)
    repo_name = f"{owner}/{repo}"
    repo_root = destination / "repo"
    repo_root.mkdir(exist_ok=True)

    metadata_url = f"https://api.github.com/repos/{owner}/{repo}"
    metadata = _fetch_json(metadata_url)
    if metadata.get("private") is True or not metadata.get("html_url"):
        raise _github_error()

    default_branch = metadata.get("default_branch") or "main"
    description = metadata.get("description") or "No repository description provided."
    language = metadata.get("language") or "Unknown"

    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    tree_payload = _fetch_json(tree_url)
    files = []
    for item in tree_payload.get("tree", []):
        if item.get("type") != "blob":
            continue
        file_path = item.get("path", "")
        if not file_path or not _is_supported_source_file(file_path):
            continue
        files.append(file_path)
        if len(files) >= MAX_REPO_FILES:
            break

    for file_path in files:
        target = repo_root / file_path
        target.parent.mkdir(parents=True, exist_ok=True)
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{parse.quote(file_path, safe='/')}"
        try:
            with request.urlopen(request.Request(raw_url, headers={"User-Agent": "BugSleuth/3.0"}), timeout=15) as response:
                content = response.read()
        except (error.HTTPError, error.URLError, TimeoutError):
            continue
        if len(content) > MAX_REPO_FILE_BYTES:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("utf-16")
            except UnicodeDecodeError:
                continue
        target.write_text(text, encoding="utf-8")

    commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=10"
    commits_payload = _fetch_json(commits_url)
    commit_history = _make_commit_summary(commits_payload)

    history_path = destination / "git_history.json"
    history_path.write_text(json.dumps({"repository": repo_name, "default_branch": default_branch, "commits": commit_history}, indent=2), encoding="utf-8")

    return {
        "repository": repo_name,
        "default_branch": default_branch,
        "description": description,
        "language": language,
        "source_path": str(repo_root),
        "history_path": str(history_path),
        "commits": commit_history,
    }
