"""
Similar patterns model for pattern detection and code review assistance.
"""

from enum import Enum
from typing import Optional


class RiskLevel(str, Enum):
    """Risk level for a similar pattern."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SimilarPattern:
    """Represents a similar code pattern found during analysis."""

    def __init__(
        self,
        pattern_id: str,
        source_file: str,
        line_number: Optional[int] = None,
        line_range: Optional[tuple[int, int]] = None,
        excerpt: str = "",
        similarity_reason: str = "",
        risk_level: RiskLevel = RiskLevel.LOW,
        match_confidence: float = 0.5,
    ):
        self.pattern_id = pattern_id
        self.source_file = source_file
        self.line_number = line_number
        self.line_range = line_range
        self.excerpt = excerpt
        self.similarity_reason = similarity_reason
        self.risk_level = risk_level
        self.match_confidence = max(0.0, min(1.0, match_confidence))

    def to_dict(self) -> dict:
        """Convert pattern to dictionary for JSON serialization."""
        return {
            "pattern_id": self.pattern_id,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "line_range": self.line_range,
            "excerpt": self.excerpt,
            "similarity_reason": self.similarity_reason,
            "risk_level": self.risk_level.value,
            "match_confidence": round(self.match_confidence, 2),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SimilarPattern":
        """Create SimilarPattern from dictionary."""
        return cls(
            pattern_id=data["pattern_id"],
            source_file=data["source_file"],
            line_number=data.get("line_number"),
            line_range=data.get("line_range"),
            excerpt=data.get("excerpt", ""),
            similarity_reason=data.get("similarity_reason", ""),
            risk_level=RiskLevel(data.get("risk_level", "LOW")),
            match_confidence=data.get("match_confidence", 0.5),
        )
