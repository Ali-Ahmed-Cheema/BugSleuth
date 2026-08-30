"""
Project analysis service for automatic project understanding.
"""

from pathlib import Path
from typing import Optional
from models import ProjectProfile


class ProjectAnalyzer:
    """Analyzes a project structure to create a project profile."""

    # Common file extensions by language
    LANGUAGE_PATTERNS = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".jsx": "JavaScript (React)",
        ".tsx": "TypeScript (React)",
        ".java": "Java",
        ".go": "Go",
        ".rb": "Ruby",
        ".php": "PHP",
        ".cs": "C#",
        ".cpp": "C++",
        ".c": "C",
        ".h": "C Header",
        ".hpp": "C++ Header",
        ".rs": "Rust",
        ".swift": "Swift",
        ".kt": "Kotlin",
    }

    FRAMEWORK_INDICATORS = {
        "flask": ("Flask", ["requirements.txt"]),
        "django": ("Django", ["requirements.txt"]),
        "fastapi": ("FastAPI", ["requirements.txt"]),
        "express": ("Express.js", ["package.json"]),
        "react": ("React", ["package.json"]),
        "vue": ("Vue.js", ["package.json"]),
        "angular": ("Angular", ["package.json"]),
        "spring": ("Spring", ["pom.xml", "build.gradle"]),
        "rails": ("Ruby on Rails", ["Gemfile"]),
        "laravel": ("Laravel", ["composer.json"]),
        "next": ("Next.js", ["package.json"]),
    }

    @staticmethod
    def analyze(source_path: Optional[Path], github_repo: Optional[dict] = None) -> ProjectProfile:
        """Analyze a project and return its profile."""

        project_name = "Unknown Project"
        if github_repo and github_repo.get("repository"):
            project_name = github_repo["repository"].split("/")[-1]
        elif source_path:
            project_name = source_path.name if source_path.is_dir() else source_path.parent.name

        profile = ProjectProfile(project_name=project_name)

        if not source_path and not github_repo:
            return profile

        if github_repo and github_repo.get("language"):
            profile.primary_language = github_repo["language"]
            profile.has_git_history = True

        if source_path and source_path.exists():
            files = []
            if source_path.is_file():
                files = [source_path]
            else:
                for ext in ProjectAnalyzer.LANGUAGE_PATTERNS:
                    files.extend(source_path.rglob(f"*{ext}"))
                files.extend(source_path.rglob(".github/workflows/*.yml"))
                files.extend(source_path.rglob(".github/workflows/*.yaml"))
                files.extend(source_path.rglob("**/Dockerfile"))
                files.extend(source_path.rglob("**/docker-compose*.yml"))
                files.extend(source_path.rglob("**/docker-compose*.yaml"))
                files.extend(source_path.rglob("**/*deployment*.yml"))
                files.extend(source_path.rglob("**/*deployment*.yaml"))
                files.extend(source_path.rglob("**/*service*.yml"))
                files.extend(source_path.rglob("**/*service*.yaml"))

            files = list(dict.fromkeys(files))[:400]
            profile.source_file_count = len(files)

            lang_counts = {}
            for file in files:
                ext = file.suffix.lower()
                if ext in ProjectAnalyzer.LANGUAGE_PATTERNS:
                    lang = ProjectAnalyzer.LANGUAGE_PATTERNS[ext]
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1

            if lang_counts:
                profile.primary_language = max(lang_counts, key=lang_counts.get)

            test_files = [f for f in files if "test" in f.name.lower() or "spec" in f.name.lower()]
            profile.test_file_count = len(test_files)

            if test_files:
                for test_file in test_files[:5]:
                    content = test_file.read_text(encoding="utf-8", errors="ignore").lower()
                    if "pytest" in content or "def test_" in content:
                        profile.test_framework = "Pytest"
                        break
                    elif "unittest" in content:
                        profile.test_framework = "Unittest"
                        break
                    elif "jest" in content or "describe(" in content:
                        profile.test_framework = "Jest"
                        break

            frameworks_found = set()
            root_files = list(source_path.iterdir()) if source_path.is_dir() else [source_path.parent]
            for file in root_files:
                if file.is_file():
                    name_lower = file.name.lower()
                    content = file.read_text(encoding="utf-8", errors="ignore").lower()
                    for framework_key, (framework_name, _) in ProjectAnalyzer.FRAMEWORK_INDICATORS.items():
                        if framework_key in content or framework_key in name_lower:
                            frameworks_found.add(framework_name)

            if frameworks_found:
                profile.framework = ", ".join(sorted(frameworks_found))

            dockerfile = next((f for f in files if f.name.lower() == "dockerfile"), None)
            compose_files = [f for f in files if f.name.lower() in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}]
            k8s_files = [f for f in files if f.name.lower().endswith((".yml", ".yaml")) and any(token in f.name.lower() for token in ["deployment", "service", "ingress", "statefulset", "configmap", "job", "k8s"])]
            workflow_files = [f for f in files if ".github/workflows" in str(f) or f.name.lower() in {"azure-pipelines.yml", "azure-pipelines.yaml", ".gitlab-ci.yml"}]

            profile.docker_detected = bool(dockerfile or compose_files)
            profile.compose_detected = bool(compose_files)
            profile.kubernetes_detected = bool(k8s_files)
            profile.pipeline_detected = bool(workflow_files)
            profile.deployment_profile = {
                "containerization": "Docker detected" if dockerfile or compose_files else "Not detected",
                "orchestration": "Kubernetes detected" if k8s_files else "Not detected",
                "infrastructure_as_code": "Terraform detected" if any(f.name.lower().endswith(".tf") for f in files) else "Not detected",
                "cloud_provider": "Not confidently identified",
                "dockerfile_present": bool(dockerfile),
                "compose_present": bool(compose_files),
                "kubernetes_files": [f.name for f in k8s_files[:10]],
            }

            entry_point_names = ["app.py", "main.py", "server.py", "manage.py", "index.js", "server.js", "index.ts"]
            entry_points = [f.name for f in files if f.name in entry_point_names]
            profile.entry_points = entry_points or []

            dep_file_names = ["requirements.txt", "package.json", "pyproject.toml", "pom.xml", "Gemfile", "composer.json", "build.gradle"]
            dep_files = [f.name for f in files if f.name in dep_file_names]
            profile.dependency_files = dep_files or []

            docs = [f for f in root_files if f.is_file() and (f.name.lower() == "readme.md" or "readme" in f.name.lower())]
            profile.has_readme = bool(docs)

            if profile.primary_language != "Unknown" and profile.source_file_count > 0:
                profile.detection_confidence = 0.9
            elif profile.source_file_count > 0:
                profile.detection_confidence = 0.7

        return profile
