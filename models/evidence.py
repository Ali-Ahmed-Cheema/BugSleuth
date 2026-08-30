"""
Evidence model for structured evidence tracking with source citations.
"""

from enum import Enum
from typing import Optional


class EvidenceStrength(str, Enum):
    """Classification of evidence strength levels."""
    STRONG = "STRONG"
    SUPPORTING = "SUPPORTING"
    WEAK = "WEAK"
    MISSING = "MISSING"


class EvidenceType(str, Enum):
    """Type of evidence source."""
    SOURCE_CODE = "source_code"
    APPLICATION_LOG = "application_log"
    GIT_HISTORY = "git_history"
    ERROR_TRACE = "error_trace"
    TEST_FAILURE = "test_failure"
    OBSERVATION = "observation"


class Evidence:
    """Represents a single piece of evidence with source citation."""

    def __init__(
        self,
        evidence_id: str,
        investigator: str,
        source_type: EvidenceType,
        source_file: str,
        line_number: Optional[int] = None,
        line_range: Optional[tuple[int, int]] = None,
        excerpt: str = "",
        explanation: str = "",
        strength: EvidenceStrength = EvidenceStrength.WEAK,
        tags: Optional[list[str]] = None,
    ):
        self.evidence_id = evidence_id
        self.investigator = investigator
        self.source_type = source_type
        self.source_file = source_file
        self.line_number = line_number
        self.line_range = line_range
        self.excerpt = excerpt
        self.explanation = explanation
        self.strength = strength
        self.tags = tags or []

    def to_dict(self) -> dict:
        """Convert evidence to dictionary for JSON serialization."""
        return {
            "evidence_id": self.evidence_id,
            "investigator": self.investigator,
            "source_type": self.source_type.value,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "line_range": self.line_range,
            "excerpt": self.excerpt,
            "explanation": self.explanation,
            "strength": self.strength.value,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Evidence":
        """Create Evidence from dictionary."""
        return cls(
            evidence_id=data["evidence_id"],
            investigator=data["investigator"],
            source_type=EvidenceType(data["source_type"]),
            source_file=data["source_file"],
            line_number=data.get("line_number"),
            line_range=data.get("line_range"),
            excerpt=data.get("excerpt", ""),
            explanation=data.get("explanation", ""),
            strength=EvidenceStrength(data.get("strength", "WEAK")),
            tags=data.get("tags", []),
        )
