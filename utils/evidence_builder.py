"""
Evidence builder utility to convert investigator findings to structured Evidence objects.
"""

from models import Evidence, EvidenceStrength, EvidenceType
from typing import Optional


class EvidenceBuilder:
    """Builder for creating structured Evidence from investigator findings."""

    def __init__(self):
        self._evidence_counter = 0

    def _next_id(self) -> str:
        """Generate next evidence ID."""
        self._evidence_counter += 1
        return f"EV-{self._evidence_counter:05d}"

    def create_from_code_line(
        self,
        investigator: str,
        source_file: str,
        line_content: str,
        line_number: Optional[int] = None,
        explanation: str = "",
        strength: EvidenceStrength = EvidenceStrength.WEAK,
        tags: Optional[list[str]] = None,
    ) -> Evidence:
        """Create evidence from a code line finding."""
        return Evidence(
            evidence_id=self._next_id(),
            investigator=investigator,
            source_type=EvidenceType.SOURCE_CODE,
            source_file=source_file,
            line_number=line_number,
            excerpt=line_content,
            explanation=explanation,
            strength=strength,
            tags=tags or [],
        )

    def create_from_log_entry(
        self,
        investigator: str,
        source_file: str,
        log_line: str,
        explanation: str = "",
        strength: EvidenceStrength = EvidenceStrength.WEAK,
        tags: Optional[list[str]] = None,
    ) -> Evidence:
        """Create evidence from a log entry."""
        return Evidence(
            evidence_id=self._next_id(),
            investigator=investigator,
            source_type=EvidenceType.APPLICATION_LOG,
            source_file=source_file,
            excerpt=log_line,
            explanation=explanation,
            strength=strength,
            tags=tags or [],
        )

    def create_from_git_history(
        self,
        investigator: str,
        commit_hash: str,
        commit_message: str,
        explanation: str = "",
        strength: EvidenceStrength = EvidenceStrength.WEAK,
        tags: Optional[list[str]] = None,
    ) -> Evidence:
        """Create evidence from git history."""
        return Evidence(
            evidence_id=self._next_id(),
            investigator=investigator,
            source_type=EvidenceType.GIT_HISTORY,
            source_file=commit_hash,
            excerpt=commit_message,
            explanation=explanation,
            strength=strength,
            tags=tags or [],
        )

    def create_generic(
        self,
        investigator: str,
        source_type: EvidenceType,
        source_file: str,
        excerpt: str = "",
        explanation: str = "",
        strength: EvidenceStrength = EvidenceStrength.WEAK,
        line_number: Optional[int] = None,
        line_range: Optional[tuple[int, int]] = None,
        tags: Optional[list[str]] = None,
    ) -> Evidence:
        """Create generic evidence object."""
        return Evidence(
            evidence_id=self._next_id(),
            investigator=investigator,
            source_type=source_type,
            source_file=source_file,
            line_number=line_number,
            line_range=line_range,
            excerpt=excerpt,
            explanation=explanation,
            strength=strength,
            tags=tags or [],
        )
