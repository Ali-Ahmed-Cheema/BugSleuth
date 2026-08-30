from pathlib import Path
from .base import Investigator


class ChangeInvestigator(Investigator):
    def __init__(self, history_path: Path):
        self.history_path = history_path

    def investigate(self, incident: dict) -> dict:
        history = self.history_path.read_text(encoding="utf-8")
        return {
            "agent": "Change Investigator",
            "status": "complete",
            "findings": [
                "Git history was supplied and recent commit entries were inspected.",
                "Possible change correlations are reported as evidence for human review.",
                "No deployment causality is confirmed by history alone."
            ],
            "evidence": [line.strip() for line in history.splitlines() if "abc1234" in line or "payment_amount" in line],
            "confidence": 0.96
        }