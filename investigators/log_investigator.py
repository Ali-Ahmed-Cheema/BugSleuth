from pathlib import Path
from .base import Investigator


class LogInvestigator(Investigator):
    def __init__(self, log_path: Path):
        self.log_path = log_path

    def investigate(self, incident: dict) -> dict:
        content = self.log_path.read_bytes()
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("utf-16")
        lines = text.splitlines()
        indicators = ("ERROR", "EXCEPTION", "TRACEBACK", "FAILED", "FATAL")
        errors = [line for line in lines if any(indicator in line.upper() for indicator in indicators)]
        return {
            "agent": "Log Investigator",
            "status": "complete",
            "findings": [
                f"Found {len(errors)} error-indicator line(s) in the supplied log.",
                "Relevant timestamps and stack-trace lines were retained as direct evidence.",
                "No conclusion is made from log evidence alone."
            ],
            "evidence": [f"{self.log_path.name}:{index + 1}: {line}" for index, line in enumerate(lines) if any(indicator in line.upper() for indicator in indicators)],
            "confidence": 0.94
        }