from pathlib import Path
from .base import Investigator


class CodeInvestigator(Investigator):
    def __init__(self, source_path: Path):
        self.source_path = source_path

    def _match_keywords(self, text: str) -> list[str]:
        text = text.lower()
        keywords = [
            "error", "exception", "traceback", "timeout", "invalid", "failed", "crash",
            "payment", "api", "request", "response", "db", "database", "auth", "login",
            "validation", "routing", "service", "handler"
        ]
        return [keyword for keyword in keywords if keyword in text]

    def investigate(self, incident: dict) -> dict:
        supported = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".php", ".cs", ".sql", ".yaml", ".yml", ".json", ".md", ".html", ".css", ".c", ".cpp", ".h", ".hpp", ".sh", ".xml"}
        files = [self.source_path] if self.source_path.is_file() else [path for path in self.source_path.rglob("*") if path.is_file() and path.suffix.lower() in supported]

        observation = (incident.get("user_observation") or "").strip()
        repo_names = [token.strip("./") for token in observation.lower().split() if len(token) > 3]
        evidence_lines = []
        findings = [
            f"Inspected {len(files)} supported source file(s) without executing them.",
            "The repository structure was analyzed, but a root cause is only claimed when there is concrete incident evidence."
        ]

        if not observation and not incident.get("logs_path"):
            findings.append("No error trace, failing test, or incident evidence was available to identify a specific failing execution path. No root cause is being claimed.")
            return {
                "agent": "Code Investigator",
                "status": "complete",
                "findings": findings,
                "evidence": [],
                "confidence": 0.18,
            }

        relevant_files = []
        for path in files[:400]:
            name_lower = path.name.lower()
            if any(keyword in name_lower for keyword in ["test", "api", "service", "handler", "auth", "payment", "route", "config", "model", "controller", "view"]):
                relevant_files.append(path)
            elif any(keyword in observation.lower() for keyword in ["payment", "api", "auth", "login", "route", "database", "error"]):
                if any(keyword in name_lower for keyword in self._match_keywords(observation)):
                    relevant_files.append(path)

        if not relevant_files:
            relevant_files = files[:20]

        for path in relevant_files[:50]:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for index, line in enumerate(lines[:250], 1):
                if observation and any(keyword in line.lower() for keyword in self._match_keywords(observation)):
                    evidence_lines.append(f"{path.name}:{index}: {line.strip()}")
                elif path.name.lower().endswith((".py", ".js", ".ts")) and any(token in line.lower() for token in ["raise", "throw", "return", "if ", "try:", "except", "catch"]):
                    evidence_lines.append(f"{path.name}:{index}: {line.strip()}")

        if not evidence_lines:
            findings.append("No specific failing code path was identified from the available evidence. The repository was inspected, but no root cause is being claimed.")
            return {
                "agent": "Code Investigator",
                "status": "complete",
                "findings": findings,
                "evidence": [],
                "confidence": 0.22,
            }

        findings.append(f"Relevant code inspection identified {len(evidence_lines)} evidence-backed line(s) for review.")
        return {
            "agent": "Code Investigator",
            "status": "complete",
            "findings": findings,
            "evidence": evidence_lines[:20],
            "confidence": 0.62,
        }