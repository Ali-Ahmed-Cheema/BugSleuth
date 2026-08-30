"""
Project profile model for automatic project understanding.
"""

from typing import Optional, List


class ProjectProfile:
    """Represents discovered information about a project."""

    def __init__(
        self,
        project_name: str,
        primary_language: str = "Unknown",
        framework: Optional[str] = None,
        test_framework: Optional[str] = None,
        source_file_count: int = 0,
        test_file_count: int = 0,
        entry_points: Optional[List[str]] = None,
        dependency_files: Optional[List[str]] = None,
        has_git_history: bool = False,
        has_readme: bool = False,
        has_documentation: bool = False,
        detection_confidence: float = 1.0,
        docker_detected: bool = False,
        compose_detected: bool = False,
        kubernetes_detected: bool = False,
        pipeline_detected: bool = False,
        deployment_profile: Optional[dict] = None,
    ):
        self.project_name = project_name
        self.primary_language = primary_language
        self.framework = framework
        self.test_framework = test_framework
        self.source_file_count = source_file_count
        self.test_file_count = test_file_count
        self.entry_points = entry_points or []
        self.dependency_files = dependency_files or []
        self.has_git_history = has_git_history
        self.has_readme = has_readme
        self.has_documentation = has_documentation
        self.detection_confidence = max(0.0, min(1.0, detection_confidence))
        self.docker_detected = docker_detected
        self.compose_detected = compose_detected
        self.kubernetes_detected = kubernetes_detected
        self.pipeline_detected = pipeline_detected
        self.deployment_profile = deployment_profile or {
            "containerization": "Not detected",
            "orchestration": "Not detected",
            "infrastructure_as_code": "Not detected",
            "cloud_provider": "Not confidently identified",
        }

    def to_dict(self) -> dict:
        """Convert project profile to dictionary for JSON serialization."""
        return {
            "project_name": self.project_name,
            "primary_language": self.primary_language,
            "framework": self.framework,
            "test_framework": self.test_framework,
            "source_file_count": self.source_file_count,
            "test_file_count": self.test_file_count,
            "entry_points": self.entry_points,
            "dependency_files": self.dependency_files,
            "has_git_history": self.has_git_history,
            "has_readme": self.has_readme,
            "has_documentation": self.has_documentation,
            "detection_confidence": round(self.detection_confidence, 2),
            "docker_detected": self.docker_detected,
            "compose_detected": self.compose_detected,
            "kubernetes_detected": self.kubernetes_detected,
            "pipeline_detected": self.pipeline_detected,
            "deployment_profile": self.deployment_profile,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectProfile":
        """Create ProjectProfile from dictionary."""
        return cls(
            project_name=data["project_name"],
            primary_language=data.get("primary_language", "Unknown"),
            framework=data.get("framework"),
            test_framework=data.get("test_framework"),
            source_file_count=data.get("source_file_count", 0),
            test_file_count=data.get("test_file_count", 0),
            entry_points=data.get("entry_points", []),
            dependency_files=data.get("dependency_files", []),
            has_git_history=data.get("has_git_history", False),
            has_readme=data.get("has_readme", False),
            has_documentation=data.get("has_documentation", False),
            detection_confidence=data.get("detection_confidence", 1.0),
            docker_detected=data.get("docker_detected", False),
            compose_detected=data.get("compose_detected", False),
            kubernetes_detected=data.get("kubernetes_detected", False),
            pipeline_detected=data.get("pipeline_detected", False),
            deployment_profile=data.get("deployment_profile", {
                "containerization": "Not detected",
                "orchestration": "Not detected",
                "infrastructure_as_code": "Not detected",
                "cloud_provider": "Not confidently identified",
            }),
        )
