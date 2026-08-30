"""
Hypothesis model for tracking multiple possible root causes.
"""

from enum import Enum
from typing import Optional


class HypothesisStatus(str, Enum):
    """Status of a hypothesis during investigation."""
    LEADING = "LEADING"
    UNDER_REVIEW = "UNDER_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECTED = "REJECTED"
    CONFIRMED = "CONFIRMED"


class Hypothesis:
    """Represents a possible root cause with evidence support."""

    def __init__(
        self,
        hypothesis_id: str,
        description: str,
        status: HypothesisStatus = HypothesisStatus.UNDER_REVIEW,
        confidence: float = 0.0,
        supporting_evidence: Optional[list[str]] = None,
        contradicting_evidence: Optional[list[str]] = None,
    ):
        self.hypothesis_id = hypothesis_id
        self.description = description
        self.status = status
        self.confidence = max(0.0, min(1.0, confidence))  # Clamp between 0 and 1
        self.supporting_evidence = supporting_evidence or []
        self.contradicting_evidence = contradicting_evidence or []

    def to_dict(self) -> dict:
        """Convert hypothesis to dictionary for JSON serialization."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "description": self.description,
            "status": self.status.value,
            "confidence": round(self.confidence, 2),
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Hypothesis":
        """Create Hypothesis from dictionary."""
        return cls(
            hypothesis_id=data["hypothesis_id"],
            description=data["description"],
            status=HypothesisStatus(data.get("status", "UNDER_REVIEW")),
            confidence=data.get("confidence", 0.0),
            supporting_evidence=data.get("supporting_evidence", []),
            contradicting_evidence=data.get("contradicting_evidence", []),
        )

    def set_status(self, status: HypothesisStatus) -> None:
        """Update hypothesis status."""
        self.status = status

    def update_confidence(self, confidence: float) -> None:
        """Update confidence level with validation."""
        self.confidence = max(0.0, min(1.0, confidence))

    def add_supporting_evidence(self, evidence_id: str) -> None:
        """Add supporting evidence ID."""
        if evidence_id not in self.supporting_evidence:
            self.supporting_evidence.append(evidence_id)

    def add_contradicting_evidence(self, evidence_id: str) -> None:
        """Add contradicting evidence ID."""
        if evidence_id not in self.contradicting_evidence:
            self.contradicting_evidence.append(evidence_id)
